"""Public sign-up: request, e-mail verification and workspace provisioning (plan v4, section 4)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import security
from app.auth.deps import mfa_setup_required
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.validators import digits, is_valid_abn
from app.domains import DOMAINS, apply_domain, finish_ready_workspace
from app.models import User
from app.models.platform import SignupRequest, Tenant
from app.security.seed_v1 import stable_id
from app.services import audit
from app.services.audit import AuditAction, RequestMeta
from app.services.auth import IssuedSession, LoginState, _issue_session
from app.tenancy import bind_tenant, by_schema

logger = logging.getLogger("app.signup")
UNVERIFIED_RETENTION = timedelta(days=7)


class SignupError(AppError):
    status_code = 400
    code = "signup_invalid"


@dataclass(frozen=True)
class Provisioned:
    slug: str
    name: str
    issued: IssuedSession
    state: LoginState


def utcnow() -> datetime:
    return datetime.now(UTC)


def verification_required() -> bool:
    """Whether sign-up e-mails a confirmation link before creating the workspace (SIGNUP_EMAIL_VERIFICATION).

    "auto": always in production; elsewhere only when e-mail is set up, so a development or staging install
    without a mail server can still create workspaces.
    """
    settings = get_settings()
    if settings.signup_email_verification != "auto":
        return settings.signup_email_verification == "required"
    if settings.is_production:
        return True
    from app.services.mail_settings import mail_config

    return mail_config().configured


def start_signup(
    db: Session, *, domain: str, firm_name: str, name: str, email: str, password: str, abn: str | None
) -> str:
    """Store a pending sign-up and return the verification token (to e-mail). ``db`` is a platform session."""
    if not get_settings().signup_enabled:
        raise SignupError("Sign-up is closed.", status_code=403, code="signup_closed")
    if domain not in DOMAINS:
        raise SignupError("Choose what kind of firm you run.", fields={"domain": "Choose a domain."})
    email = email.strip().lower()
    if not firm_name.strip():
        raise SignupError("Enter your firm's name.", fields={"firm_name": "Required."})
    if abn and digits(abn) and not is_valid_abn(abn):
        raise SignupError(
            "That ABN isn't valid. Check the 11 digits, or leave it blank.",
            fields={"abn": "Not a valid ABN."},
        )
    errors = security.password_policy_errors(password, email=email, name=name)
    if errors:
        raise AppError(errors[0], status_code=422, code="weak_password", fields={"password": errors[0]})
    token = security.generate_token()
    db.add(
        SignupRequest(
            token_hash=security.hash_token(token),
            email=email,
            name=name.strip(),
            firm_name=firm_name.strip(),
            domain=domain,
            abn=digits(abn or "") or None,
            password_hash=security.hash_password(password),
            expires_at=utcnow() + timedelta(hours=get_settings().signup_verification_hours),
        )
    )
    db.commit()
    return token


def pending_signup(db: Session, token: str) -> SignupRequest:
    req = db.scalar(
        select(SignupRequest).where(SignupRequest.token_hash == security.hash_token(token)).with_for_update()
    )
    if req is None or req.verified_at is not None or req.expires_at <= utcnow():
        raise SignupError(
            "This link is invalid or has expired. Sign up again to get a new one.", code="token_invalid"
        )
    return req


def verify_and_provision(platform: Session, tenant_db: Session, token: str, meta: RequestMeta) -> Provisioned:
    """Create the workspace and its administrator, then sign the administrator in."""
    from app.db.migrate import create_tenant, drop_tenant, refill_warm_pool_soon

    req = pending_signup(platform, token)
    try:
        tenant_id, slug, schema = create_tenant(req.firm_name, req.domain)
    except Exception as exc:
        logger.exception("Workspace provisioning failed", extra={"domain": req.domain})
        raise AppError(
            "We couldn't create your workspace just now. Open the link again in a minute.",
            status_code=503,
            code="provisioning_failed",
        ) from exc
    refill_warm_pool_soon()
    try:
        return _set_up_workspace(platform, tenant_db, req, tenant_id, slug, schema, meta)
    except Exception as exc:
        # Leave nothing half-built: the link stays valid, so the person can simply try again.
        tenant_db.rollback()
        platform.rollback()
        try:
            drop_tenant(schema)
        except Exception:
            logger.exception("Could not remove a half-built workspace", extra={"schema": schema})
        if isinstance(exc, AppError):
            raise
        logger.exception("Workspace set-up failed", extra={"domain": req.domain})
        raise AppError(
            "We couldn't finish setting up your workspace. Open the link again in a minute.",
            status_code=503,
            code="provisioning_failed",
        ) from exc


def _set_up_workspace(
    platform: Session,
    tenant_db: Session,
    req: SignupRequest,
    tenant_id: uuid.UUID,
    slug: str,
    schema: str,
    meta: RequestMeta,
) -> Provisioned:
    tenant = by_schema(schema)
    if tenant is None:  # pragma: no cover - create_tenant refreshes the catalogue
        raise AppError("The workspace could not be created. Try again.", status_code=503)
    bind_tenant(tenant_db, tenant)

    from app.services.settings import get_setting, set_setting

    company = dict(get_setting(tenant_db, "company") or {})
    company.update({"legal_name": req.firm_name, "abn": req.abn or "", "email": req.email})
    set_setting(tenant_db, "company", company)
    user = User(
        email=req.email,
        name=req.name,
        profile_id=stable_id("profile", "system_administrator"),
        role_id=stable_id("role", "ceo"),
        password_hash=req.password_hash,
        is_active=True,
    )
    tenant_db.add(user)
    tenant_db.flush()
    from app.db.migrate import is_ready_made

    if is_ready_made(schema, req.domain):
        finish_ready_workspace(tenant_db, user.id)  # set up ahead of time: only the firm's details left
    else:
        apply_domain(tenant_db, req.domain, user.id)
    audit.record(
        tenant_db,
        action=AuditAction.CREATE,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        summary=f"Workspace created for {req.firm_name}; {req.email} is its administrator",
        meta=meta,
    )
    needs_mfa = mfa_setup_required(user)
    issued = _issue_session(tenant_db, user, mfa_verified=not needs_mfa, meta=meta)
    if not needs_mfa:
        user.last_login_at = utcnow()
    tenant_db.commit()

    req.verified_at = utcnow()
    req.tenant_id = tenant_id
    req.password_hash = None
    row = platform.get(Tenant, tenant_id)
    if row is not None:
        row.verified_at = utcnow()
    platform.commit()
    return Provisioned(
        slug=slug,
        name=req.firm_name,
        issued=issued,
        state=LoginState.MFA_SETUP_REQUIRED if needs_mfa else LoginState.AUTHENTICATED,
    )


def purge_unverified(db: Session) -> int:
    """Remove sign-ups never verified within 7 days (and spent ones)."""
    cutoff = utcnow() - UNVERIFIED_RETENTION
    result = db.execute(delete(SignupRequest).where(SignupRequest.created_at < cutoff))
    db.commit()
    return int(getattr(result, "rowcount", 0) or 0)

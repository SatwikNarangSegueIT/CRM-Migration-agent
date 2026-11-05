"""/platform: settings for the whole platform (outgoing e-mail) and a status check of everything sign-up
depends on. Only System Administrators of the operator workspace (PLATFORM_OPERATOR_WORKSPACE, default the
first workspace) can use it: a firm's administrators can't change how every firm's e-mail is sent."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.deps import AuthContext, DbSession, StaffAuth
from app.core.config import get_settings, is_pooled_url
from app.core.errors import AppError, PermissionDeniedError
from app.core.rate_limit import check_rate_limit
from app.services import audit
from app.services import mail_settings as mail
from app.services.audit import AuditAction, RequestMeta
from app.services.email import MailDeliveryError, send
from app.tenancy import DEFAULT_SCHEMA, tenant_schema, tenant_slug

router = APIRouter(prefix="/platform", tags=["platform"])


def is_platform_operator(db: Session, auth: AuthContext) -> bool:
    if not auth.session.mfa_verified or not auth.is_staff or not auth.policy.is_system_admin:
        return False
    wanted = get_settings().platform_operator_workspace
    if wanted:
        return tenant_slug(db) == wanted
    return tenant_schema(db) == DEFAULT_SCHEMA


def require_operator(db: DbSession, auth: StaffAuth) -> AuthContext:
    if not is_platform_operator(db, auth):
        raise PermissionDeniedError(
            "Only System Administrators of the platform's own workspace can change platform settings."
        )
    return auth


Operator = Annotated[AuthContext, Depends(require_operator)]


class EmailSettingsIn(BaseModel):
    provider: Literal["console", "smtp", "zeptomail"]
    from_name: str = Field(default="", max_length=120)
    from_email: EmailStr | None = None
    smtp_host: str = Field(default="", max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_username: str = Field(default="", max_length=254)
    # Blank keeps the saved password / token.
    smtp_password: str | None = Field(default=None, max_length=500)
    zeptomail_api_url: str = Field(default=mail.ZEPTOMAIL_DEFAULT_URL, max_length=255)
    zeptomail_token: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _complete(self) -> EmailSettingsIn:
        fields: dict[str, str] = {}
        if self.provider != "console" and not self.from_email:
            fields["from_email"] = "Enter the address e-mails come from."
        if self.provider == "smtp" and not self.smtp_host.strip():
            fields["smtp_host"] = "Enter the SMTP server."
        if self.provider == "zeptomail" and not self.zeptomail_api_url.startswith("https://"):
            fields["zeptomail_api_url"] = "Use the https:// API URL shown in ZeptoMail."
        if fields:
            raise AppError(
                next(iter(fields.values())), status_code=422, code="validation_error", fields=fields
            )
        return self

    def values(self) -> dict[str, Any]:
        data = self.model_dump()
        data["from_email"] = str(self.from_email) if self.from_email else ""
        data["smtp_host"] = self.smtp_host.strip()
        data["smtp_username"] = self.smtp_username.strip()
        return data


class TestEmailIn(BaseModel):
    to: EmailStr
    # Unsaved values from the form; omit to test what is saved.
    settings: EmailSettingsIn | None = None


def _email_payload() -> dict[str, Any]:
    return {
        "settings": mail.mail_config().public(),
        "environment": mail.from_environment().public(),
        "zoho_smtp_hosts": [
            {"key": key, "label": label, "personal": personal, "organisation": organisation}
            for key, (label, personal, organisation) in mail.ZOHO_SMTP_HOSTS.items()
        ],
        "zeptomail_default_url": mail.ZEPTOMAIL_DEFAULT_URL,
    }


@router.get("/email")
def read_email(_: Operator) -> dict[str, Any]:
    return _email_payload()


@router.put("/email")
def write_email(body: EmailSettingsIn, request: Request, db: DbSession, auth: Operator) -> dict[str, Any]:
    mail.save(body.values(), updated_by=auth.user.email)
    audit.record(
        db,
        action=AuditAction.UPDATE,
        entity_type="platform_setting",
        entity_id="email",
        summary=f"Platform e-mail delivery set to {body.provider}",
        actor_id=auth.user.id,
        meta=RequestMeta.from_request(request),
    )
    db.commit()
    return _email_payload()


@router.delete("/email")
def reset_email(request: Request, db: DbSession, auth: Operator) -> dict[str, Any]:
    mail.clear()
    audit.record(
        db,
        action=AuditAction.UPDATE,
        entity_type="platform_setting",
        entity_id="email",
        summary="Platform e-mail delivery reset to the environment settings",
        actor_id=auth.user.id,
        meta=RequestMeta.from_request(request),
    )
    db.commit()
    return _email_payload()


@router.post("/email/test")
def test_email(body: TestEmailIn, auth: Operator) -> dict[str, str]:
    check_rate_limit("email-test", str(auth.user.id), limit=10, window_seconds=600)
    config = mail.candidate(body.settings.values()) if body.settings else mail.mail_config()
    if config.provider == "console":
        raise AppError(
            "E-mail is set to log only, so nothing would be sent. Choose Zoho Mail (SMTP), ZeptoMail or "
            "another SMTP server first.",
            status_code=400,
            code="email_not_configured",
        )
    try:
        send(
            str(body.to),
            "Test e-mail from Segue CRM",
            "This is a test of your outgoing e-mail settings. If you can read it, sign-up confirmations, "
            "password resets and invitations will arrive too.\n",
            config=config,
        )
    except MailDeliveryError as exc:
        raise AppError(str(exc), status_code=400, code="email_failed") from exc
    return {"message": f"Test e-mail sent to {body.to}. Check the inbox (and spam folder)."}


# ------------------------------------------------------------------ status


@lru_cache
def _heads() -> tuple[str, str]:
    from alembic.script import ScriptDirectory

    from app.db.migrate import _config

    platform = ScriptDirectory.from_config(_config("alembic_platform")).get_current_head() or ""
    tenant = ScriptDirectory.from_config(_config("alembic")).get_current_head() or ""
    return platform, tenant


def _check(key: str, label: str, status: str, detail: str) -> dict[str, str]:
    return {"key": key, "label": label, "status": status, "detail": detail}


@router.get("/status")
def platform_status(db: DbSession, _: Operator) -> list[dict[str, str]]:
    """Everything sign-up and e-mail depend on, with what to do about anything that isn't right."""
    from app.services.signup import verification_required
    from app.worker.dispatch import worker_available

    settings = get_settings()
    checks: list[dict[str, str]] = []
    platform_head, tenant_head = _heads()

    try:
        platform_version = db.execute(text("SELECT version_num FROM platform.alembic_version")).scalar()
    except Exception:
        db.rollback()
        platform_version = None
    checks.append(
        _check("platform_schema", "Platform database", "ok", f"Up to date ({platform_version}).")
        if platform_version == platform_head
        else _check(
            "platform_schema",
            "Platform database",
            "error",
            f"At {platform_version or 'nothing'}, expected {platform_head}. Run deploy/neon_upgrade_v6.sql "
            "in the Neon SQL Editor, or `python -m app.cli migrate`.",
        )
    )
    try:
        tenant_version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        db.rollback()
        tenant_version = None
    checks.append(
        _check("workspace_schema", "This workspace's database", "ok", f"Up to date ({tenant_version}).")
        if tenant_version == tenant_head
        else _check(
            "workspace_schema",
            "This workspace's database",
            "error",
            f"At {tenant_version or 'nothing'}, expected {tenant_head}. Run `python -m app.cli migrate`.",
        )
    )

    direct = settings.database_url_direct
    if direct and not is_pooled_url(direct):
        checks.append(
            _check("direct_url", "Direct database connection", "ok", "Set: new workspaces build on it.")
        )
    else:
        checks.append(
            _check(
                "direct_url",
                "Direct database connection",
                "warn",
                "DATABASE_URL_DIRECT isn't set to a direct (non -pooler) endpoint. New workspaces are built "
                "through the pooled connection: it works, but set it for faster, more reliable sign-ups.",
            )
        )

    config = mail.mail_config()
    source = "Setup" if config.source == "setup" else "environment variables"
    if config.configured:
        where = config.smtp_host if config.provider == "smtp" else "ZeptoMail API"
        checks.append(
            _check(
                "email",
                "Outgoing e-mail",
                "ok",
                f"{config.provider.upper()} via {where}, from {config.from_email} (from {source}). Use "
                '"Send test e-mail" to confirm it works.',
            )
        )
    else:
        checks.append(
            _check(
                "email",
                "Outgoing e-mail",
                "error" if settings.is_production else "warn",
                "Not set up: e-mails are only written to the log, so confirmation links, password resets and "
                "invitations never arrive. Set it up below.",
            )
        )

    if verification_required():
        detail = "New firms confirm their e-mail address before the workspace is created."
        status = "ok" if config.configured else "error"
        if not config.configured:
            detail += " E-mail isn't set up, so nobody can finish signing up."
        checks.append(_check("signup", "Sign-up", status, detail))
    else:
        checks.append(
            _check(
                "signup",
                "Sign-up",
                "warn",
                "Workspaces are created straight away without confirming the e-mail address, because e-mail "
                "isn't set up (or SIGNUP_EMAIL_VERIFICATION=off). Fine for testing; set up e-mail before "
                "launch.",
            )
        )

    if worker_available():
        checks.append(
            _check("worker", "Background worker", "ok", "Running: it sends e-mail and runs imports.")
        )
    else:
        checks.append(
            _check(
                "worker",
                "Background worker",
                "warn",
                "Not running. E-mail, imports and index builds run in the API instead, but reminders, "
                "scheduled reports and marketing schedules need the worker and scheduler (Celery).",
            )
        )

    ready = db.execute(text("SELECT count(*) FROM platform.warm_schemas")).scalar() or 0
    wanted = settings.signup_warm_pool_size
    checks.append(
        _check("warm_pool", "Ready-made workspaces", "ok", f"{ready} ready: new workspaces open in seconds.")
        if ready >= min(wanted, 1)
        else _check(
            "warm_pool",
            "Ready-made workspaces",
            "warn",
            f"{ready} of {wanted} ready. The API builds them in the background after a restart; until then a "
            "new workspace is built on the spot (slower, especially far from the database's region).",
        )
    )

    url = settings.public_app_url
    local = "localhost" in url or "127.0.0.1" in url
    checks.append(
        _check(
            "public_url",
            "Address in e-mail links",
            "error" if local and settings.is_production else ("warn" if local else "ok"),
            f"{url}" + (" - set PUBLIC_APP_URL to the address people open." if local else ""),
        )
    )
    return checks

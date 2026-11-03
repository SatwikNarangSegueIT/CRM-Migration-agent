"""Authentication workflows: login, MFA, sessions, password change/reset, invitations.

Each public function commits its own transaction. E-mails are queued by the caller after commit.
"""

from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

import segno
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.auth import security
from app.auth.deps import AuthContext, mfa_setup_required, utcnow
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import RecoveryCode, User, UserSession, UserToken
from app.models.user import TokenPurpose
from app.services import audit
from app.services.audit import AuditAction, RequestMeta


class InvalidCredentialsError(AppError):
    status_code = 401
    code = "invalid_credentials"


class IncorrectPasswordError(AppError):
    """Wrong password while already signed in (422, so the client does not treat it as signed out)."""

    status_code = 422
    code = "incorrect_password"


class AccountLockedError(AppError):
    status_code = 423
    code = "account_locked"


class InvalidTokenError(AppError):
    status_code = 400
    code = "invalid_token"


class LoginState(StrEnum):
    AUTHENTICATED = "authenticated"
    MFA_REQUIRED = "mfa_required"
    MFA_SETUP_REQUIRED = "mfa_setup_required"


@dataclass(frozen=True)
class IssuedSession:
    token: str
    csrf_token: str
    session: UserSession


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_new_password(password: str, user: User, *, field: str) -> None:
    """Raise 422 `weak_password` with the error on `field` (the request's password field name)."""
    errors = security.password_policy_errors(password, email=user.email, name=user.name)
    if errors:
        raise AppError(" ".join(errors), code="weak_password", status_code=422, fields={field: errors[0]})


# ---------------------------------------------------------------- sessions


def _issue_session(db: Session, user: User, *, mfa_verified: bool, meta: RequestMeta) -> IssuedSession:
    settings = get_settings()
    now = utcnow()
    # Opportunistic cleanup of this user's expired sessions.
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at <= now))
    token, csrf = security.generate_token(), security.generate_token()
    session = UserSession(
        user_id=user.id,
        token_hash=security.hash_token(token),
        csrf_token_hash=security.hash_token(csrf),
        mfa_verified=mfa_verified,
        expires_at=now + timedelta(hours=settings.session_absolute_hours),
        last_seen_at=now,
        ip_address=meta.ip_address,
        user_agent=meta.user_agent,
    )
    db.add(session)
    return IssuedSession(token=token, csrf_token=csrf, session=session)


def revoke_sessions(db: Session, user_id: uuid.UUID, *, except_session_id: uuid.UUID | None = None) -> int:
    stmt = delete(UserSession).where(UserSession.user_id == user_id)
    if except_session_id is not None:
        stmt = stmt.where(UserSession.id != except_session_id)
    result = db.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)


def _login_state(user: User, mfa_verified: bool) -> LoginState:
    if mfa_verified:
        return LoginState.AUTHENTICATED
    return LoginState.MFA_REQUIRED if user.mfa_enabled else LoginState.MFA_SETUP_REQUIRED


def _register_failure(db: Session, user: User, meta: RequestMeta, *, action: AuditAction, what: str) -> bool:
    """Count a failed attempt; lock the account when the limit is reached. Returns True if now locked."""
    settings = get_settings()
    user.failed_login_count += 1
    locked = user.failed_login_count >= settings.login_max_failures
    audit.record(
        db, action=action, entity_type="user", entity_id=user.id, actor_id=user.id, summary=what, meta=meta
    )
    if locked:
        user.locked_until = utcnow() + timedelta(minutes=settings.login_lockout_minutes)
        user.failed_login_count = 0
        revoke_sessions(db, user.id)
        audit.record(
            db,
            action=AuditAction.ACCOUNT_LOCKED,
            entity_type="user",
            entity_id=user.id,
            actor_id=user.id,
            summary=f"Account locked for {settings.login_lockout_minutes} minutes after repeated failures",
            meta=meta,
        )
    return locked


def _ensure_not_locked(user: User) -> None:
    if user.locked_until is not None and user.locked_until > utcnow():
        raise AccountLockedError("Too many failed attempts. The account is locked; try again later.")


# ---------------------------------------------------------------- login / logout


def login(db: Session, email: str, password: str, meta: RequestMeta) -> tuple[IssuedSession, LoginState]:
    email = normalize_email(email)
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        security.verify_password(None, password)  # equalise timing
        audit.record(
            db,
            action=AuditAction.LOGIN_FAILED,
            entity_type="user",
            actor_id=None,
            summary=f"Failed sign-in for unknown e-mail {email[:254]}",
            meta=meta,
        )
        db.commit()
        raise InvalidCredentialsError("Invalid e-mail or password.")

    _ensure_not_locked(user)
    password_ok = security.verify_password(user.password_hash, password)
    if not password_ok or not user.is_active:
        # Same response for every failure so the reason is not disclosed.
        if password_ok:
            reason = "account is deactivated"
        elif user.password_hash is None:
            reason = "invitation not accepted"
        else:
            reason = "wrong password"
        _register_failure(db, user, meta, action=AuditAction.LOGIN_FAILED, what=f"Failed sign-in ({reason})")
        db.commit()
        raise InvalidCredentialsError("Invalid e-mail or password.")

    assert user.password_hash is not None
    if security.password_needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(password)
    user.failed_login_count = 0
    user.locked_until = None

    needs_mfa = user.mfa_enabled or mfa_setup_required(user)
    issued = _issue_session(db, user, mfa_verified=not needs_mfa, meta=meta)
    if not needs_mfa:
        user.last_login_at = utcnow()
        audit.record(
            db,
            action=AuditAction.LOGIN,
            entity_type="user",
            entity_id=user.id,
            actor_id=user.id,
            summary="Signed in",
            meta=meta,
        )
    db.commit()
    return issued, _login_state(user, not needs_mfa)


def logout(db: Session, auth: AuthContext, meta: RequestMeta) -> None:
    audit.record(
        db,
        action=AuditAction.LOGOUT,
        entity_type="user",
        entity_id=auth.user.id,
        actor_id=auth.user.id,
        summary="Signed out",
        meta=meta,
    )
    db.delete(auth.session)
    db.commit()


# ---------------------------------------------------------------- MFA


def _complete_mfa_session(db: Session, auth: AuthContext, meta: RequestMeta) -> IssuedSession:
    """Replace the pending session with a fully authenticated one (prevents session fixation)."""
    user = auth.user
    db.delete(auth.session)
    issued = _issue_session(db, user, mfa_verified=True, meta=meta)
    user.failed_login_count = 0
    user.last_login_at = utcnow()
    return issued


def verify_mfa(db: Session, auth: AuthContext, code: str, meta: RequestMeta) -> IssuedSession:
    user = auth.user
    if auth.session.mfa_verified:
        raise AppError(
            "Multi-factor authentication is already complete.", code="mfa_not_pending", status_code=409
        )
    if not user.mfa_enabled or user.mfa_secret_encrypted is None:
        raise AppError(
            "Set up multi-factor authentication first.", code="mfa_setup_required", status_code=409
        )
    _ensure_not_locked(user)

    cleaned = code.strip()
    method = "authenticator code"
    ok = False
    if cleaned.replace(" ", "").isdigit():
        secret = security.decrypt_field(user.mfa_secret_encrypted)
        step = security.verify_totp(secret, cleaned, last_used_step=user.mfa_last_used_step)
        if step is not None:
            user.mfa_last_used_step = step
            ok = True
    else:
        method = "recovery code"
        recovery = db.scalar(
            select(RecoveryCode).where(
                RecoveryCode.user_id == user.id,
                RecoveryCode.code_hash == security.hash_recovery_code(cleaned),
                RecoveryCode.used_at.is_(None),
            )
        )
        if recovery is not None:
            recovery.used_at = utcnow()
            ok = True

    if not ok:
        _register_failure(db, user, meta, action=AuditAction.MFA_FAILED, what=f"Invalid {method}")
        db.commit()
        # 422 (not 401): the session itself is still valid.
        raise AppError(
            "The code is not valid. Try again.",
            code="invalid_code",
            status_code=422,
            fields={"code": "Invalid code"},
        )

    issued = _complete_mfa_session(db, auth, meta)
    if method == "recovery code":
        audit.record(
            db,
            action=AuditAction.RECOVERY_CODE_USED,
            entity_type="user",
            entity_id=user.id,
            actor_id=user.id,
            summary="Signed in with a recovery code",
            meta=meta,
        )
    audit.record(
        db,
        action=AuditAction.LOGIN,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        summary=f"Signed in (MFA: {method})",
        meta=meta,
    )
    db.commit()
    return issued


@dataclass(frozen=True)
class MfaSetup:
    secret: str
    otpauth_uri: str
    qr_svg_data_uri: str


def begin_mfa_setup(db: Session, auth: AuthContext) -> MfaSetup:
    user = auth.user
    if user.mfa_enabled:
        raise AppError(
            "Multi-factor authentication is already enabled. Ask an administrator to reset it.",
            code="mfa_already_enabled",
            status_code=409,
        )
    # Reuse a pending (not yet confirmed) secret so a repeated request shows the same QR code.
    if user.mfa_secret_encrypted is not None:
        secret = security.decrypt_field(user.mfa_secret_encrypted)
    else:
        secret = security.new_totp_secret()
        user.mfa_secret_encrypted = security.encrypt_field(secret)
        user.mfa_last_used_step = None
        db.commit()
    uri = security.totp_uri(secret, user.email)
    svg = segno.make(uri, error="m").svg_inline(scale=5, border=2, dark="#0f172a", light="#ffffff")
    data_uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
    return MfaSetup(secret=secret, otpauth_uri=uri, qr_svg_data_uri=data_uri)


def complete_mfa_setup(
    db: Session, auth: AuthContext, code: str, meta: RequestMeta
) -> tuple[IssuedSession, list[str]]:
    user = auth.user
    if user.mfa_enabled:
        raise AppError(
            "Multi-factor authentication is already enabled.", code="mfa_already_enabled", status_code=409
        )
    if user.mfa_secret_encrypted is None:
        raise AppError("Start the set-up first.", code="mfa_setup_not_started", status_code=409)
    secret = security.decrypt_field(user.mfa_secret_encrypted)
    step = security.verify_totp(secret, code, last_used_step=None)
    if step is None:
        raise AppError(
            "The code is not valid. Check your authenticator app.",
            code="invalid_code",
            status_code=422,
            fields={"code": "Invalid code"},
        )

    user.mfa_enabled = True
    user.mfa_last_used_step = step
    codes = _replace_recovery_codes(db, user)
    issued = _complete_mfa_session(db, auth, meta) if not auth.session.mfa_verified else _keep(auth)
    audit.record(
        db,
        action=AuditAction.MFA_ENABLED,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        summary="Multi-factor authentication enabled",
        meta=meta,
    )
    if issued.session is not auth.session:
        audit.record(
            db,
            action=AuditAction.LOGIN,
            entity_type="user",
            entity_id=user.id,
            actor_id=user.id,
            summary="Signed in (MFA set up)",
            meta=meta,
        )
    db.commit()
    return issued, codes


def _keep(auth: AuthContext) -> IssuedSession:
    # Already fully authenticated (optional MFA for clients): keep the current session and cookies.
    return IssuedSession(token="", csrf_token="", session=auth.session)


def _replace_recovery_codes(db: Session, user: User) -> list[str]:
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    codes = security.generate_recovery_codes()
    db.add_all(RecoveryCode(user_id=user.id, code_hash=security.hash_recovery_code(c)) for c in codes)
    return codes


def regenerate_recovery_codes(db: Session, auth: AuthContext, password: str, meta: RequestMeta) -> list[str]:
    user = auth.user
    if not user.mfa_enabled:
        raise AppError("Multi-factor authentication is not enabled.", code="mfa_not_enabled", status_code=409)
    if not security.verify_password(user.password_hash, password):
        raise IncorrectPasswordError("Password is incorrect.", fields={"password": "Incorrect password"})
    codes = _replace_recovery_codes(db, user)
    audit.record(
        db,
        action=AuditAction.UPDATE,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        summary="Recovery codes regenerated",
        meta=meta,
    )
    db.commit()
    return codes


def remaining_recovery_codes(db: Session, user_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(RecoveryCode)
            .where(RecoveryCode.user_id == user_id, RecoveryCode.used_at.is_(None))
        )
        or 0
    )


# ---------------------------------------------------------------- passwords


def change_password(db: Session, auth: AuthContext, current: str, new: str, meta: RequestMeta) -> None:
    user = auth.user
    if not security.verify_password(user.password_hash, current):
        raise IncorrectPasswordError(
            "Current password is incorrect.", fields={"current_password": "Incorrect password"}
        )
    if current == new:
        raise AppError(
            "Choose a password you have not just used.",
            code="weak_password",
            status_code=422,
            fields={"new_password": "Same as current password"},
        )
    validate_new_password(new, user, field="new_password")
    user.password_hash = security.hash_password(new)
    user.password_changed_at = utcnow()
    revoked = revoke_sessions(db, user.id, except_session_id=auth.session.id)
    audit.record(
        db,
        action=AuditAction.PASSWORD_CHANGED,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        summary=f"Password changed; {revoked} other session(s) signed out",
        meta=meta,
    )
    db.commit()


def _issue_user_token(db: Session, user: User, purpose: TokenPurpose, lifetime: timedelta) -> str:
    # Invalidate earlier unused tokens for the same purpose.
    db.execute(
        update(UserToken)
        .where(UserToken.user_id == user.id, UserToken.purpose == purpose.value, UserToken.used_at.is_(None))
        .values(used_at=utcnow())
    )
    token = security.generate_token()
    db.add(
        UserToken(
            user_id=user.id,
            purpose=purpose.value,
            token_hash=security.hash_token(token),
            expires_at=utcnow() + lifetime,
        )
    )
    return token


def _consume_user_token(db: Session, token: str, purpose: TokenPurpose, *, mark_used: bool) -> UserToken:
    row = db.scalar(
        select(UserToken)
        .where(
            UserToken.token_hash == security.hash_token(token.strip()),
            UserToken.purpose == purpose.value,
        )
        .with_for_update()
    )
    if row is None or row.used_at is not None or row.expires_at <= utcnow() or not row.user.is_active:
        raise InvalidTokenError("This link is invalid or has expired. Request a new one.")
    if mark_used:
        row.used_at = utcnow()
    return row


def request_password_reset(db: Session, email: str, meta: RequestMeta) -> tuple[User, str] | None:
    """Returns (user, token) when a reset e-mail should be sent. Callers must not reveal the outcome."""
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or not user.is_active or user.password_hash is None:
        return None
    token = _issue_user_token(
        db, user, TokenPurpose.PASSWORD_RESET, timedelta(minutes=get_settings().password_reset_minutes)
    )
    audit.record(
        db,
        action=AuditAction.PASSWORD_RESET_REQUESTED,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        summary="Password reset requested",
        meta=meta,
    )
    db.commit()
    return user, token


def reset_password(db: Session, token: str, new_password: str, meta: RequestMeta) -> None:
    row = _consume_user_token(db, token, TokenPurpose.PASSWORD_RESET, mark_used=False)
    user = row.user
    validate_new_password(new_password, user, field="new_password")
    row.used_at = utcnow()
    user.password_hash = security.hash_password(new_password)
    user.password_changed_at = utcnow()
    user.failed_login_count = 0
    user.locked_until = None
    revoke_sessions(db, user.id)
    audit.record(
        db,
        action=AuditAction.PASSWORD_RESET,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        summary="Password reset via e-mail link; all sessions signed out",
        meta=meta,
    )
    db.commit()


# ---------------------------------------------------------------- invitations


def issue_invitation(db: Session, user: User) -> str:
    """Create an invitation token (caller commits and e-mails it)."""
    return _issue_user_token(
        db, user, TokenPurpose.INVITATION, timedelta(hours=get_settings().invitation_hours)
    )


def inspect_invitation(db: Session, token: str) -> User:
    row = _consume_user_token(db, token, TokenPurpose.INVITATION, mark_used=False)
    user = row.user
    db.rollback()  # release the row lock; nothing changed
    if user.password_hash is not None:
        raise InvalidTokenError("This invitation has already been accepted. Sign in instead.")
    return user


def accept_invitation(db: Session, token: str, password: str, meta: RequestMeta) -> User:
    row = _consume_user_token(db, token, TokenPurpose.INVITATION, mark_used=False)
    user = row.user
    if user.password_hash is not None:
        raise InvalidTokenError("This invitation has already been accepted. Sign in instead.")
    validate_new_password(password, user, field="password")
    row.used_at = utcnow()
    user.password_hash = security.hash_password(password)
    user.password_changed_at = utcnow()
    audit.record(
        db,
        action=AuditAction.INVITATION_ACCEPTED,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        summary="Invitation accepted and password set",
        meta=meta,
    )
    db.commit()
    return user

"""FastAPI dependencies for authentication, CSRF protection and permission checks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.security import hash_token, tokens_equal
from app.core.config import get_settings
from app.core.errors import AppError, PermissionDeniedError
from app.db.session import get_db
from app.models import User, UserSession
from app.permissions.matrix import Permission, Scope, is_staff, scope_of

SESSION_COOKIE = "crm_session"
CSRF_COOKIE = "crm_csrf"
CSRF_HEADER = "X-CSRF-Token"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# last_seen_at is written at most this often per session.
_TOUCH_INTERVAL = timedelta(seconds=60)

DbSession = Annotated[Session, Depends(get_db)]


class NotAuthenticatedError(AppError):
    status_code = 401
    code = "unauthenticated"


class MfaRequiredError(AppError):
    status_code = 403
    code = "mfa_required"


class CsrfError(AppError):
    status_code = 403
    code = "csrf_failed"


@dataclass
class AuthContext:
    user: User
    session: UserSession

    @property
    def role(self) -> str:
        return self.user.role

    @property
    def is_staff(self) -> bool:
        return is_staff(self.user.role)

    def scope(self, permission: Permission) -> Scope | None:
        return scope_of(self.user.role, permission)

    def can(self, permission: Permission) -> bool:
        return self.scope(permission) is not None


def utcnow() -> datetime:
    return datetime.now(UTC)


def mfa_setup_required(user: User) -> bool:
    return not user.mfa_enabled and is_staff(user.role) and get_settings().mfa_required_for_staff


def verify_origin(request: Request) -> None:
    """Reject cross-site unsafe requests whose Origin is not ours (defence in depth with SameSite + CSRF)."""
    if request.method not in UNSAFE_METHODS:
        return
    origin = request.headers.get("origin")
    if origin is None:  # non-browser clients; browsers always send Origin on unsafe requests
        return
    if origin.rstrip("/") not in get_settings().allowed_origins:
        raise CsrfError("Request origin is not allowed.")


def get_optional_auth(request: Request, db: DbSession) -> AuthContext | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    session = db.scalar(
        select(UserSession)
        .options(joinedload(UserSession.user))
        .where(UserSession.token_hash == hash_token(token))
    )
    if session is None:
        return None

    settings = get_settings()
    now = utcnow()
    idle_limit = session.last_seen_at + timedelta(minutes=settings.session_idle_minutes)
    if session.expires_at <= now or idle_limit <= now or not session.user.is_active:
        db.delete(session)
        db.commit()
        return None

    if request.method in UNSAFE_METHODS:
        header = request.headers.get(CSRF_HEADER, "")
        if not header or not tokens_equal(hash_token(header), session.csrf_token_hash):
            raise CsrfError("Missing or invalid CSRF token. Refresh the page and try again.")

    if now - session.last_seen_at >= _TOUCH_INTERVAL:
        session.last_seen_at = now
        db.commit()
    return AuthContext(user=session.user, session=session)


OptionalAuth = Annotated[AuthContext | None, Depends(get_optional_auth)]


def get_auth_any(auth: OptionalAuth) -> AuthContext:
    """Any valid session, including one still waiting for MFA."""
    if auth is None:
        raise NotAuthenticatedError("Please sign in.")
    return auth


AnyAuth = Annotated[AuthContext, Depends(get_auth_any)]


def get_auth(auth: AnyAuth) -> AuthContext:
    """A fully authenticated session (MFA completed where required)."""
    if not auth.session.mfa_verified:
        raise MfaRequiredError("Complete multi-factor authentication to continue.")
    return auth


Auth = Annotated[AuthContext, Depends(get_auth)]


def require(permission: Permission) -> Callable[[AuthContext], AuthContext]:
    """Dependency factory: fully authenticated user holding `permission` (any scope)."""

    def dependency(auth: Auth) -> AuthContext:
        if not auth.can(permission):
            raise PermissionDeniedError("You do not have permission to perform this action.")
        return auth

    dependency.__name__ = f"require_{permission.value.replace('.', '_')}"
    return dependency


def require_staff(auth: Auth) -> AuthContext:
    if not auth.is_staff:
        raise PermissionDeniedError("This area is for staff only.")
    return auth


StaffAuth = Annotated[AuthContext, Depends(require_staff)]

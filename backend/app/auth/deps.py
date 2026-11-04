"""FastAPI dependencies for authentication, CSRF protection and permission checks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.security import hash_token, tokens_equal
from app.core.cache import set_revisions
from app.core.config import get_settings
from app.core.errors import AppError, PermissionDeniedError
from app.db.session import get_db
from app.models import MetadataRevision, User, UserSession
from app.security.catalog import SystemPermission
from app.security.policy import AccessPolicy, load_policy
from app.tenancy import SESSION_COOKIE as SESSION_COOKIE
from app.tenancy import is_resolved, split_token

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
    db: Session | None = None
    _policy: AccessPolicy | None = field(default=None, repr=False)

    @property
    def is_staff(self) -> bool:
        return not self.user.profile.is_portal

    @property
    def policy(self) -> AccessPolicy:
        """Effective permissions, loaded once per request."""
        if self._policy is None:
            if self.db is None:
                raise RuntimeError("AuthContext has no database session to load permissions")
            self._policy = load_policy(self.db, self.user)
        return self._policy

    def has(self, permission: SystemPermission) -> bool:
        return self.policy.has(permission)


def utcnow() -> datetime:
    return datetime.now(UTC)


def mfa_setup_required(user: User) -> bool:
    return not user.mfa_enabled and not user.profile.is_portal and get_settings().mfa_required_for_staff


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
    cookie = request.cookies.get(SESSION_COOKIE)
    if not cookie or not is_resolved(db):
        return None
    # "<tenant>.<token>": get_db already bound the session to the tenant named by the prefix.
    _, token = split_token(cookie)
    # One round trip: the session with its user, profile and role, plus the metadata/security revisions
    # that key the in-memory caches (app.core.cache).
    row = db.execute(
        select(UserSession, MetadataRevision.revision, MetadataRevision.security)
        .options(joinedload(UserSession.user))
        .outerjoin(MetadataRevision, MetadataRevision.id == 1)
        .where(UserSession.token_hash == hash_token(token))
    ).first()
    if row is None:
        return None
    session, metadata_revision, security_revision = row
    set_revisions(db, metadata_revision, security_revision)

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
    return AuthContext(user=session.user, session=session, db=db)


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


def require_staff(auth: Auth) -> AuthContext:
    if not auth.is_staff:
        raise PermissionDeniedError("This area is for staff only.")
    return auth


StaffAuth = Annotated[AuthContext, Depends(require_staff)]


def require(*permissions: SystemPermission) -> Callable[[AuthContext], AuthContext]:
    """Dependency factory: a fully authenticated staff user holding ANY of `permissions`."""
    if not permissions:
        raise ValueError("require() needs at least one permission")

    def dependency(auth: StaffAuth) -> AuthContext:
        if not any(auth.has(p) for p in permissions):
            raise PermissionDeniedError("You do not have permission to perform this action.")
        return auth

    dependency.__name__ = "require_" + "_or_".join(p.value for p in permissions)
    return dependency

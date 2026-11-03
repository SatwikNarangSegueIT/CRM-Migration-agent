"""User administration (user.manage)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.deps import AuthContext
from app.core.errors import AppError, ConflictError, NotFoundError
from app.db.session import escape_like
from app.models import RecoveryCode, User
from app.permissions.matrix import Role
from app.schemas.common import PageParams
from app.schemas.users import UserCreate, UserUpdate
from app.services import audit
from app.services.audit import AuditAction, RequestMeta
from app.services.auth import issue_invitation, revoke_sessions

_AUDITED_FIELDS = ("email", "name", "role", "title", "phone", "mara_number", "is_active")


def _snapshot(user: User) -> dict[str, Any]:
    return {f: getattr(user, f) for f in _AUDITED_FIELDS}


def get_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    return user


def list_users(
    db: Session, params: PageParams, *, q: str | None, role: Role | None, is_active: bool | None
) -> tuple[list[User], int]:
    stmt = select(User)
    if q:
        pattern = f"%{escape_like(q.strip().lower())}%"
        stmt = stmt.where(
            or_(func.lower(User.name).like(pattern, escape="\\"), User.email.like(pattern, escape="\\"))
        )
    if role is not None:
        stmt = stmt.where(User.role == role.value)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.scalars(
        stmt.order_by(func.lower(User.name), User.email).offset(params.offset).limit(params.page_size)
    )
    return list(rows), total


def _active_admin_count(db: Session, *, excluding: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == Role.ADMIN.value, User.is_active.is_(True), User.id != excluding)
        )
        or 0
    )


def create_user(db: Session, actor: AuthContext, data: UserCreate, meta: RequestMeta) -> tuple[User, str]:
    if data.role is Role.CLIENT:
        raise AppError(
            "Client accounts are created by inviting a contact to the client portal.",
            code="invalid_role",
            status_code=422,
            fields={"role": "Not allowed here"},
        )
    email = str(data.email).strip().lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise ConflictError("A user with this e-mail already exists.", fields={"email": "Already in use"})
    user = User(
        email=email,
        name=data.name,
        role=data.role.value,
        title=data.title or None,
        phone=data.phone or None,
        mara_number=data.mara_number or None,
        is_active=True,
    )
    db.add(user)
    db.flush()
    token = issue_invitation(db, user)
    audit.record(
        db,
        action=AuditAction.CREATE,
        entity_type="user",
        entity_id=user.id,
        actor_id=actor.user.id,
        summary=f"Created user {user.email} ({user.role}) and sent invitation",
        changes=audit.diff({}, _snapshot(user)),
        meta=meta,
    )
    db.commit()
    return user, token


def update_user(
    db: Session, actor: AuthContext, user_id: uuid.UUID, data: UserUpdate, meta: RequestMeta
) -> User:
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise NotFoundError("User not found.")
    if user.updated_at != data.updated_at:
        raise ConflictError(
            "This user was changed by someone else. Reload and try again.", fields={"updated_at": "Stale"}
        )
    fields = data.model_fields_set - {"updated_at"}
    before = _snapshot(user)
    is_self = user.id == actor.user.id

    if "role" in fields and data.role is not None and data.role.value != user.role:
        if is_self:
            raise AppError(
                "You cannot change your own role.",
                code="forbidden_self_change",
                status_code=422,
                fields={"role": "Cannot change own role"},
            )
        if data.role is Role.CLIENT or user.role == Role.CLIENT.value:
            raise AppError(
                "Staff and client accounts cannot be converted.",
                code="invalid_role",
                status_code=422,
                fields={"role": "Not allowed"},
            )
        if (
            user.role == Role.ADMIN.value
            and user.is_active
            and _active_admin_count(db, excluding=user.id) == 0
        ):
            raise AppError(
                "At least one active administrator is required.",
                code="last_admin",
                status_code=422,
                fields={"role": "Last active administrator"},
            )
        user.role = data.role.value

    if "is_active" in fields and data.is_active is not None and data.is_active != user.is_active:
        if is_self:
            raise AppError(
                "You cannot deactivate your own account.",
                code="forbidden_self_change",
                status_code=422,
                fields={"is_active": "Cannot deactivate yourself"},
            )
        if (
            not data.is_active
            and user.role == Role.ADMIN.value
            and _active_admin_count(db, excluding=user.id) == 0
        ):
            raise AppError(
                "At least one active administrator is required.",
                code="last_admin",
                status_code=422,
                fields={"is_active": "Last active administrator"},
            )
        user.is_active = data.is_active

    if "name" in fields and data.name is not None:
        user.name = data.name
    for optional in ("title", "phone", "mara_number"):
        if optional in fields:
            setattr(user, optional, getattr(data, optional) or None)

    changes = audit.diff(before, _snapshot(user))
    if not changes:
        return user
    # Role or status changes take effect immediately: sign the user out everywhere.
    if "role" in changes or "is_active" in changes:
        revoke_sessions(db, user.id)
    audit.record(
        db,
        action=AuditAction.UPDATE,
        entity_type="user",
        entity_id=user.id,
        actor_id=actor.user.id,
        summary=f"Updated user {user.email}",
        changes=changes,
        meta=meta,
    )
    db.commit()
    db.refresh(user)
    return user


def resend_invitation(
    db: Session, actor: AuthContext, user_id: uuid.UUID, meta: RequestMeta
) -> tuple[User, str]:
    user = get_user(db, user_id)
    if user.password_hash is not None:
        raise AppError(
            "This user has already accepted the invitation.", code="invitation_accepted", status_code=409
        )
    if not user.is_active:
        raise AppError(
            "Activate the user before sending an invitation.", code="user_inactive", status_code=409
        )
    token = issue_invitation(db, user)
    audit.record(
        db,
        action=AuditAction.INVITATION_SENT,
        entity_type="user",
        entity_id=user.id,
        actor_id=actor.user.id,
        summary=f"Invitation re-sent to {user.email}",
        meta=meta,
    )
    db.commit()
    return user, token


def reset_mfa(db: Session, actor: AuthContext, user_id: uuid.UUID, meta: RequestMeta) -> User:
    user = get_user(db, user_id)
    user.mfa_enabled = False
    user.mfa_secret_encrypted = None
    user.mfa_last_used_step = None
    db.query(RecoveryCode).filter(RecoveryCode.user_id == user.id).delete()
    revoke_sessions(db, user.id)
    audit.record(
        db,
        action=AuditAction.MFA_RESET,
        entity_type="user",
        entity_id=user.id,
        actor_id=actor.user.id,
        summary=f"MFA reset for {user.email}; user must enrol again at next sign-in",
        meta=meta,
    )
    db.commit()
    return user


def unlock(db: Session, actor: AuthContext, user_id: uuid.UUID, meta: RequestMeta) -> User:
    user = get_user(db, user_id)
    user.locked_until = None
    user.failed_login_count = 0
    audit.record(
        db,
        action=AuditAction.UNLOCK,
        entity_type="user",
        entity_id=user.id,
        actor_id=actor.user.id,
        summary=f"Unlocked {user.email}",
        meta=meta,
    )
    db.commit()
    return user


def revoke_all_sessions(db: Session, actor: AuthContext, user_id: uuid.UUID, meta: RequestMeta) -> int:
    user = get_user(db, user_id)
    count = revoke_sessions(db, user.id)
    audit.record(
        db,
        action=AuditAction.SESSIONS_REVOKED,
        entity_type="user",
        entity_id=user.id,
        actor_id=actor.user.id,
        summary=f"Signed out {count} session(s) of {user.email}",
        meta=meta,
    )
    db.commit()
    return count

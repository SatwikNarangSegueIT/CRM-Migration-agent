"""User administration (user.manage)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.auth.deps import AuthContext
from app.core.errors import AppError, ConflictError, NotFoundError
from app.db.session import escape_like
from app.models import (
    DELETED_EMAIL_DOMAIN,
    Dashboard,
    GroupMember,
    Profile,
    QueueMember,
    Record,
    RecordShare,
    RecoveryCode,
    Report,
    ReportFolder,
    ReportSchedule,
    Role,
    User,
    UserToken,
)
from app.schemas.common import PageParams
from app.schemas.users import UserCreate, UserUpdate
from app.security.policy import SYSTEM_ADMIN_KEY
from app.services import audit
from app.services.audit import AuditAction, RequestMeta
from app.services.auth import issue_invitation, revoke_sessions

_AUDITED_FIELDS = ("email", "name", "profile_id", "role_id", "title", "phone", "mara_number", "is_active")


def _snapshot(user: User) -> dict[str, Any]:
    return {f: getattr(user, f) for f in _AUDITED_FIELDS}


def get_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None or user.is_deleted:
        raise NotFoundError("User not found.")
    return user


def list_users(
    db: Session,
    params: PageParams,
    *,
    q: str | None,
    profile_id: uuid.UUID | None,
    role_id: uuid.UUID | None,
    is_active: bool | None,
) -> tuple[list[User], int]:
    stmt = select(User).where(not_deleted())
    if q:
        pattern = f"%{escape_like(q.strip().lower())}%"
        stmt = stmt.where(
            or_(func.lower(User.name).like(pattern, escape="\\"), User.email.like(pattern, escape="\\"))
        )
    if profile_id is not None:
        stmt = stmt.where(User.profile_id == profile_id)
    if role_id is not None:
        stmt = stmt.where(User.role_id == role_id)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    rows = db.scalars(
        stmt.order_by(func.lower(User.name), User.email).offset(params.offset).limit(params.page_size)
    )
    return list(rows), total


def not_deleted() -> Any:
    """SQL condition: the user hasn't been deleted (see delete_user)."""
    return User.email.not_like(f"%@{DELETED_EMAIL_DOMAIN}")


def _active_admin_count(db: Session, *, excluding: uuid.UUID) -> int:
    """Active users holding the System Administrator profile, other than `excluding`."""
    return int(
        db.scalar(
            select(func.count())
            .select_from(User)
            .join(Profile, Profile.id == User.profile_id)
            .where(Profile.key == SYSTEM_ADMIN_KEY, User.is_active.is_(True), User.id != excluding)
        )
        or 0
    )


def _staff_profile(db: Session, profile_id: uuid.UUID) -> Profile:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise AppError(
            "Profile not found.",
            code="invalid_profile",
            status_code=422,
            fields={"profile_id": "Unknown profile"},
        )
    if profile.is_portal:
        raise AppError(
            "Portal users are created by inviting a contact to the customer portal.",
            code="invalid_profile",
            status_code=422,
            fields={"profile_id": "Portal profiles are not allowed here"},
        )
    return profile


def _role(db: Session, role_id: uuid.UUID) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise AppError(
            "Role not found.", code="invalid_role", status_code=422, fields={"role_id": "Unknown role"}
        )
    return role


def _last_admin_error(field: str) -> AppError:
    return AppError(
        "At least one active System Administrator is required.",
        code="last_admin",
        status_code=422,
        fields={field: "Last active System Administrator"},
    )


def _self_change_error(field: str, message: str) -> AppError:
    return AppError(message, code="forbidden_self_change", status_code=422, fields={field: message})


def _check_registration(db: Session, value: str | None) -> None:
    from app.domain_content import registration_number_error
    from app.services.settings import get_setting

    domain = (get_setting(db, "workspace") or {}).get("domain")
    message = registration_number_error(domain, value)
    if message:
        raise AppError(message, status_code=422, fields={"mara_number": message})


def create_user(db: Session, actor: AuthContext, data: UserCreate, meta: RequestMeta) -> tuple[User, str]:
    profile = _staff_profile(db, data.profile_id)
    _check_registration(db, data.mara_number)
    role = _role(db, data.role_id) if data.role_id is not None else None
    email = str(data.email).strip().lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise ConflictError("A user with this e-mail already exists.", fields={"email": "Already in use"})
    user = User(
        email=email,
        name=data.name,
        profile_id=profile.id,
        role_id=role.id if role else None,
        title=data.title,
        phone=data.phone,
        mara_number=data.mara_number,
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
        summary=f"Created user {user.email} (profile {profile.name}) and sent invitation",
        changes=audit.diff({}, _snapshot(user)),
        meta=meta,
    )
    db.commit()
    db.refresh(user)
    return user, token


def update_user(
    db: Session, actor: AuthContext, user_id: uuid.UUID, data: UserUpdate, meta: RequestMeta
) -> User:
    user = db.scalar(select(User).where(User.id == user_id).with_for_update(of=User))
    if user is None:
        raise NotFoundError("User not found.")
    if user.updated_at != data.updated_at:
        raise ConflictError(
            "This user was changed by someone else. Reload and try again.", fields={"updated_at": "Stale"}
        )
    fields = data.model_fields_set - {"updated_at"}
    before = _snapshot(user)
    is_self = user.id == actor.user.id
    is_admin = user.profile.key == SYSTEM_ADMIN_KEY

    if "profile_id" in fields and data.profile_id is not None and data.profile_id != user.profile_id:
        if is_self:
            raise _self_change_error("profile_id", "You cannot change your own profile.")
        if user.profile.is_portal:
            raise AppError(
                "Portal users cannot be given a staff profile.",
                code="invalid_profile",
                status_code=422,
                fields={"profile_id": "Not allowed"},
            )
        new_profile = _staff_profile(db, data.profile_id)
        if (
            is_admin
            and new_profile.key != SYSTEM_ADMIN_KEY
            and user.is_active
            and (_active_admin_count(db, excluding=user.id) == 0)
        ):
            raise _last_admin_error("profile_id")
        user.profile_id = new_profile.id

    if "role_id" in fields and data.role_id != user.role_id:
        if is_self:
            raise _self_change_error("role_id", "You cannot change your own role.")
        user.role_id = _role(db, data.role_id).id if data.role_id is not None else None

    if "is_active" in fields and data.is_active is not None and data.is_active != user.is_active:
        if is_self:
            raise _self_change_error("is_active", "You cannot deactivate your own account.")
        if not data.is_active and is_admin and _active_admin_count(db, excluding=user.id) == 0:
            raise _last_admin_error("is_active")
        user.is_active = data.is_active

    if "name" in fields and data.name is not None:
        user.name = data.name
    if "mara_number" in fields:
        _check_registration(db, data.mara_number)
    for optional in ("title", "phone", "mara_number"):
        if optional in fields:
            setattr(user, optional, getattr(data, optional))

    changes = audit.diff(before, _snapshot(user))
    if not changes:
        return user
    user.updated_at = func.now()
    # Access changes take effect immediately: sign the user out everywhere.
    if {"profile_id", "role_id", "is_active"} & changes.keys():
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
    db.expire(user)
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


def delete_user(
    db: Session,
    actor: AuthContext,
    user_id: uuid.UUID,
    meta: RequestMeta,
    *,
    transfer_to: uuid.UUID | None = None,
) -> User:
    """Delete a staff or portal user.

    The row stays, because audit entries and old records name the person, but everything else goes: their
    records, reports and dashboards move to ``transfer_to`` (default: the administrator deleting them),
    their sign-ins, tokens, MFA, group and queue memberships and record shares are removed, and the
    e-mail address is released so the same person can be added again (e.g. as a client instead).
    """
    user = db.scalar(select(User).where(User.id == user_id).with_for_update(of=User))
    if user is None or user.is_deleted:
        raise NotFoundError("User not found.")
    if user.id == actor.user.id:
        raise AppError("You cannot delete your own account.", status_code=422, code="self_delete")
    if (
        user.is_active
        and user.profile.key == SYSTEM_ADMIN_KEY
        and _active_admin_count(db, excluding=user.id) == 0
    ):
        raise _last_admin_error("user")
    heir_id = transfer_to or actor.user.id
    if heir_id == user.id:
        raise AppError("Choose someone else to take over their records.", status_code=422)
    heir = db.get(User, heir_id)
    if heir is None or not heir.is_active or heir.is_deleted or heir.profile.is_portal:
        raise AppError(
            "Records can only be transferred to an active staff member.",
            status_code=422,
            fields={"transfer_to": "Choose an active staff member"},
        )

    moved = int(db.scalar(select(func.count()).select_from(Record).where(Record.owner_id == user.id)) or 0)
    db.execute(update(Record).where(Record.owner_id == user.id).values(owner_id=heir.id))
    for model in (ReportFolder, Report, Dashboard, ReportSchedule):
        db.execute(update(model).where(model.owner_id == user.id).values(owner_id=heir.id))
    db.execute(update(Dashboard).where(Dashboard.running_user_id == user.id).values(running_user_id=heir.id))
    db.execute(delete(GroupMember).where(GroupMember.user_id == user.id))
    db.execute(delete(QueueMember).where(QueueMember.user_id == user.id))
    db.execute(
        delete(RecordShare).where(RecordShare.principal_type == "user", RecordShare.principal_id == user.id)
    )
    db.execute(delete(UserToken).where(UserToken.user_id == user.id))
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    revoke_sessions(db, user.id)

    old_email, old_name = user.email, user.name
    user.email = f"deleted-{user.id.hex}@{DELETED_EMAIL_DOMAIN}"
    user.name = f"{old_name} (deleted)"[:120]
    user.is_active = False
    user.password_hash = None
    user.mfa_enabled = False
    user.mfa_secret_encrypted = None
    user.contact_id = None
    user.role_id = None
    user.phone = None
    user.updated_at = func.now()
    audit.record(
        db,
        action=AuditAction.DELETE,
        entity_type="user",
        entity_id=user.id,
        actor_id=actor.user.id,
        summary=f"Deleted user {old_name} <{old_email}>; {moved} record(s) transferred to {heir.name}",
        changes={"email": {"from": old_email, "to": None}, "is_active": {"from": True, "to": False}},
        meta=meta,
    )
    db.commit()
    return user

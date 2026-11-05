"""Setup: profiles, permissions, role hierarchy, sharing defaults, groups, queues, sharing rules.

Every change is audited and committed by the function that makes it.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.auth.deps import AuthContext
from app.core.errors import AppError, ConflictError, NotFoundError
from app.models import (
    Group,
    GroupMember,
    Profile,
    ProfileFieldPermission,
    ProfileObjectPermission,
    ProfileSystemPermission,
    Queue,
    QueueMember,
    Role,
    SharingDefault,
    SharingRule,
    User,
)
from app.schemas.setup import (
    FieldPermissionsIn,
    GroupIn,
    GroupMembersIn,
    ObjectPermissionIn,
    ObjectPermissionsIn,
    ProfileCreate,
    ProfileUpdate,
    QueueIn,
    QueueMembersIn,
    RoleCreate,
    RoleUpdate,
    SharingDefaultIn,
    SharingRuleIn,
)
from app.security.catalog import STANDARD_OBJECT_NAMES, STANDARD_OBJECTS, SharingAccess, SystemPermission
from app.services import audit
from app.services.audit import AuditAction, RequestMeta

_DEFAULT_SHARING = {o.api_name: o.sharing for o in STANDARD_OBJECTS}


def _invalid(message: str, field: str, code: str = "invalid") -> AppError:
    return AppError(message, code=code, status_code=422, fields={field: message})


def known_objects(db: Session) -> set[str]:
    """Standard catalog objects (including reports/dashboards) plus every object in the metadata engine."""
    from app.models import ObjectDefinition

    return set(STANDARD_OBJECT_NAMES) | set(db.scalars(select(ObjectDefinition.api_name)))


def ensure_known_object(db: Session, api_name: str, field: str = "object_api_name") -> None:
    if api_name not in known_objects(db):
        raise _invalid(f"Unknown object '{api_name}'.", field, "unknown_object")


def ensure_known_field(db: Session, object_api: str, field_api: str, field: str = "fields") -> None:
    from app.engine.meta import load_registry

    meta = load_registry(db).objects.get(object_api)
    if meta is not None and field_api not in meta.fields:
        raise _invalid(f"Unknown field '{object_api}.{field_api}'.", field, "unknown_field")


def _record(
    db: Session,
    actor: AuthContext,
    action: AuditAction,
    entity_type: str,
    entity_id: Any,
    summary: str,
    meta: RequestMeta,
    changes: dict[str, Any] | None = None,
) -> None:
    audit.record(
        db,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor.user.id,
        summary=summary,
        changes=changes,
        meta=meta,
    )


# ================================================================ profiles


def user_counts_by_profile(db: Session) -> dict[uuid.UUID, int]:
    rows = db.execute(select(User.profile_id, func.count()).group_by(User.profile_id))
    return {pid: int(n) for pid, n in rows}


# Kept in every workspace: the administrator and the client portal profile.
_ALWAYS_SHOWN = {"system_administrator", "customer_portal"}


def list_profiles(db: Session) -> list[Profile]:
    """Every profile; in a profession workspace, the general CRM's own profiles (Sales Manager, Marketing
    User, Finance...) are left out unless someone is assigned one. They aren't deleted: the profession's
    profiles were copied from them."""
    from app.security.seed_v1 import PROFILES
    from app.services.settings import get_setting

    profiles = list(db.scalars(select(Profile).order_by(Profile.is_portal, func.lower(Profile.name))))
    if not (get_setting(db, "workspace") or {}).get("domain"):
        return profiles
    generic = {key for key, *_ in PROFILES} - _ALWAYS_SHOWN
    in_use = user_counts_by_profile(db)
    return [p for p in profiles if p.key not in generic or in_use.get(p.id)]


def get_profile(db: Session, profile_id: uuid.UUID) -> Profile:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise NotFoundError("Profile not found.")
    return profile


def _editable_profile(db: Session, profile_id: uuid.UUID) -> Profile:
    profile = get_profile(db, profile_id)
    if profile.is_locked:
        raise AppError(
            "The System Administrator profile cannot be changed.", code="profile_locked", status_code=409
        )
    return profile


def _name_taken(db: Session, model: Any, name: str, exclude_id: uuid.UUID | None = None) -> bool:
    stmt = select(model.id).where(func.lower(model.name) == name.lower())
    if exclude_id is not None:
        stmt = stmt.where(model.id != exclude_id)
    return db.scalar(stmt) is not None


def create_profile(db: Session, actor: AuthContext, data: ProfileCreate, meta: RequestMeta) -> Profile:
    if _name_taken(db, Profile, data.name):
        raise ConflictError("A profile with this name already exists.", fields={"name": "Already in use"})
    source = get_profile(db, data.clone_from_id) if data.clone_from_id else None
    if source is not None and source.is_locked:
        raise _invalid("The System Administrator profile cannot be cloned.", "clone_from_id")
    profile = Profile(
        name=data.name,
        description=data.description,
        is_portal=source.is_portal if source else data.is_portal,
    )
    db.add(profile)
    db.flush()
    if source is not None:
        for sp in source.system_permissions:
            db.add(ProfileSystemPermission(profile_id=profile.id, permission=sp.permission))
        for op in source.object_permissions:
            db.add(
                ProfileObjectPermission(
                    profile_id=profile.id,
                    object_api_name=op.object_api_name,
                    can_read=op.can_read,
                    can_create=op.can_create,
                    can_edit=op.can_edit,
                    can_delete=op.can_delete,
                    view_all=op.view_all,
                    modify_all=op.modify_all,
                )
            )
        for fp in source.field_permissions:
            db.add(
                ProfileFieldPermission(
                    profile_id=profile.id,
                    object_api_name=fp.object_api_name,
                    field_api_name=fp.field_api_name,
                    access=fp.access,
                )
            )
    _record(
        db,
        actor,
        AuditAction.CREATE,
        "profile",
        profile.id,
        f"Created profile {profile.name}" + (f" (cloned from {source.name})" if source else ""),
        meta,
    )
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(
    db: Session, actor: AuthContext, profile_id: uuid.UUID, data: ProfileUpdate, meta: RequestMeta
) -> Profile:
    profile = _editable_profile(db, profile_id)
    before = {"name": profile.name, "description": profile.description}
    fields = data.model_fields_set
    if "name" in fields and data.name is not None:
        if _name_taken(db, Profile, data.name, profile.id):
            raise ConflictError("A profile with this name already exists.", fields={"name": "Already in use"})
        profile.name = data.name
    if "description" in fields:
        profile.description = data.description
    changes = audit.diff(before, {"name": profile.name, "description": profile.description})
    if changes:
        _record(
            db,
            actor,
            AuditAction.UPDATE,
            "profile",
            profile.id,
            f"Updated profile {profile.name}",
            meta,
            changes,
        )
        db.commit()
    return profile


def delete_profile(db: Session, actor: AuthContext, profile_id: uuid.UUID, meta: RequestMeta) -> None:
    profile = _editable_profile(db, profile_id)
    if profile.key is not None:
        raise AppError(
            "Standard profiles cannot be deleted; clone and edit them instead.",
            code="profile_standard",
            status_code=409,
        )
    if db.scalar(select(func.count()).select_from(User).where(User.profile_id == profile.id)):
        raise ConflictError("Reassign this profile's users before deleting it.")
    _record(db, actor, AuditAction.DELETE, "profile", profile.id, f"Deleted profile {profile.name}", meta)
    db.delete(profile)
    db.commit()


def _profile_user_ids(db: Session, profile_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(select(User.id).where(User.profile_id == profile_id)))


def set_system_permissions(
    db: Session,
    actor: AuthContext,
    profile_id: uuid.UUID,
    permissions: list[SystemPermission],
    meta: RequestMeta,
) -> Profile:
    profile = _editable_profile(db, profile_id)
    wanted = {p.value for p in permissions}
    if profile.is_portal and wanted:
        raise _invalid("Portal profiles cannot hold system permissions.", "permissions")
    current = {sp.permission for sp in profile.system_permissions}
    if wanted == current:
        return profile
    db.execute(delete(ProfileSystemPermission).where(ProfileSystemPermission.profile_id == profile.id))
    db.add_all(ProfileSystemPermission(profile_id=profile.id, permission=p) for p in sorted(wanted))
    _record(
        db,
        actor,
        AuditAction.UPDATE,
        "profile",
        profile.id,
        f"Changed system permissions of profile {profile.name}",
        meta,
        {"system_permissions": {"from": sorted(current), "to": sorted(wanted)}},
    )
    db.commit()
    db.expire(profile)
    return profile


def _check_object_permission(api: str, perm: ObjectPermissionIn, is_portal: bool) -> None:
    field = f"objects.{api}"
    if (perm.create or perm.edit or perm.delete or perm.view_all or perm.modify_all) and not perm.read:
        raise _invalid("Create, edit, delete and view all require read.", field)
    if perm.modify_all and not (perm.view_all and perm.edit):
        raise _invalid("Modify all requires view all and edit.", field)
    if is_portal and (perm.delete or perm.view_all or perm.modify_all):
        raise _invalid("Portal profiles may only read, create and edit their own records.", field)


def set_object_permissions(
    db: Session, actor: AuthContext, profile_id: uuid.UUID, data: ObjectPermissionsIn, meta: RequestMeta
) -> Profile:
    profile = _editable_profile(db, profile_id)
    existing = {op.object_api_name: op for op in profile.object_permissions}
    changes: dict[str, Any] = {}
    for api, perm in sorted(data.objects.items()):
        ensure_known_object(db, api, f"objects.{api}")
        _check_object_permission(api, perm, profile.is_portal)
        row = existing.get(api)
        old = _perm_code(row) if row else "-"
        new_flags = {
            "can_read": perm.read,
            "can_create": perm.create,
            "can_edit": perm.edit,
            "can_delete": perm.delete,
            "view_all": perm.view_all,
            "modify_all": perm.modify_all,
        }
        if not perm.read:
            if row is not None:
                db.delete(row)
        elif row is None:
            row = ProfileObjectPermission(profile_id=profile.id, object_api_name=api, **new_flags)
            db.add(row)
        else:
            for k, v in new_flags.items():
                setattr(row, k, v)
        new = _perm_code_flags(new_flags) if perm.read else "-"
        if old != new:
            changes[api] = {"from": old, "to": new}
    if changes:
        _record(
            db,
            actor,
            AuditAction.UPDATE,
            "profile",
            profile.id,
            f"Changed object permissions of profile {profile.name}",
            meta,
            changes,
        )
        db.commit()
        db.expire(profile)
    return profile


def _perm_code_flags(f: dict[str, bool]) -> str:
    letters = "".join(
        c for c, k in zip("RCED", ("can_read", "can_create", "can_edit", "can_delete"), strict=True) if f[k]
    )
    extra = [t for t, k in (("VA", "view_all"), ("MA", "modify_all")) if f[k]]
    return " ".join([letters, *extra]).strip() or "-"


def _perm_code(row: ProfileObjectPermission) -> str:
    return _perm_code_flags(
        {
            k: getattr(row, k)
            for k in ("can_read", "can_create", "can_edit", "can_delete", "view_all", "modify_all")
        }
    )


def set_field_permissions(
    db: Session, actor: AuthContext, profile_id: uuid.UUID, data: FieldPermissionsIn, meta: RequestMeta
) -> Profile:
    profile = _editable_profile(db, profile_id)
    existing = {(fp.object_api_name, fp.field_api_name): fp for fp in profile.field_permissions}
    changes: dict[str, Any] = {}
    for item in data.fields:
        ensure_known_object(db, item.object_api_name, "fields")
        ensure_known_field(db, item.object_api_name, item.field_api_name)
        key = (item.object_api_name, item.field_api_name)
        row = existing.get(key)
        old = row.access if row else None
        new = item.access.value if item.access else None
        if old == new:
            continue
        if new is None:
            assert row is not None
            db.delete(row)
            existing.pop(key)
        elif row is None:
            row = ProfileFieldPermission(
                profile_id=profile.id, object_api_name=key[0], field_api_name=key[1], access=new
            )
            db.add(row)
            existing[key] = row
        else:
            row.access = new
        changes[f"{key[0]}.{key[1]}"] = {"from": old, "to": new}
    if changes:
        _record(
            db,
            actor,
            AuditAction.UPDATE,
            "profile",
            profile.id,
            f"Changed field-level security of profile {profile.name}",
            meta,
            changes,
        )
        db.commit()
        db.expire(profile)
    return profile


# ================================================================ roles


def list_roles(db: Session) -> list[tuple[Role, int]]:
    counts = dict(
        db.execute(
            select(User.role_id, func.count()).where(User.role_id.is_not(None)).group_by(User.role_id)
        ).all()
    )
    roles = list(db.scalars(select(Role).order_by(Role.path)))
    return [(r, int(counts.get(r.id, 0))) for r in roles]


def role_depth(role: Role) -> int:
    return role.path.strip("/").count("/")


def get_role(db: Session, role_id: uuid.UUID) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise NotFoundError("Role not found.")
    return role


def create_role(db: Session, actor: AuthContext, data: RoleCreate, meta: RequestMeta) -> Role:
    if _name_taken(db, Role, data.name):
        raise ConflictError("A role with this name already exists.", fields={"name": "Already in use"})
    parent = get_role(db, data.parent_id) if data.parent_id else None
    role_id = uuid.uuid4()
    role = Role(
        id=role_id,
        name=data.name,
        description=data.description,
        parent_id=parent.id if parent else None,
        path=(parent.path if parent else "/") + f"{role_id}/",
    )
    db.add(role)
    _record(
        db,
        actor,
        AuditAction.CREATE,
        "role",
        role_id,
        f"Created role {role.name}" + (f" under {parent.name}" if parent else " (top level)"),
        meta,
    )
    db.commit()
    return role


def update_role(
    db: Session, actor: AuthContext, role_id: uuid.UUID, data: RoleUpdate, meta: RequestMeta
) -> Role:
    role = get_role(db, role_id)
    fields = data.model_fields_set
    changes: dict[str, Any] = {}
    if "name" in fields and data.name is not None and data.name != role.name:
        if _name_taken(db, Role, data.name, role.id):
            raise ConflictError("A role with this name already exists.", fields={"name": "Already in use"})
        changes["name"] = {"from": role.name, "to": data.name}
        role.name = data.name
    if "description" in fields and data.description != role.description:
        changes["description"] = {"from": role.description, "to": data.description}
        role.description = data.description
    if "parent_id" in fields and data.parent_id != role.parent_id:
        new_parent = get_role(db, data.parent_id) if data.parent_id else None
        if new_parent is not None and new_parent.path.startswith(role.path):
            raise _invalid(
                "A role cannot be moved under itself or one of its subordinates.", "parent_id", "role_cycle"
            )
        old_prefix = role.path
        new_prefix = (new_parent.path if new_parent else "/") + f"{role.id}/"
        db.execute(
            update(Role)
            .where(Role.path.startswith(old_prefix, autoescape=True))
            .values(path=func.concat(new_prefix, func.substr(Role.path, len(old_prefix) + 1)))
            .execution_options(synchronize_session=False)
        )
        changes["parent_id"] = {
            "from": str(role.parent_id) if role.parent_id else None,
            "to": str(new_parent.id) if new_parent else None,
        }
        role.parent_id = new_parent.id if new_parent else None
    if changes:
        _record(db, actor, AuditAction.UPDATE, "role", role.id, f"Updated role {role.name}", meta, changes)
        db.commit()
        db.refresh(role)
    return role


def delete_role(db: Session, actor: AuthContext, role_id: uuid.UUID, meta: RequestMeta) -> None:
    role = get_role(db, role_id)
    if db.scalar(select(Role.id).where(Role.parent_id == role.id).limit(1)) is not None:
        raise ConflictError("Move or delete this role's subordinate roles first.")
    if db.scalar(select(User.id).where(User.role_id == role.id).limit(1)) is not None:
        raise ConflictError("Reassign the users in this role first.")
    in_rules = db.scalar(
        select(SharingRule.id)
        .where(
            (
                (SharingRule.source_type.in_(("role", "role_and_subordinates")))
                & (SharingRule.source_id == role.id)
            )
            | (
                (SharingRule.target_type.in_(("role", "role_and_subordinates")))
                & (SharingRule.target_id == role.id)
            )
        )
        .limit(1)
    )
    if in_rules is not None:
        raise ConflictError("This role is used by a sharing rule.")
    _record(db, actor, AuditAction.DELETE, "role", role.id, f"Deleted role {role.name}", meta)
    db.execute(delete(GroupMember).where(GroupMember.role_id == role.id))
    db.delete(role)
    db.commit()


def subordinate_role_ids(db: Session, role: Role, *, include_self: bool = False) -> list[uuid.UUID]:
    stmt = select(Role.id).where(Role.path.startswith(role.path, autoescape=True))
    if not include_self:
        stmt = stmt.where(Role.id != role.id)
    return list(db.scalars(stmt))


# ================================================================ sharing defaults


def list_sharing_defaults(db: Session) -> list[SharingDefault]:
    stored = {sd.object_api_name: sd for sd in db.scalars(select(SharingDefault))}
    result = []
    for api in sorted(known_objects(db)):
        default = _DEFAULT_SHARING.get(api, SharingAccess.PRIVATE)
        result.append(
            stored.get(api)
            or SharingDefault(object_api_name=api, access=default.value, grant_access_using_hierarchy=True)
        )
    return result


def set_sharing_default(
    db: Session, actor: AuthContext, api: str, data: SharingDefaultIn, meta: RequestMeta
) -> SharingDefault:
    ensure_known_object(db, api)
    is_detail = _DEFAULT_SHARING.get(api) is SharingAccess.CONTROLLED_BY_PARENT
    if is_detail and data.access is not SharingAccess.CONTROLLED_BY_PARENT:
        raise _invalid("This object's sharing is controlled by its parent record.", "access")
    if not is_detail and data.access is SharingAccess.CONTROLLED_BY_PARENT:
        raise _invalid("Only detail objects can be controlled by a parent.", "access")
    row = db.get(SharingDefault, api)
    before = (
        {"access": row.access, "grant_access_using_hierarchy": row.grant_access_using_hierarchy}
        if row
        else {}
    )
    if row is None:
        row = SharingDefault(object_api_name=api)
        db.add(row)
    row.access = data.access.value
    row.grant_access_using_hierarchy = data.grant_access_using_hierarchy
    changes = audit.diff(
        before, {"access": row.access, "grant_access_using_hierarchy": row.grant_access_using_hierarchy}
    )
    if changes:
        _record(
            db,
            actor,
            AuditAction.UPDATE,
            "sharing_default",
            api,
            f"Changed sharing default of {api}",
            meta,
            changes,
        )
    db.commit()
    return row


# ================================================================ groups


def list_groups(db: Session) -> list[Group]:
    return list(db.scalars(select(Group).order_by(func.lower(Group.name))))


def get_group(db: Session, group_id: uuid.UUID) -> Group:
    group = db.get(Group, group_id)
    if group is None:
        raise NotFoundError("Group not found.")
    return group


def save_group(
    db: Session, actor: AuthContext, data: GroupIn, meta: RequestMeta, group_id: uuid.UUID | None = None
) -> Group:
    group = get_group(db, group_id) if group_id else None
    if _name_taken(db, Group, data.name, group.id if group else None):
        raise ConflictError("A group with this name already exists.", fields={"name": "Already in use"})
    if group is None:
        group = Group(name=data.name, description=data.description)
        db.add(group)
        db.flush()
        _record(db, actor, AuditAction.CREATE, "group", group.id, f"Created group {group.name}", meta)
    else:
        changes = audit.diff(
            {"name": group.name, "description": group.description},
            {"name": data.name, "description": data.description},
        )
        group.name, group.description = data.name, data.description
        if changes:
            _record(
                db, actor, AuditAction.UPDATE, "group", group.id, f"Updated group {group.name}", meta, changes
            )
    db.commit()
    return group


def set_group_members(
    db: Session, actor: AuthContext, group_id: uuid.UUID, data: GroupMembersIn, meta: RequestMeta
) -> Group:
    group = get_group(db, group_id)
    user_ids = list(dict.fromkeys(data.user_ids))
    _ensure_users_exist(db, user_ids, "user_ids")
    roles = {(r.role_id, r.include_subordinates) for r in data.roles}
    for role_id, _ in roles:
        if db.get(Role, role_id) is None:
            raise _invalid("Unknown role.", "roles")
    db.execute(delete(GroupMember).where(GroupMember.group_id == group.id))
    db.add_all(GroupMember(group_id=group.id, user_id=u) for u in user_ids)
    db.add_all(
        GroupMember(group_id=group.id, role_id=r, include_subordinates=s) for r, s in sorted(roles, key=str)
    )
    _record(
        db,
        actor,
        AuditAction.UPDATE,
        "group",
        group.id,
        f"Set members of group {group.name}",
        meta,
        {
            "members": {
                "from": None,
                "to": {
                    "users": [str(u) for u in user_ids],
                    "roles": [[str(r), s] for r, s in sorted(roles, key=str)],
                },
            }
        },
    )
    db.commit()
    db.expire(group)
    return group


def delete_group(db: Session, actor: AuthContext, group_id: uuid.UUID, meta: RequestMeta) -> None:
    group = get_group(db, group_id)
    used = db.scalar(
        select(SharingRule.id)
        .where(
            ((SharingRule.source_type == "group") & (SharingRule.source_id == group.id))
            | ((SharingRule.target_type == "group") & (SharingRule.target_id == group.id))
        )
        .limit(1)
    )
    if used is not None:
        raise ConflictError("This group is used by a sharing rule.")
    _record(db, actor, AuditAction.DELETE, "group", group.id, f"Deleted group {group.name}", meta)
    db.delete(group)
    db.commit()


def _ensure_users_exist(db: Session, user_ids: list[uuid.UUID], field: str) -> None:
    if not user_ids:
        return
    found = set(db.scalars(select(User.id).where(User.id.in_(user_ids))))
    if found != set(user_ids):
        raise _invalid("One or more users do not exist.", field)


# ================================================================ queues


def list_queues(db: Session) -> list[Queue]:
    return list(db.scalars(select(Queue).order_by(func.lower(Queue.name))))


def get_queue(db: Session, queue_id: uuid.UUID) -> Queue:
    queue = db.get(Queue, queue_id)
    if queue is None:
        raise NotFoundError("Queue not found.")
    return queue


def save_queue(
    db: Session, actor: AuthContext, data: QueueIn, meta: RequestMeta, queue_id: uuid.UUID | None = None
) -> Queue:
    queue = get_queue(db, queue_id) if queue_id else None
    if _name_taken(db, Queue, data.name, queue.id if queue else None):
        raise ConflictError("A queue with this name already exists.", fields={"name": "Already in use"})
    objects = sorted(set(data.object_api_names))
    for api in objects:
        ensure_known_object(db, api, "object_api_names")
    snapshot = {"name": data.name, "email": data.email or None, "object_api_names": objects}
    if queue is None:
        queue = Queue(**snapshot)
        db.add(queue)
        db.flush()
        _record(
            db,
            actor,
            AuditAction.CREATE,
            "queue",
            queue.id,
            f"Created queue {queue.name}",
            meta,
            audit.diff({}, snapshot),
        )
    else:
        changes = audit.diff(
            {"name": queue.name, "email": queue.email, "object_api_names": queue.object_api_names}, snapshot
        )
        for k, v in snapshot.items():
            setattr(queue, k, v)
        if changes:
            _record(
                db, actor, AuditAction.UPDATE, "queue", queue.id, f"Updated queue {queue.name}", meta, changes
            )
    db.commit()
    return queue


def set_queue_members(
    db: Session, actor: AuthContext, queue_id: uuid.UUID, data: QueueMembersIn, meta: RequestMeta
) -> Queue:
    queue = get_queue(db, queue_id)
    user_ids = list(dict.fromkeys(data.user_ids))
    _ensure_users_exist(db, user_ids, "user_ids")
    db.execute(delete(QueueMember).where(QueueMember.queue_id == queue.id))
    db.add_all(QueueMember(queue_id=queue.id, user_id=u) for u in user_ids)
    _record(
        db,
        actor,
        AuditAction.UPDATE,
        "queue",
        queue.id,
        f"Set members of queue {queue.name}",
        meta,
        {"members": {"from": None, "to": [str(u) for u in user_ids]}},
    )
    db.commit()
    db.expire(queue)
    return queue


def delete_queue(db: Session, actor: AuthContext, queue_id: uuid.UUID, meta: RequestMeta) -> None:
    queue = get_queue(db, queue_id)
    if (
        db.scalar(
            select(SharingRule.id)
            .where(SharingRule.source_type == "queue", SharingRule.source_id == queue.id)
            .limit(1)
        )
        is not None
    ):
        raise ConflictError("This queue is used by a sharing rule.")
    _record(db, actor, AuditAction.DELETE, "queue", queue.id, f"Deleted queue {queue.name}", meta)
    db.delete(queue)
    db.commit()


# ================================================================ sharing rules


def _ensure_principal(db: Session, kind: str, principal_id: uuid.UUID, field: str) -> None:
    model: Any = {"role": Role, "role_and_subordinates": Role, "group": Group, "queue": Queue}[kind]
    if db.get(model, principal_id) is None:
        raise _invalid(f"Unknown {kind.replace('_', ' ')}.", field)


def _validate_rule(db: Session, data: SharingRuleIn) -> None:
    ensure_known_object(db, data.object_api_name)
    if _DEFAULT_SHARING.get(data.object_api_name) is SharingAccess.CONTROLLED_BY_PARENT:
        raise _invalid("Sharing of this object is controlled by its parent record.", "object_api_name")
    if data.rule_type == "owner":
        if data.source_type is None or data.source_id is None or data.criteria is not None:
            raise _invalid("Owner-based rules need a source and no criteria.", "source_type")
        _ensure_principal(db, data.source_type, data.source_id, "source_id")
    else:
        if data.criteria is None or data.source_type is not None or data.source_id is not None:
            raise _invalid("Criteria-based rules need criteria and no source.", "criteria")
    _ensure_principal(db, data.target_type, data.target_id, "target_id")


def list_sharing_rules(db: Session, object_api_name: str | None) -> list[SharingRule]:
    stmt = select(SharingRule).order_by(SharingRule.object_api_name, func.lower(SharingRule.name))
    if object_api_name:
        stmt = stmt.where(SharingRule.object_api_name == object_api_name)
    return list(db.scalars(stmt))


def get_sharing_rule(db: Session, rule_id: uuid.UUID) -> SharingRule:
    rule = db.get(SharingRule, rule_id)
    if rule is None:
        raise NotFoundError("Sharing rule not found.")
    return rule


def _rule_values(data: SharingRuleIn) -> dict[str, Any]:
    return {
        "object_api_name": data.object_api_name,
        "name": data.name,
        "description": data.description,
        "rule_type": data.rule_type,
        "source_type": data.source_type,
        "source_id": data.source_id,
        "criteria": data.criteria.model_dump() if data.criteria else None,
        "target_type": data.target_type,
        "target_id": data.target_id,
        "access": data.access.value,
    }


def save_sharing_rule(
    db: Session, actor: AuthContext, data: SharingRuleIn, meta: RequestMeta, rule_id: uuid.UUID | None = None
) -> SharingRule:
    _validate_rule(db, data)
    values = _rule_values(data)
    if rule_id is None:
        rule = SharingRule(**values)
        db.add(rule)
        db.flush()
        _record(
            db,
            actor,
            AuditAction.CREATE,
            "sharing_rule",
            rule.id,
            f"Created sharing rule {rule.name} on {rule.object_api_name}",
            meta,
            audit.diff({}, values),
        )
    else:
        rule = get_sharing_rule(db, rule_id)
        before = {k: getattr(rule, k) for k in values}
        for k, v in values.items():
            setattr(rule, k, v)
        changes = audit.diff(before, values)
        if changes:
            _record(
                db,
                actor,
                AuditAction.UPDATE,
                "sharing_rule",
                rule.id,
                f"Updated sharing rule {rule.name}",
                meta,
                changes,
            )
    db.commit()
    db.refresh(rule)
    return rule


def delete_sharing_rule(db: Session, actor: AuthContext, rule_id: uuid.UUID, meta: RequestMeta) -> None:
    rule = get_sharing_rule(db, rule_id)
    _record(db, actor, AuditAction.DELETE, "sharing_rule", rule.id, f"Deleted sharing rule {rule.name}", meta)
    db.delete(rule)
    db.commit()

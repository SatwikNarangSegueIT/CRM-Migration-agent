"""Per-user effective permissions, loaded once per request.

Layers (plan v3, section 9): system permissions, object permissions, field-level security (here) and
record sharing (record engine, phase 3, using role paths from this policy).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProfileFieldPermission, ProfileObjectPermission, ProfileSystemPermission, User
from app.security.catalog import FieldAccess, ObjectAccess, SystemPermission

SYSTEM_ADMIN_KEY = "system_administrator"
FULL_ACCESS = ObjectAccess(read=True, create=True, edit=True, delete=True, view_all=True, modify_all=True)


@dataclass(frozen=True)
class AccessPolicy:
    user_id: uuid.UUID
    profile_id: uuid.UUID
    profile_name: str
    is_system_admin: bool
    is_portal: bool
    role_id: uuid.UUID | None
    role_path: str | None
    system: frozenset[str] = frozenset()
    objects: dict[str, ObjectAccess] = field(default_factory=dict)
    fields: dict[tuple[str, str], FieldAccess] = field(default_factory=dict)

    @property
    def is_staff(self) -> bool:
        return not self.is_portal

    def has(self, permission: SystemPermission) -> bool:
        return self.is_system_admin or permission.value in self.system

    def object(self, object_api_name: str) -> ObjectAccess:
        """Object permissions. System Administrator implicitly has full access to every object."""
        if self.is_system_admin:
            return FULL_ACCESS
        return self.objects.get(object_api_name, ObjectAccess())

    def field(self, object_api_name: str, field_api_name: str, default: FieldAccess) -> FieldAccess:
        """Field access, capped by object access (no edit without object edit/create)."""
        if self.is_system_admin:
            return FieldAccess.EDIT
        obj = self.object(object_api_name)
        if not obj.read:
            return FieldAccess.HIDDEN
        access = self.fields.get((object_api_name, field_api_name), default)
        if access is FieldAccess.EDIT and not (obj.edit or obj.create):
            return FieldAccess.READ
        return access

    def system_permissions(self) -> list[str]:
        if self.is_system_admin:
            return sorted(p.value for p in SystemPermission)
        return sorted(self.system)


def load_policy(db: Session, user: User) -> AccessPolicy:
    profile = user.profile
    system = frozenset(
        db.scalars(
            select(ProfileSystemPermission.permission).where(ProfileSystemPermission.profile_id == profile.id)
        )
    )
    objects = {
        row.object_api_name: ObjectAccess(
            read=row.can_read,
            create=row.can_create,
            edit=row.can_edit,
            delete=row.can_delete,
            view_all=row.view_all,
            modify_all=row.modify_all,
        )
        for row in db.scalars(
            select(ProfileObjectPermission).where(ProfileObjectPermission.profile_id == profile.id)
        )
    }
    fields = {
        (row.object_api_name, row.field_api_name): FieldAccess(row.access)
        for row in db.scalars(
            select(ProfileFieldPermission).where(ProfileFieldPermission.profile_id == profile.id)
        )
    }
    return AccessPolicy(
        user_id=user.id,
        profile_id=profile.id,
        profile_name=profile.name,
        is_system_admin=profile.key == SYSTEM_ADMIN_KEY,
        is_portal=profile.is_portal,
        role_id=user.role_id,
        role_path=user.role.path if user.role is not None else None,
        system=system,
        objects=objects,
        fields=fields,
    )

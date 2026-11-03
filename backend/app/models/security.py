"""Profiles, permissions, role hierarchy, groups, queues and sharing configuration (plan v3, section 9)."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

API_NAME = String(80)


class Profile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "profiles"

    # Stable key for the shipped profiles (e.g. "system_administrator"); NULL for admin-created profiles.
    key: Mapped[str | None] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    # System Administrator: cannot be edited or deleted.
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # External customer users (portal); never reach staff APIs.
    is_portal: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    system_permissions: Mapped[list[ProfileSystemPermission]] = relationship(
        cascade="all, delete-orphan", back_populates="profile"
    )
    object_permissions: Mapped[list[ProfileObjectPermission]] = relationship(
        cascade="all, delete-orphan", back_populates="profile"
    )
    field_permissions: Mapped[list[ProfileFieldPermission]] = relationship(
        cascade="all, delete-orphan", back_populates="profile"
    )


class ProfileSystemPermission(Base):
    __tablename__ = "profile_system_permissions"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    permission: Mapped[str] = mapped_column(String(40), primary_key=True)

    profile: Mapped[Profile] = relationship(back_populates="system_permissions")


class ProfileObjectPermission(Base):
    __tablename__ = "profile_object_permissions"
    __table_args__ = (
        CheckConstraint(
            "can_read OR NOT (can_create OR can_edit OR can_delete OR view_all OR modify_all)",
            name="read_required",
        ),
        CheckConstraint("NOT modify_all OR (view_all AND can_edit)", name="modify_all_implies"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    object_api_name: Mapped[str] = mapped_column(API_NAME, primary_key=True)
    can_read: Mapped[bool] = mapped_column(Boolean, default=False)
    can_create: Mapped[bool] = mapped_column(Boolean, default=False)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False)
    view_all: Mapped[bool] = mapped_column(Boolean, default=False)
    modify_all: Mapped[bool] = mapped_column(Boolean, default=False)

    profile: Mapped[Profile] = relationship(back_populates="object_permissions")


class ProfileFieldPermission(Base):
    """Field-level security override. Absent row = the field's default access (set per field)."""

    __tablename__ = "profile_field_permissions"
    __table_args__ = (CheckConstraint("access IN ('hidden', 'read', 'edit')", name="access_valid"),)

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    object_api_name: Mapped[str] = mapped_column(API_NAME, primary_key=True)
    field_api_name: Mapped[str] = mapped_column(API_NAME, primary_key=True)
    access: Mapped[str] = mapped_column(String(10))

    profile: Mapped[Profile] = relationship(back_populates="field_permissions")


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Position in the role hierarchy (who sees whose records). Separate from profiles."""

    __tablename__ = "roles"

    key: Mapped[str | None] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), index=True
    )
    # Materialised path of ancestor ids including self: "/<root>/<child>/<self>/". Maintained by the service.
    path: Mapped[str] = mapped_column(String(2000), index=True)

    parent: Mapped[Role | None] = relationship(remote_side="Role.id")


class SharingDefault(Base):
    """Organisation-wide default (OWD) per object."""

    __tablename__ = "sharing_defaults"
    __table_args__ = (
        CheckConstraint(
            "access IN ('private', 'read', 'read_write', 'controlled_by_parent')", name="access_valid"
        ),
    )

    object_api_name: Mapped[str] = mapped_column(API_NAME, primary_key=True)
    access: Mapped[str] = mapped_column(String(24))
    grant_access_using_hierarchy: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Group(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Public group used as a sharing-rule source or target."""

    __tablename__ = "groups"

    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(Text)

    members: Mapped[list[GroupMember]] = relationship(cascade="all, delete-orphan", back_populates="group")


class GroupMember(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "group_members"
    __table_args__ = (
        CheckConstraint("(user_id IS NULL) <> (role_id IS NULL)", name="one_member"),
        UniqueConstraint(
            "group_id", "user_id", "role_id", "include_subordinates", name="uq_group_members_member"
        ),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    include_subordinates: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    group: Mapped[Group] = relationship(back_populates="members")


class Queue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Records (cases, leads, custom objects) can be owned by a queue; members work them."""

    __tablename__ = "queues"

    name: Mapped[str] = mapped_column(String(80), unique=True)
    email: Mapped[str | None] = mapped_column(String(254))
    object_api_names: Mapped[list[str]] = mapped_column(JSONB, default=list)

    members: Mapped[list[QueueMember]] = relationship(cascade="all, delete-orphan", back_populates="queue")


class QueueMember(Base):
    __tablename__ = "queue_members"

    queue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("queues.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    queue: Mapped[Queue] = relationship(back_populates="members")


class SharingRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Shares records with a role / role and subordinates / group.

    Owner-based: records owned by members of the source. Criteria-based: records matching `criteria`
    (evaluated by the record engine).
    """

    __tablename__ = "sharing_rules"
    __table_args__ = (
        CheckConstraint("rule_type IN ('owner', 'criteria')", name="rule_type_valid"),
        CheckConstraint("access IN ('read', 'read_write')", name="access_valid"),
        CheckConstraint(
            "source_type IS NULL OR source_type IN ('role', 'role_and_subordinates', 'group', 'queue')",
            name="source_type_valid",
        ),
        CheckConstraint(
            "target_type IN ('role', 'role_and_subordinates', 'group')", name="target_type_valid"
        ),
        CheckConstraint(
            "(rule_type = 'owner' AND source_type IS NOT NULL AND source_id IS NOT NULL AND criteria IS NULL)"
            " OR (rule_type = 'criteria' AND criteria IS NOT NULL AND source_type IS NULL AND source_id IS NULL)",  # noqa: E501
            name="shape_valid",
        ),
        Index("ix_sharing_rules_object", "object_api_name"),
    )

    object_api_name: Mapped[str] = mapped_column(API_NAME)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    rule_type: Mapped[str] = mapped_column(String(10))
    source_type: Mapped[str | None] = mapped_column(String(30))
    source_id: Mapped[uuid.UUID | None] = mapped_column()
    criteria: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[uuid.UUID] = mapped_column()
    access: Mapped[str] = mapped_column(String(10))

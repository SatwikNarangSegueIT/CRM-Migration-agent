"""Metadata: object and field definitions, apps, list views (plan v3, sections 3-7).

Every business object, standard or custom, is described here and stored by the record engine.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

API_NAME = String(80)

FIELD_TYPES = (
    "text",
    "textarea",
    "long_text",
    "email",
    "phone",
    "url",
    "number",
    "percent",
    "currency",
    "date",
    "datetime",
    "time",
    "checkbox",
    "picklist",
    "multi_picklist",
    "lookup",
    "master_detail",
    "auto_number",
    "address",
    "encrypted_text",
    "user",
)


class ObjectDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "object_definitions"
    __table_args__ = (
        CheckConstraint("name_field_type IN ('text', 'auto_number')", name="name_field_type_valid"),
    )

    api_name: Mapped[str] = mapped_column(API_NAME, unique=True)
    label: Mapped[str] = mapped_column(String(80))
    plural_label: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(40), default="record", server_default="record")
    color: Mapped[str] = mapped_column(String(9), default="#64748b", server_default="#64748b")
    # Standard objects ship with the product (cannot be deleted); custom objects end in "__c".
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Industry pack that installed the object (NULL = core / admin-created).
    pack_key: Mapped[str | None] = mapped_column(String(60))
    # Name field: free text, or an auto-number such as "CASE-{00000}".
    name_field_type: Mapped[str] = mapped_column(String(12), default="text", server_default="text")
    name_label: Mapped[str] = mapped_column(String(80), default="Name", server_default="Name")
    name_format: Mapped[str | None] = mapped_column(String(60))
    # Feature switches.
    track_history: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    allow_activities: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    allow_files: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    allow_notes: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    searchable: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    allow_reports: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    show_in_portal: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Queues may own records of this object.
    allow_queues: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Hidden from tabs/search (e.g. junction and line objects, still reachable through related lists).
    is_detail_only: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Layout metadata (ordered lists; the v1 UI edits these as forms, not a drag-and-drop canvas).
    # page_layout: [{"label": str, "columns": 1|2, "fields": [api_name, ...]}]
    page_layout: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # compact_layout: [api_name, ...] shown in the highlights panel.
    compact_layout: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # related_lists: [{"object": api, "field": lookup api, "label": str, "columns": [api, ...]}]
    related_lists: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # Default list-view columns.
    list_columns: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # Portal scoping: lookup fields that tie a record to the portal user's contact or account.
    portal_fields: Mapped[list[str]] = mapped_column(JSONB, default=list)

    fields: Mapped[list[FieldDefinition]] = relationship(
        back_populates="object",
        cascade="all, delete-orphan",
        order_by="FieldDefinition.sort_order",
    )


class FieldDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "field_definitions"
    __table_args__ = (
        UniqueConstraint("object_id", "api_name", name="uq_field_definitions_object_api"),
        CheckConstraint(
            "type IN (" + ", ".join(f"'{t}'" for t in FIELD_TYPES) + ")",
            name="type_valid",
        ),
        CheckConstraint("default_access IN ('hidden', 'read', 'edit')", name="default_access_valid"),
    )

    object_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("object_definitions.id", ondelete="CASCADE"))
    api_name: Mapped[str] = mapped_column(API_NAME)
    label: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(20))
    help_text: Mapped[str | None] = mapped_column(Text)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Standard fields cannot be deleted or have their type changed.
    is_standard: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Read-only for everyone (maintained by the engine or object hooks, e.g. totals).
    is_readonly: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_unique: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    external_id: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    filterable: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Creates an expression index (limit: 25 per object).
    indexed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    searchable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    track_history: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Field-level security for profiles without an explicit override.
    default_access: Mapped[str] = mapped_column(String(10), default="edit", server_default="edit")
    default_value: Mapped[Any] = mapped_column(JSONB(none_as_null=True), nullable=True)
    # Type options: max_length, precision, scale, min, max, values (picklists), target / targets
    # (lookups), delete_rule, is_path, probabilities, format, filter.
    options: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    pack_key: Mapped[str | None] = mapped_column(String(60))
    # Soft-deleted custom fields are kept for 15 days, then purged.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    object: Mapped[ObjectDefinition] = relationship(back_populates="fields")


class MetadataRevision(Base):
    """Single row incremented on every metadata change; processes reload their cache when it moves."""

    __tablename__ = "metadata_revision"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    revision: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1")


class App(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Configurable app: name, icon, ordered tabs, profiles that can see it (empty = all staff)."""

    __tablename__ = "apps"

    key: Mapped[str] = mapped_column(String(60), unique=True)
    label: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str] = mapped_column(String(40), default="app", server_default="app")
    color: Mapped[str] = mapped_column(String(9), default="#0176d3", server_default="#0176d3")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # [{"kind": "home"|"object"|"calendar"|"reports"|"dashboards", "object": api_name?}]
    tabs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    profile_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    pack_key: Mapped[str | None] = mapped_column(String(60))


class ListView(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "list_views"
    __table_args__ = (
        CheckConstraint("visibility IN ('private', 'public', 'shared')", name="visibility_valid"),
        CheckConstraint("scope IN ('mine', 'all', 'team', 'queue')", name="scope_valid"),
        Index("ix_list_views_object", "object_api_name"),
    )

    object_api_name: Mapped[str] = mapped_column(API_NAME)
    name: Mapped[str] = mapped_column(String(80))
    # Shipped views (e.g. "All Open Leads") have a key and no owner.
    key: Mapped[str | None] = mapped_column(String(60))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    visibility: Mapped[str] = mapped_column(String(10), default="private")
    shared_profile_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    shared_role_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    scope: Mapped[str] = mapped_column(String(10), default="all")
    columns: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # Filter AST: {"logic": "and"|"or", "conditions": [{"field", "op", "value"} | nested]}
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # [{"field": api_name, "direction": "asc"|"desc"}]
    sort: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list)
    # Optional Kanban grouping (a path picklist).
    kanban_field: Mapped[str | None] = mapped_column(API_NAME)

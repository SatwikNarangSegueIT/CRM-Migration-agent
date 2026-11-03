"""Record storage (plan v3, section 3): one table for every object, values in JSONB.

System fields are real columns; field values live in `data` keyed by field API name. Lookup and
master-detail values are mirrored in `record_links` with real foreign keys (integrity, related lists,
delete rules).
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
    LargeBinary,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

API_NAME = String(80)


class Record(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "records"
    __table_args__ = (
        CheckConstraint("NOT (owner_id IS NOT NULL AND queue_id IS NOT NULL)", name="one_owner"),
        Index("ix_records_object_name", "object_api_name", "is_deleted", "name"),
        Index("ix_records_object_created", "object_api_name", "created_at"),
        Index("ix_records_owner", "owner_id"),
        Index("ix_records_queue", "queue_id"),
        Index("ix_records_data", "data", postgresql_using="gin", postgresql_ops={"data": "jsonb_path_ops"}),
        Index("ix_records_search", "search_vector", postgresql_using="gin"),
        Index(
            "ix_records_deleted",
            "deleted_at",
            postgresql_where=text("is_deleted"),
        ),
    )

    object_api_name: Mapped[str] = mapped_column(
        API_NAME, ForeignKey("object_definitions.api_name", ondelete="RESTRICT", onupdate="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    record_number: Mapped[str | None] = mapped_column(String(60))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    queue_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("queues.id", ondelete="SET NULL"))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Optimistic concurrency: updates must send the version they read.
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    search_vector: Mapped[Any] = mapped_column(TSVECTOR, nullable=True)


class RecordLink(Base):
    """Mirror of a lookup / master-detail value with referential integrity."""

    __tablename__ = "record_links"
    __table_args__ = (Index("ix_record_links_to", "to_record_id", "field_api_name"),)

    from_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("records.id", ondelete="CASCADE"), primary_key=True
    )
    field_api_name: Mapped[str] = mapped_column(API_NAME, primary_key=True)
    # RESTRICT: the record engine applies delete rules (clear / restrict / cascade) before deleting.
    to_record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("records.id", ondelete="RESTRICT"))
    from_object: Mapped[str] = mapped_column(API_NAME)
    is_master: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class FieldHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "field_history"
    __table_args__ = (Index("ix_field_history_record", "record_id", "changed_at"),)

    record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"))
    field_api_name: Mapped[str] = mapped_column(API_NAME)
    old_value: Mapped[Any] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Any] = mapped_column(JSONB, nullable=True)
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecordShare(UUIDPrimaryKeyMixin, Base):
    """Manual share of one record with a user, group or role (plan v3, section 9)."""

    __tablename__ = "record_shares"
    __table_args__ = (
        CheckConstraint(
            "principal_type IN ('user', 'group', 'role', 'role_and_subordinates')", name="principal_valid"
        ),
        CheckConstraint("access IN ('read', 'read_write')", name="access_valid"),
        Index("ix_record_shares_record", "record_id"),
        Index("ix_record_shares_principal", "principal_type", "principal_id"),
    )

    record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"))
    principal_type: Mapped[str] = mapped_column(String(30))
    principal_id: Mapped[uuid.UUID] = mapped_column()
    access: Mapped[str] = mapped_column(String(10))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Sequence(Base):
    """Counters for auto-numbers (row-locked while incremented)."""

    __tablename__ = "sequences"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    next_value: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1")


class RecentItem(Base):
    __tablename__ = "recent_items"
    __table_args__ = (Index("ix_recent_items_user_viewed", "user_id", "viewed_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("records.id", ondelete="CASCADE"), primary_key=True
    )
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserPreference(Base):
    """Per-user UI preferences: default list view per object, pinned items, locale, time zone."""

    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Notification(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user", "user_id", "read_at", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(500))
    record_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StoredFile(UUIDPrimaryKeyMixin, Base):
    """Binary content of an uploaded file. `storage` = "db" keeps bytes here; "s3"/"local" keep a key."""

    __tablename__ = "stored_files"

    storage: Mapped[str] = mapped_column(String(10), default="db")
    storage_key: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[bytes | None] = mapped_column(LargeBinary)
    content_type: Mapped[str] = mapped_column(String(120))
    size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    scan_status: Mapped[str] = mapped_column(String(12), default="clean", server_default="clean")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')", name="status_valid"
        ),
        CheckConstraint("duplicate_action IN ('skip', 'update', 'create')", name="duplicate_action_valid"),
    )

    object_api_name: Mapped[str] = mapped_column(API_NAME)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(12), default="pending")
    file_name: Mapped[str] = mapped_column(String(255))
    csv_text: Mapped[str] = mapped_column(Text)
    # {"CSV column": "field api name"}
    mapping: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)
    match_field: Mapped[str | None] = mapped_column(API_NAME)
    duplicate_action: Mapped[str] = mapped_column(String(10), default="skip")
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    # [{"row": n, "message": str}]
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Setting(Base):
    """Organisation settings (branding, billing details, invoice numbering, retention...)."""

    __tablename__ = "org_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PackInstallation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pack_installations"

    pack_key: Mapped[str] = mapped_column(String(60), unique=True)
    version: Mapped[str] = mapped_column(String(20))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    installed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)

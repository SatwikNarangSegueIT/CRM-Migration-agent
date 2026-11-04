"""Platform schema (plan v4, section 3): the tenant catalogue shared by every firm.

These tables live in the ``platform`` schema and have their own metadata and migrations
(``alembic_platform``); every other model lives in a tenant schema selected per transaction.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, MetaData, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.base import NAMING_CONVENTION

PLATFORM_SCHEMA = "platform"


class PlatformBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION, schema=PLATFORM_SCHEMA)


class Tenant(PlatformBase):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("slug ~ '^[a-z0-9][a-z0-9-]{1,40}$'", name="slug_format"),
        CheckConstraint("status IN ('active', 'provisioning', 'suspended', 'deleted')", name="status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(41), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    # Profession the workspace was set up for: legal, migration, accounting, lending (or general).
    domain: Mapped[str] = mapped_column(String(40), default="general")
    schema_name: Mapped[str] = mapped_column(String(63), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    region: Mapped[str] = mapped_column(String(40), default="ap-southeast-2")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserDirectory(PlatformBase):
    """E-mail -> workspace(s), so sign-in can find the user's tenant. Kept in sync by app.tenancy."""

    __tablename__ = "user_directory"
    __table_args__ = (Index("ix_user_directory_email", "email"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254))


class SignupRequest(PlatformBase):
    """A sign-up waiting for e-mail verification (single-use link, 24 h; removed after 7 days)."""

    __tablename__ = "signup_requests"
    __table_args__ = (Index("ix_signup_requests_email", "email"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(254))
    name: Mapped[str] = mapped_column(String(200))
    firm_name: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(40))
    abn: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id", ondelete="SET NULL"))


class WarmSchema(PlatformBase):
    """A fully migrated, unassigned tenant schema, so a new workspace is ready instantly."""

    __tablename__ = "warm_schemas"

    schema_name: Mapped[str] = mapped_column(String(63), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

"""platform schema: tenants and user directory; shared extensions schema.

Revision ID: p0001
Revises:
Create Date: 2026-11-04

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Database-wide extensions stay where they are (often owned by a superuser); new ones go to a shared
    # "extensions" schema. Tenant DDL names an extension's objects with its schema.
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(41), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("domain", sa.String(40), nullable=False, server_default="general"),
        sa.Column("schema_name", sa.String(63), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("region", sa.String(40), nullable=False, server_default="ap-southeast-2"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("slug ~ '^[a-z0-9][a-z0-9-]{1,40}$'", name="ck_tenants_slug_format"),
        sa.CheckConstraint(
            "status IN ('active', 'provisioning', 'suspended', 'deleted')", name="ck_tenants_status_valid"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenants"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
        sa.UniqueConstraint("schema_name", name="uq_tenants_schema_name"),
        schema="platform",
    )
    op.create_table(
        "user_directory",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["platform.tenants.id"],
            ondelete="CASCADE",
            name="fk_user_directory_tenant_id_tenants",
        ),
        sa.PrimaryKeyConstraint("tenant_id", "user_id", name="pk_user_directory"),
        schema="platform",
    )
    op.create_index("ix_user_directory_email", "user_directory", ["email"], schema="platform")


def downgrade() -> None:
    op.drop_table("user_directory", schema="platform")
    op.drop_table("tenants", schema="platform")

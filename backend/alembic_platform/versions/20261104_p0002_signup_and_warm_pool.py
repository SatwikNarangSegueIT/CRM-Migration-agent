"""platform: sign-up requests and warm pool of pre-built tenant schemas.

Revision ID: p0002
Revises: p0001
Create Date: 2026-11-04

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p0002"
down_revision: str | Sequence[str] | None = "p0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signup_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("firm_name", sa.String(200), nullable=False),
        sa.Column("domain", sa.String(40), nullable=False),
        sa.Column("abn", sa.String(20), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["platform.tenants.id"],
            ondelete="SET NULL",
            name="fk_signup_requests_tenant_id_tenants",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_signup_requests"),
        sa.UniqueConstraint("token_hash", name="uq_signup_requests_token_hash"),
        schema="platform",
    )
    op.create_index("ix_signup_requests_email", "signup_requests", ["email"], schema="platform")
    op.create_table(
        "warm_schemas",
        sa.Column("schema_name", sa.String(63), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("schema_name", name="pk_warm_schemas"),
        schema="platform",
    )


def downgrade() -> None:
    op.drop_table("warm_schemas", schema="platform")
    op.drop_table("signup_requests", schema="platform")

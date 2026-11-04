"""platform: settings (outgoing e-mail configured in Setup).

Revision ID: p0003
Revises: p0002
Create Date: 2026-11-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p0003"
down_revision: str | Sequence[str] | None = "p0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("key", sa.String(60), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.String(254), nullable=True),
        sa.PrimaryKeyConstraint("key", name="pk_settings"),
        schema="platform",
    )


def downgrade() -> None:
    op.drop_table("settings", schema="platform")

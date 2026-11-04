"""security revision counter: metadata_revision.security, bumped on every security change so cached
permissions and sharing contexts are rebuilt (app.core.cache, app.security.revision).

Revision ID: 4a708a753f1b
Revises: b51c2e7a9d40
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4a708a753f1b"
down_revision: str | Sequence[str] | None = "b51c2e7a9d40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("metadata_revision", sa.Column("security", sa.BigInteger(), server_default="1", nullable=False))
    op.execute("INSERT INTO metadata_revision (id, revision, security) VALUES (1, 1, 1) ON CONFLICT (id) DO NOTHING")


def downgrade() -> None:
    op.drop_column("metadata_revision", "security")

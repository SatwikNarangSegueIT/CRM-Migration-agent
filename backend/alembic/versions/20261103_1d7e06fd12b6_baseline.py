"""baseline: empty root revision. Domain tables are added from phase 1.

Revision ID: 1d7e06fd12b6
Revises: 
Create Date: 2026-11-03 04:05:10.272097

"""
from collections.abc import Sequence


# revision identifiers, used by Alembic.
revision: str = '1d7e06fd12b6'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

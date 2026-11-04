"""immutable ISO date conversion for date-field indexes.

``(data->>'f')::date`` cannot be indexed: text-to-date casts depend on the DateStyle setting, so Postgres
treats them as not immutable. Stored dates are always ISO ``YYYY-MM-DD`` (app.engine.types), and ISO input
parses the same under every DateStyle, so this wrapper is safe to declare IMMUTABLE. Queries and
expression indexes both use it (app.engine.filters.field_expr, app.engine.indexes).

Created in the tenant schema the migration runs in (first entry of search_path).

Revision ID: c3f1d2e8a901
Revises: 4a708a753f1b
Create Date: 2026-11-05

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c3f1d2e8a901"
down_revision: str | Sequence[str] | None = "4a708a753f1b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTION = """
CREATE OR REPLACE FUNCTION crm_iso_date(value text) RETURNS date
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
AS $$ SELECT CASE WHEN value ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN value::date END $$
"""


def upgrade() -> None:
    op.execute(FUNCTION)


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN SELECT indexname FROM pg_indexes
                     WHERE schemaname = current_schema() AND indexdef LIKE '%crm_iso_date(%'
            LOOP
                EXECUTE format('DROP INDEX IF EXISTS %I', r.indexname);
            END LOOP;
        END $$;
        """
    )
    op.execute("DROP FUNCTION IF EXISTS crm_iso_date(text)")

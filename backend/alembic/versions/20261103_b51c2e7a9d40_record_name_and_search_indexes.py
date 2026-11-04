"""record name and search indexes: case-insensitive name sort index; trigram name index where pg_trgm exists.

Revision ID: b51c2e7a9d40
Revises: 7297d4764d7e
Create Date: 2026-11-03 13:00:00

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b51c2e7a9d40'
down_revision: Union[str, Sequence[str], None] = '7297d4764d7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # List views sort by lower(name) with the id as tie-breaker (keyset pagination).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_records_object_lower_name ON records "
        "(object_api_name, lower(name), id) WHERE NOT is_deleted"
    )
    # "Contains" search on record names. pg_trgm is available on Neon; skip quietly where it isn't.
    # Named ix_rec_* so Alembic autogenerate ignores it (it exists only where the extension does).
    op.execute(
        """
        DO $$
        DECLARE ext_schema text;
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
                BEGIN
                    CREATE EXTENSION IF NOT EXISTS pg_trgm;
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'pg_trgm not available; name search uses sequential scans';
                END;
            END IF;
            -- The operator class is named with the extension's schema: tenant schemas do not have the
            -- extension on their search_path.
            SELECT n.nspname INTO ext_schema FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace
                WHERE e.extname = 'pg_trgm';
            IF ext_schema IS NOT NULL THEN
                EXECUTE format(
                    'CREATE INDEX IF NOT EXISTS ix_rec_trgm_records_name ON records USING gin (name %I.gin_trgm_ops)',
                    ext_schema
                );
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_rec_trgm_records_name")
    op.execute("DROP INDEX IF EXISTS ix_records_object_lower_name")

"""Alembic environment for the shared ``platform`` schema (tenant catalogue).

Run via ``python -m app.cli migrate`` (or ``-x url=... upgrade head --sql`` to print the SQL).
"""

from __future__ import annotations

from alembic import context
from app.core.config import get_settings
from app.db.session import build_engine
from app.models.platform import PLATFORM_SCHEMA, PlatformBase

target_metadata = PlatformBase.metadata


def _url() -> str:
    return context.get_x_argument(as_dictionary=True).get("url") or get_settings().migration_database_url


def run_migrations_offline() -> None:
    """Emit SQL (``alembic upgrade --sql``) for review, e.g. the Neon upgrade script."""
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=PLATFORM_SCHEMA,
        include_schemas=True,
    )
    context.execute(f"CREATE SCHEMA IF NOT EXISTS {PLATFORM_SCHEMA}")
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = build_engine(get_settings(), url=_url(), null_pool=True)
    with engine.connect() as connection:
        connection.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {PLATFORM_SCHEMA}")
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=PLATFORM_SCHEMA,
            include_schemas=True,
            include_name=lambda name, type_, _parent: type_ != "schema" or name == PLATFORM_SCHEMA,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

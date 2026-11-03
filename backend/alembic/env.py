"""Alembic environment. Migrations run against the *direct* (non-pooled) Neon endpoint."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from app.core.config import get_settings
from app.db.session import build_engine
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    # Allow `alembic -x url=...` for one-off runs (e.g. tests); otherwise use settings.
    return context.get_x_argument(as_dictionary=True).get("url") or get_settings().migration_database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Migrations use a single short-lived connection; no pooling needed.
    engine = build_engine(get_settings(), url=_url(), null_pool=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

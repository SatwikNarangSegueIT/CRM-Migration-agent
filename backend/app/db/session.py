"""Database engine and session management, tuned for Neon serverless Postgres."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import Settings, get_settings


def build_engine(settings: Settings, url: str | None = None, *, null_pool: bool = False) -> Engine:
    """Create an engine. `null_pool=True` opens a fresh connection per use (migrations, scripts)."""
    connect_args: dict[str, Any] = {
        "connect_timeout": settings.db_connect_timeout_seconds,
        "application_name": settings.app_name,
    }
    if settings.disable_prepared_statements:
        # Neon pooled endpoints run PgBouncer in transaction mode; psycopg prepared statements are
        # disabled to stay safe regardless of the libpq/PgBouncer versions in use.
        connect_args["prepare_threshold"] = None
    elif settings.db_statement_timeout_ms and not null_pool:
        # Direct connections: cap runaway queries (reports, exports) server-side.
        connect_args["options"] = f"-c statement_timeout={settings.db_statement_timeout_ms}"
    if null_pool:
        return create_engine(url or settings.database_url, poolclass=NullPool, connect_args=connect_args)
    return create_engine(
        url or settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle_seconds,
        # Neon may scale compute to zero and drop idle connections; verify before use.
        pool_pre_ping=True,
        connect_args=connect_args,
    )


@lru_cache
def get_engine() -> Engine:
    return build_engine(get_settings())


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, rolled back on error."""
    session = get_sessionmaker()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def escape_like(value: str) -> str:
    """Escape LIKE wildcards in user input (use with escape='\\\\')."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

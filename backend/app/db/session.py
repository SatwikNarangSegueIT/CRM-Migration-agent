"""Database engine and session management, tuned for Neon serverless Postgres."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from fastapi import Request
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
    # Registers the session events that keep cached security data fresh (import has side effects).
    import app.security.revision
    import app.tenancy  # noqa: F401 - per-tenant search_path and user directory sync

    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def sibling_session(db: Session) -> Session:
    """A new session in the same tenant as ``db`` for read-only work on another thread.

    Shares the revisions ``db`` already knows (so caches are hit) unless ``db`` has uncommitted changes.
    """
    from app.core.cache import cache_allowed

    session = get_sessionmaker()()
    for key in ("tenant", "tenant_id", "tenant_slug"):
        if key in db.info:
            session.info[key] = db.info[key]
    if "revisions" in db.info and cache_allowed(db):
        session.info["revisions"] = db.info["revisions"]
    return session


def request_tenant_slug(request: Request) -> str | None:
    """Tenant named by the request: session cookie prefix, else the X-Tenant header or ?tenant=."""
    from app.tenancy import SESSION_COOKIE, TENANT_HEADER, split_token

    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        slug, _ = split_token(cookie)
        if slug:
            return slug
    return request.headers.get(TENANT_HEADER) or request.query_params.get("tenant") or None


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency: one session per request, bound to the request's tenant, rolled back on error."""
    from app.tenancy import bind_tenant, resolve

    session = get_sessionmaker()()
    bind_tenant(session, resolve(request_tenant_slug(request)))
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

"""Schema-per-tenant routing (plan v4, section 3).

Every firm (tenant) has its own PostgreSQL schema holding all CRM tables; the shared ``platform`` schema
lists the tenants and maps e-mail addresses to them. A database session is bound to one tenant
(``bind_tenant``) and every transaction it starts uses that tenant's ``search_path``:

* direct connections (local Postgres, Neon direct endpoint): the path is set once per pooled connection,
  outside any transaction, and only changes when the connection serves another tenant - no extra round
  trip in the steady state;
* PgBouncer transaction pooling (Neon ``-pooler`` endpoint): ``SET LOCAL`` at the start of every
  transaction, because a session-level setting could leak to another client of the same server connection.

A session that could not be resolved to a tenant is bound to a schema that does not exist, so any query
on tenant tables fails instead of reading another firm's data. Links in e-mails carry the tenant as a
token prefix (``<slug>.<token>``), as does the session cookie.
"""

from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from sqlalchemy import Connection, event, inspect, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, UOWTransaction

from app.core.cache import forget_revisions

logger = logging.getLogger("app.tenancy")

SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
DEFAULT_SCHEMA = "public"
# Never created: a session bound here cannot read any tenant's tables.
UNRESOLVED_SCHEMA = "tenant_unresolved"
EXTENSIONS_SCHEMA = "extensions"
SESSION_COOKIE = "crm_session"
TENANT_HEADER = "X-Tenant"
_CATALOGUE_TTL_SECONDS = 15.0
_PATH_KEY = "tenant_search_path"


def search_path_for(schema: str) -> str:
    if not SCHEMA_NAME.match(schema):
        raise ValueError(f"Invalid schema name: {schema!r}")
    return f'"{schema}", {EXTENSIONS_SCHEMA}'


@dataclass(frozen=True)
class TenantInfo:
    id: uuid.UUID | None
    slug: str | None
    name: str
    domain: str
    schema: str
    status: str = "active"

    @property
    def is_active(self) -> bool:
        return self.status == "active"


# Used when the platform schema does not exist yet (fresh install before `migrate`, migration tests).
IMPLICIT_PUBLIC = TenantInfo(id=None, slug=None, name="", domain="general", schema=DEFAULT_SCHEMA)


# ------------------------------------------------------------------ catalogue


class _Catalogue:
    """In-process copy of platform.tenants, refreshed every few seconds (tenants change rarely)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded_at = 0.0
        self._tenants: list[TenantInfo] = []
        self._platform = True

    def _load(self) -> None:
        from app.db.session import get_engine

        try:
            with get_engine().connect() as conn:
                rows = conn.execute(
                    text("SELECT id, slug, name, domain, schema_name, status FROM platform.tenants")
                ).all()
            self._tenants = [TenantInfo(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows]
            # An empty catalogue (platform migrated, first tenant not registered yet) behaves like none.
            self._platform = bool(rows)
        except DBAPIError as exc:
            if "does not exist" not in str(exc.orig):
                raise
            self._tenants, self._platform = [], False
        self._loaded_at = time.monotonic()

    def tenants(self) -> list[TenantInfo]:
        with self._lock:
            if time.monotonic() - self._loaded_at > _CATALOGUE_TTL_SECONDS:
                self._load()
            return list(self._tenants) if self._platform else [IMPLICIT_PUBLIC]

    def invalidate(self) -> None:
        with self._lock:
            self._loaded_at = 0.0


_catalogue = _Catalogue()


def tenants() -> list[TenantInfo]:
    return _catalogue.tenants()


def active_tenants() -> list[TenantInfo]:
    return [t for t in tenants() if t.is_active]


def invalidate_catalogue() -> None:
    _catalogue.invalidate()


def by_slug(slug: str) -> TenantInfo | None:
    return next((t for t in tenants() if t.slug == slug), None)


def by_schema(schema: str) -> TenantInfo | None:
    return next((t for t in tenants() if t.schema == schema), None)


def resolve(slug: str | None) -> TenantInfo | None:
    """The tenant named by ``slug``; without one, the only active tenant (single-firm installs)."""
    if slug:
        tenant = by_slug(slug)
        return tenant if tenant is not None and tenant.is_active else None
    active = active_tenants()
    return active[0] if len(active) == 1 else None


# ------------------------------------------------------------------ sessions


def bind_tenant(db: Session, tenant: TenantInfo | None) -> None:
    """Point ``db`` at a tenant's schema (None = unresolved: tenant tables are unreachable).

    Call before the session runs tenant queries; an open transaction in another schema is rolled back.
    """
    schema = tenant.schema if tenant is not None else UNRESOLVED_SCHEMA
    if db.info.get("tenant") == schema:
        return
    if db.in_transaction():
        db.rollback()
    forget_revisions(db)
    db.info["tenant"] = schema
    db.info["tenant_id"] = tenant.id if tenant is not None else None
    db.info["tenant_slug"] = tenant.slug if tenant is not None else None


def is_resolved(db: Session) -> bool:
    return str(db.info.get("tenant", DEFAULT_SCHEMA)) != UNRESOLVED_SCHEMA


def current_tenant(db: Session) -> TenantInfo | None:
    schema = str(db.info.get("tenant", DEFAULT_SCHEMA))
    if schema == UNRESOLVED_SCHEMA:
        return None
    return by_schema(schema) or (IMPLICIT_PUBLIC if schema == DEFAULT_SCHEMA else None)


def tenant_slug(db: Session) -> str | None:
    slug = db.info.get("tenant_slug")
    if slug:
        return str(slug)
    tenant = current_tenant(db)
    return tenant.slug if tenant is not None else None


def tenant_schema(db: Session) -> str:
    return str(db.info.get("tenant", DEFAULT_SCHEMA))


# ------------------------------------------------------------------ tokens carrying the tenant


def qualify_token(db: Session, token: str) -> str:
    """``<slug>.<token>`` for links and cookies, so the receiving request finds the tenant."""
    slug = tenant_slug(db)
    return f"{slug}.{token}" if slug else token


def split_token(value: str) -> tuple[str | None, str]:
    """(slug, token). Tokens are URL-safe base64 (no dots), so a dot always separates the tenant."""
    slug, sep, token = value.partition(".")
    if sep and SLUG.match(slug) and token:
        return slug, token
    return None, value


def bind_for_token(db: Session, value: str) -> str:
    """Bind ``db`` to the tenant a qualified token names; returns the bare token."""
    slug, token = split_token(value)
    bind_tenant(db, resolve(slug))
    return token


# ------------------------------------------------------------------ search_path per transaction


@lru_cache
def _per_transaction() -> bool:
    from app.core.config import get_settings

    return get_settings().disable_prepared_statements


def apply_search_path(connection: Connection, schema: str) -> None:
    path = search_path_for(schema)
    if _per_transaction():
        connection.exec_driver_sql(f"SET LOCAL search_path TO {path}")
        return
    pooled = connection.connection
    if pooled.info.get(_PATH_KEY) == schema:
        return
    raw: Any = pooled.dbapi_connection
    status = getattr(getattr(raw, "info", None), "transaction_status", None)
    if raw is not None and status is not None and int(status) == 0:  # psycopg TransactionStatus.IDLE
        # Outside any transaction, so a rollback cannot undo it; remembered for this connection's life.
        previous = raw.autocommit
        raw.autocommit = True
        try:
            raw.execute(f"SET search_path TO {path}")
        finally:
            raw.autocommit = previous
        pooled.info[_PATH_KEY] = schema
    else:
        connection.exec_driver_sql(f"SET LOCAL search_path TO {path}")


@event.listens_for(Session, "after_begin")
def _begin(session: Session, _transaction: Any, connection: Connection) -> None:
    apply_search_path(connection, str(session.info.get("tenant", DEFAULT_SCHEMA)))


# ------------------------------------------------------------------ user directory sync

_DIRECTORY_OPS = "directory_ops"


def _user_cls() -> type[Any]:
    from app.models import User

    return User


@event.listens_for(Session, "after_flush")
def _collect_directory_changes(session: Session, _flush: UOWTransaction) -> None:
    user_cls = _user_cls()
    ops: dict[uuid.UUID, str | None] | None = None
    for obj in session.new:
        if isinstance(obj, user_cls):
            ops = session.info.setdefault(_DIRECTORY_OPS, {})
            ops[obj.id] = obj.email
    for obj in session.dirty:
        if isinstance(obj, user_cls) and inspect(obj).attrs.email.history.has_changes():
            ops = session.info.setdefault(_DIRECTORY_OPS, {})
            ops[obj.id] = obj.email
    for obj in session.deleted:
        if isinstance(obj, user_cls):
            ops = session.info.setdefault(_DIRECTORY_OPS, {})
            ops[obj.id] = None


@event.listens_for(Session, "before_commit")
def _write_directory(session: Session) -> None:
    session.flush()
    ops: dict[uuid.UUID, str | None] | None = session.info.pop(_DIRECTORY_OPS, None)
    if not ops:
        return
    tenant = current_tenant(session)
    if tenant is None or tenant.id is None:
        return  # no platform schema yet: `migrate` backfills the directory
    conn = session.connection()
    for user_id, email in ops.items():
        if email is None:
            conn.execute(
                text("DELETE FROM platform.user_directory WHERE tenant_id = :t AND user_id = :u"),
                {"t": tenant.id, "u": user_id},
            )
        else:
            conn.execute(
                text(
                    "INSERT INTO platform.user_directory (tenant_id, user_id, email) VALUES (:t, :u, :e) "
                    "ON CONFLICT (tenant_id, user_id) DO UPDATE SET email = EXCLUDED.email"
                ),
                {"t": tenant.id, "u": user_id, "e": email},
            )


@event.listens_for(Session, "after_rollback")
def _forget_directory(session: Session) -> None:
    session.info.pop(_DIRECTORY_OPS, None)


def directory_tenants(email: str) -> list[TenantInfo]:
    """Active workspaces where ``email`` has an account."""
    if tenants() == [IMPLICIT_PUBLIC]:
        return [IMPLICIT_PUBLIC]
    from app.db.session import get_engine

    with get_engine().connect() as conn:
        ids = set(
            conn.execute(
                text("SELECT tenant_id FROM platform.user_directory WHERE email = :e"), {"e": email.lower()}
            ).scalars()
        )
    return [t for t in active_tenants() if t.id in ids]

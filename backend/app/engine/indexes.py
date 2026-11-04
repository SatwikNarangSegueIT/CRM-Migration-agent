"""Expression indexes on record fields (plan v3, section 3, "Indexes").

Fields marked indexed (filterable/sortable) get a partial expression index; unique and external-ID
fields get a partial unique index. Indexes are named "ix_rec_*" (ignored by Alembic autogenerate) and
are created with CREATE INDEX CONCURRENTLY outside a transaction when possible.
"""

from __future__ import annotations

import hashlib
import logging
import re

from sqlalchemy import Connection, Engine, text

from app.engine.meta import FieldMeta, ObjectMeta, Registry

logger = logging.getLogger("app.engine.indexes")
SAFE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
SAFE_SCHEMA = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
MAX_INDEXED_FIELDS = 25


def index_name(obj: str, field: str, unique: bool) -> str:
    base = f"ix_rec_{'u' if unique else 'f'}_{obj}_{field}"
    if len(base) <= 63:
        return base
    digest = hashlib.sha1(base.encode()).hexdigest()[:8]  # noqa: S324 - not security relevant
    return base[:54] + "_" + digest


def _expression(f: FieldMeta) -> str:
    key = f"data->>'{f.api_name}'"
    if f.type in ("number", "percent", "currency"):
        return f"(({key})::numeric)"
    if f.type == "date":
        # Immutable ISO conversion (migration c3f1d2e8a901); "::date" itself cannot be indexed.
        return f"(crm_iso_date({key}))"
    if f.type in ("text", "textarea", "email", "phone", "url"):
        return f"(lower({key}))"
    return f"(({key}))"


def index_statements(obj: ObjectMeta, f: FieldMeta, *, concurrently: bool) -> list[str]:
    if not (SAFE_NAME.match(obj.api_name) and SAFE_NAME.match(f.api_name)) or f.is_system:
        return []
    cc = "CONCURRENTLY " if concurrently else ""
    where = f"WHERE object_api_name = '{obj.api_name}' AND NOT is_deleted"
    stmts: list[str] = []
    if f.is_unique or f.external_id:
        stmts.append(
            f"CREATE UNIQUE INDEX {cc}IF NOT EXISTS {index_name(obj.api_name, f.api_name, True)} "
            f"ON records ((lower(data->>'{f.api_name}'))) {where}"
        )
    elif f.indexed:
        stmts.append(
            f"CREATE INDEX {cc}IF NOT EXISTS {index_name(obj.api_name, f.api_name, False)} "
            f"ON records ({_expression(f)}) {where}"
        )
    return stmts


def drop_statements(obj: str, field: str, *, concurrently: bool) -> list[str]:
    cc = "CONCURRENTLY " if concurrently else ""
    return [f"DROP INDEX {cc}IF EXISTS {index_name(obj, field, u)}" for u in (True, False)]


def sync_indexes(conn: Connection, registry: Registry) -> None:
    """Create every missing index inside the current transaction (migrations, tests)."""
    for obj in registry.objects.values():
        for f in obj.data_fields:
            for stmt in index_statements(obj, f, concurrently=False):
                conn.execute(text(stmt))


def schedule_index_ddl(statements: list[str], tenant: str = "public") -> None:
    """Hand index DDL to the worker. CREATE INDEX CONCURRENTLY waits for every open transaction, so it
    must never run inside a web request. `app.cli sync-indexes` (run on deploy) creates anything missed."""
    if not statements:
        return
    try:
        from app.worker.tasks import apply_index_ddl

        apply_index_ddl.delay(statements, tenant)
    except Exception:
        logger.warning("Could not queue index DDL; run 'sync-indexes'", extra={"statements": statements})


def qualify(statement: str, schema: str) -> str:
    """Name the tenant schema in index DDL (it runs outside a transaction, so search_path can't be used)."""
    if not SAFE_SCHEMA.match(schema):
        raise ValueError(f"Invalid schema name: {schema!r}")
    statement = statement.replace(" ON records ", f' ON "{schema}".records ')
    return re.sub(r"IF EXISTS (ix_rec_\w+)", rf'IF EXISTS "{schema}".\1', statement)


def apply_concurrently(engine: Engine, statements: list[str], schema: str = "public") -> None:
    """Run index DDL outside a transaction so writes are not blocked. Failures are logged, not raised:
    a missing index only costs performance; uniqueness is also checked by the record engine."""
    if not statements:
        return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for stmt in statements:
            try:
                conn.execute(text(qualify(stmt, schema)))
            except Exception:
                logger.exception("Index statement failed", extra={"statement": stmt})

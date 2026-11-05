"""Platform and tenant migrations, and tenant creation (plan v4, section 3, "Migrations").

``python -m app.cli migrate`` runs the platform migrations once, then the tenant migrations in every
tenant schema. The pre-tenancy ``public`` schema is registered as the first tenant, so no data moves.
"""

from __future__ import annotations

import argparse
import re
import secrets
import threading
import uuid
from pathlib import Path

from alembic.config import Config
from sqlalchemy import Connection, text

from alembic import command
from app.core.config import get_settings
from app.db.session import build_engine
from app.tenancy import DEFAULT_SCHEMA, SCHEMA_NAME, SLUG, invalidate_catalogue

BACKEND_DIR = Path(__file__).resolve().parents[2]
RESERVED_SLUGS = frozenset(
    {"admin", "api", "app", "www", "platform", "public", "login", "signup", "support", "help", "status"}
)


def _config(script: str, *x: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / script))
    cfg.cmd_opts = argparse.Namespace(x=list(x))
    cfg.attributes["configure_logger"] = False  # keep the app's logging (alembic/env.py)
    return cfg


def _url_args(url: str | None) -> list[str]:
    return [f"url={url}"] if url else []


# Alembic's `op` and `context` are process-wide, so two migrations running in one process at once (a
# sign-up building a workspace while the API refills the warm pool) would run each other's statements in the
# wrong transaction. One migration at a time per process; separate processes are independent.
_ALEMBIC_LOCK = threading.RLock()


def migrate_platform(url: str | None = None) -> None:
    with _ALEMBIC_LOCK:
        command.upgrade(_config("alembic_platform", *_url_args(url)), "head")


def migrate_tenant(schema: str, url: str | None = None, revision: str = "head") -> None:
    if not SCHEMA_NAME.match(schema):
        raise ValueError(f"Invalid schema name: {schema!r}")
    with _ALEMBIC_LOCK:
        command.upgrade(_config("alembic", f"schema={schema}", *_url_args(url)), revision)


def _engine(url: str | None):  # type: ignore[no-untyped-def]
    return build_engine(get_settings(), url=url or get_settings().migration_database_url, null_pool=True)


def tenant_schemas(url: str | None = None) -> list[str]:
    engine = _engine(url)
    try:
        with engine.connect() as conn:
            return list(
                conn.execute(
                    text(
                        "SELECT schema_name FROM platform.tenants "
                        "WHERE status <> 'deleted' ORDER BY created_at"
                    )
                ).scalars()
            )
    finally:
        engine.dispose()


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:32].strip("-")
    return slug if len(slug) >= 2 else "firm"


def ensure_first_tenant(url: str | None = None, *, slug: str = "main", domain: str = "migration") -> None:
    """Register the existing public schema as a tenant and copy its users into the directory."""
    engine = _engine(url)
    try:
        with engine.begin() as conn:
            exists = conn.execute(
                text("SELECT id FROM platform.tenants WHERE schema_name = :s"), {"s": DEFAULT_SCHEMA}
            ).scalar()
            if exists is None:
                name = (
                    conn.execute(
                        text(
                            "SELECT NULLIF(value->>'legal_name', '') "
                            "FROM public.org_settings WHERE key = 'company'"
                        )
                    ).scalar()
                    if conn.execute(text("SELECT to_regclass('public.org_settings')")).scalar()
                    else None
                )
                exists = uuid.uuid4()
                conn.execute(
                    text(
                        "INSERT INTO platform.tenants "
                        "(id, slug, name, domain, schema_name, status, verified_at) "
                        "VALUES (:id, :slug, :name, :domain, 'public', 'active', now())"
                    ),
                    {"id": exists, "slug": slug, "name": name or "My firm", "domain": domain},
                )
            if conn.execute(text("SELECT to_regclass('public.users')")).scalar():
                conn.execute(
                    text(
                        "INSERT INTO platform.user_directory (tenant_id, user_id, email) "
                        "SELECT :t, id, email FROM public.users ON CONFLICT DO NOTHING"
                    ),
                    {"t": exists},
                )
    finally:
        engine.dispose()
    invalidate_catalogue()


def migrate_all(url: str | None = None) -> list[str]:
    migrate_platform(url)
    migrate_tenant(DEFAULT_SCHEMA, url)
    ensure_first_tenant(url)
    schemas = tenant_schemas(url)
    for schema in [*schemas, *warm_schemas(url)]:
        if schema != DEFAULT_SCHEMA:
            migrate_tenant(schema, url)
    return schemas


def _unique_slug(conn: Connection, wanted: str) -> str:
    slug = wanted if SLUG.match(wanted) and wanted not in RESERVED_SLUGS else slugify(wanted)
    if slug in RESERVED_SLUGS:
        slug = f"{slug}-firm"
    while conn.execute(text("SELECT 1 FROM platform.tenants WHERE slug = :s"), {"s": slug}).scalar():
        slug = f"{slug[:34]}-{secrets.token_hex(2)}"
    return slug


def _new_schema_name() -> str:
    return f"t_{secrets.token_hex(6)}"


# Ready-made schemas in platform.warm_schemas: "t_<12 hex>" is a bare workspace; "t_<domain>_<hex>" is one
# already set up for a profession, so sign-up only names it for the firm and adds the administrator.
_BARE = "^t_[0-9a-f]{12}$"


def _ready_pattern(domain: str) -> str:
    return f"^t_{re.escape(domain)}_[0-9a-f]+$"


def ready_schemas(domain: str, url: str | None = None) -> list[str]:
    engine = _engine(url)
    try:
        with engine.connect() as conn:
            return list(
                conn.execute(
                    text("SELECT schema_name FROM platform.warm_schemas WHERE schema_name ~ :p"),
                    {"p": _ready_pattern(domain)},
                ).scalars()
            )
    finally:
        engine.dispose()


def is_ready_made(schema: str, domain: str | None) -> bool:
    """Whether ``schema`` came from the profession's ready-made pool (already set up for ``domain``)."""
    return bool(domain) and re.match(_ready_pattern(str(domain)), schema) is not None


def build_schema(url: str | None = None) -> str:
    """Create and migrate an unassigned tenant schema (shipped defaults included)."""
    schema = _new_schema_name()
    migrate_tenant(schema, url)
    return schema


def warm_schemas(url: str | None = None) -> list[str]:
    engine = _engine(url)
    try:
        with engine.connect() as conn:
            return list(conn.execute(text("SELECT schema_name FROM platform.warm_schemas")).scalars())
    finally:
        engine.dispose()


def _bare_schemas(url: str | None = None) -> list[str]:
    return [s for s in warm_schemas(url) if re.match(_BARE, s)]


_WARM_POOL_LOCK = 72_410_001  # pg advisory lock id: one builder at a time across API and worker processes


def fill_warm_pool(size: int, url: str | None = None) -> int:
    """Keep ``size`` pre-built schemas ready so sign-up is instant. Returns how many were built.

    Only one process builds at a time: a transaction-level advisory lock, held by an open transaction for
    the whole build, so it also works through PgBouncer (a session-level lock could be released on another
    server connection and never come free). Others return 0 straight away.
    """
    built = 0
    engine = _engine(url)
    try:
        with engine.begin() as lock_conn:
            got = lock_conn.execute(
                text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": _WARM_POOL_LOCK}
            ).scalar()
            if not got:
                return 0
            while len(_bare_schemas(url)) < size:
                schema = build_schema(url)
                with engine.begin() as conn:
                    conn.execute(
                        text("INSERT INTO platform.warm_schemas (schema_name) VALUES (:s)"), {"s": schema}
                    )
                built += 1
    finally:
        engine.dispose()
    return built


_READY_POOL_LOCK = 72_410_002


def build_ready_schema(domain: str, url: str | None = None) -> str:
    """A schema migrated and set up for ``domain`` (pack, layouts, wording, starter records), not yet
    anyone's workspace. Doing this ahead of time is what makes sign-up quick: it's hundreds of statements."""
    from sqlalchemy.orm import Session

    from app.domains import apply_domain
    from app.tenancy import TenantInfo, bind_tenant

    schema = f"t_{domain}_{secrets.token_hex(5)}"
    migrate_tenant(schema, url)
    engine = _engine(url)
    try:
        with Session(engine) as db:
            bind_tenant(db, TenantInfo(id=uuid.uuid4(), slug=None, name="", domain=domain, schema=schema))
            apply_domain(db, domain, None)
            db.commit()
    except Exception:
        _drop_schema(engine, schema)
        raise
    finally:
        engine.dispose()
    return schema


def fill_ready_pool(per_domain: int, url: str | None = None) -> int:
    """Keep ``per_domain`` workspaces ready for each profession. One builder at a time (advisory lock)."""
    from app.domains import DOMAINS

    built = 0
    engine = _engine(url)
    try:
        with engine.begin() as lock_conn:
            got = lock_conn.execute(
                text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": _READY_POOL_LOCK}
            ).scalar()
            if not got:
                return 0
            for key, spec in DOMAINS.items():
                if spec.pack_key is None:
                    continue
                while len(ready_schemas(key, url)) < per_domain:
                    schema = build_ready_schema(key, url)
                    with engine.begin() as conn:
                        conn.execute(
                            text("INSERT INTO platform.warm_schemas (schema_name) VALUES (:s)"),
                            {"s": schema},
                        )
                    built += 1
    finally:
        engine.dispose()
    return built


def refill_warm_pool_soon() -> None:
    """Top up the warm pools in a background thread of this process (no worker needed)."""
    import logging
    import threading

    settings = get_settings()
    size, per_domain = settings.signup_warm_pool_size, settings.signup_ready_per_domain
    if (size <= 0 and per_domain <= 0) or settings.is_serverless:
        return  # serverless: a thread wouldn't finish; the "maintain" scheduled job refills the pools

    def run() -> None:
        try:
            if per_domain > 0:
                fill_ready_pool(per_domain)  # first: these are what make a sign-up quick
            if size > 0:
                fill_warm_pool(size)
        except Exception:
            logging.getLogger("app.signup").exception("Could not refill the warm pool")

    threading.Thread(target=run, name="warm-pool", daemon=True).start()


def _take_warm_schema(conn: Connection, pattern: str = _BARE) -> str | None:
    return conn.execute(
        text(
            "DELETE FROM platform.warm_schemas WHERE schema_name = ("
            "SELECT schema_name FROM platform.warm_schemas WHERE schema_name ~ :p ORDER BY created_at "
            "LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING schema_name"
        ),
        {"p": pattern},
    ).scalar()


def _claim_warm_schema(engine, domain: str | None = None) -> str | None:  # type: ignore[no-untyped-def]
    """A ready-made workspace for the profession if there is one, else a bare pre-built one."""
    with engine.begin() as conn:
        ready = _take_warm_schema(conn, _ready_pattern(domain)) if domain else None
        return ready or _take_warm_schema(conn)


def _drop_schema(engine, schema: str) -> None:  # type: ignore[no-untyped-def]
    if SCHEMA_NAME.match(schema) and schema != DEFAULT_SCHEMA:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def create_tenant(
    name: str,
    domain: str,
    *,
    slug: str | None = None,
    url: str | None = None,
    use_warm_pool: bool = True,
) -> tuple[uuid.UUID, str, str]:
    """Create a firm with its own schema (warm pool first). Returns (id, slug, schema).

    The schema is ready before the firm is registered, so a failure never leaves a half-built workspace in
    the catalogue.
    """
    tenant_id = uuid.uuid4()
    engine = _engine(url)
    try:
        schema = _claim_warm_schema(engine, domain) if use_warm_pool else None
        if schema is None:
            with _ALEMBIC_LOCK:
                # While waiting, this process may have finished building a ready-made one.
                schema = _claim_warm_schema(engine) if use_warm_pool else None
                if schema is None:
                    schema = _new_schema_name()
                    try:
                        migrate_tenant(schema, url)
                    except Exception:
                        _drop_schema(engine, schema)
                        raise
        try:
            with engine.begin() as conn:
                slug = _unique_slug(conn, slug or slugify(name))
                conn.execute(
                    text(
                        "INSERT INTO platform.tenants (id, slug, name, domain, schema_name, status) "
                        "VALUES (:id, :slug, :name, :domain, :schema, 'active')"
                    ),
                    {"id": tenant_id, "slug": slug, "name": name, "domain": domain, "schema": schema},
                )
        except Exception:
            _drop_schema(engine, schema)
            raise
    finally:
        engine.dispose()
    invalidate_catalogue()
    return tenant_id, slug, schema


def drop_tenant(schema: str, url: str | None = None) -> None:
    """Permanently delete a tenant's schema and catalogue entry (tests and account closure)."""
    if not SCHEMA_NAME.match(schema) or schema == DEFAULT_SCHEMA:
        raise ValueError(f"Refusing to drop schema {schema!r}")
    engine = _engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            conn.execute(text("DELETE FROM platform.tenants WHERE schema_name = :s"), {"s": schema})
            conn.execute(text("DELETE FROM platform.warm_schemas WHERE schema_name = :s"), {"s": schema})
    finally:
        engine.dispose()
    invalidate_catalogue()

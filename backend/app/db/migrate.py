"""Platform and tenant migrations, and tenant creation (plan v4, section 3, "Migrations").

``python -m app.cli migrate`` runs the platform migrations once, then the tenant migrations in every
tenant schema. The pre-tenancy ``public`` schema is registered as the first tenant, so no data moves.
"""

from __future__ import annotations

import argparse
import re
import secrets
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
    return cfg


def _url_args(url: str | None) -> list[str]:
    return [f"url={url}"] if url else []


def migrate_platform(url: str | None = None) -> None:
    command.upgrade(_config("alembic_platform", *_url_args(url)), "head")


def migrate_tenant(schema: str, url: str | None = None, revision: str = "head") -> None:
    if not SCHEMA_NAME.match(schema):
        raise ValueError(f"Invalid schema name: {schema!r}")
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


def fill_warm_pool(size: int, url: str | None = None) -> int:
    """Keep ``size`` pre-built schemas ready so sign-up is instant. Returns how many were built."""
    built = 0
    while len(warm_schemas(url)) < size:
        schema = build_schema(url)
        engine = _engine(url)
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO platform.warm_schemas (schema_name) VALUES (:s)"), {"s": schema}
                )
        finally:
            engine.dispose()
        built += 1
    return built


def _take_warm_schema(conn: Connection) -> str | None:
    return conn.execute(
        text(
            "DELETE FROM platform.warm_schemas WHERE schema_name = ("
            "SELECT schema_name FROM platform.warm_schemas ORDER BY created_at "
            "LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING schema_name"
        )
    ).scalar()


def create_tenant(
    name: str,
    domain: str,
    *,
    slug: str | None = None,
    url: str | None = None,
    use_warm_pool: bool = True,
) -> tuple[uuid.UUID, str, str]:
    """Create a firm with its own schema (warm pool first). Returns (id, slug, schema)."""
    tenant_id = uuid.uuid4()
    engine = _engine(url)
    try:
        with engine.begin() as conn:
            schema = _take_warm_schema(conn) if use_warm_pool else None
            slug = _unique_slug(conn, slug or slugify(name))
            conn.execute(
                text(
                    "INSERT INTO platform.tenants (id, slug, name, domain, schema_name, status) "
                    "VALUES (:id, :slug, :name, :domain, :schema, :status)"
                ),
                {
                    "id": tenant_id,
                    "slug": slug,
                    "name": name,
                    "domain": domain,
                    "schema": schema or _new_schema_name(),
                    "status": "active" if schema else "provisioning",
                },
            )
            if schema is None:
                schema = conn.execute(
                    text("SELECT schema_name FROM platform.tenants WHERE id = :id"), {"id": tenant_id}
                ).scalar_one()
                warm = False
            else:
                warm = True
        if not warm:
            migrate_tenant(schema, url)
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE platform.tenants SET status = 'active' WHERE id = :id"), {"id": tenant_id}
                )
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

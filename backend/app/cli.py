"""Management commands.

uv run python -m app.cli create-admin --email you@agency.com.au --name "Your Name"
uv run python -m app.cli seed-demo            # development/test only: demo users + sample data
uv run python -m app.cli sync-indexes         # after each deploy
uv run python -m app.cli seed-load --count 1000000   # disposable databases only (load tests)
uv run python -m app.cli migrate              # platform + every tenant schema (run on deploy)
uv run python -m app.cli create-tenant --name "Smith Lawyers" --domain legal
uv run python -m app.cli list-tenants

Commands that touch CRM data take --tenant <workspace address> (default: the first workspace).
"""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password, password_policy_errors
from app.core.config import get_settings
from app.db.session import get_sessionmaker as _sessionmaker
from app.models import Profile, Role, User
from app.security.policy import SYSTEM_ADMIN_KEY
from app.services import audit
from app.services.audit import AuditAction

_TENANT: str | None = None


def get_sessionmaker() -> Callable[[], Session]:
    """Sessions bound to the --tenant workspace (default: the first one)."""
    from app.tenancy import IMPLICIT_PUBLIC, bind_tenant, by_schema, by_slug

    maker = _sessionmaker()

    def factory() -> Session:
        db = maker()
        tenant = by_slug(_TENANT) if _TENANT else (by_schema("public") or IMPLICIT_PUBLIC)
        if tenant is None:
            raise SystemExit(f"Unknown workspace: {_TENANT}")
        bind_tenant(db, tenant)
        return db

    return factory


DEMO_PASSWORD = "Demo-Password-2026!"  # noqa: S105 - documented development-only credential
# One demo user per default staff profile (plan v3 section 10): email, name, profile key, hierarchy role key.
DEMO_USERS: list[tuple[str, str, str, str | None]] = [
    ("admin@demo.example.com", "Alex Admin", "system_administrator", "ceo"),
    ("salesmanager@demo.example.com", "Morgan Manager", "sales_manager", "sales_manager"),
    ("sales@demo.example.com", "Riley Rep", "sales_representative", "sales_representative"),
    ("service@demo.example.com", "Casey Service", "service_agent", "service_agent"),
    ("marketing@demo.example.com", "Jordan Marketing", "marketing_user", "marketing_user"),
    ("finance@demo.example.com", "Taylor Finance", "finance", "finance_officer"),
    ("auditor@demo.example.com", "Avery Auditor", "read_only", None),
]


def create_admin(email: str, name: str, password: str | None) -> int:
    email = email.strip().lower()
    if password is None:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match.", file=sys.stderr)
            return 1
    errors = password_policy_errors(password, email=email, name=name)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    with get_sessionmaker()() as db:
        if db.scalar(select(User.id).where(User.email == email)) is not None:
            print(f"A user with e-mail {email} already exists.", file=sys.stderr)
            return 1
        admin_profile = db.scalar(select(Profile).where(Profile.key == SYSTEM_ADMIN_KEY))
        if admin_profile is None:
            print("System Administrator profile not found. Run migrations first.", file=sys.stderr)
            return 1
        user = User(
            email=email,
            name=name.strip(),
            profile_id=admin_profile.id,
            password_hash=hash_password(password),
        )
        db.add(user)
        db.flush()
        audit.record(
            db,
            action=AuditAction.CREATE,
            entity_type="user",
            entity_id=user.id,
            actor_id=None,
            summary=f"Administrator {email} created from the command line",
        )
        db.commit()
    print(f"Administrator {email} created. MFA set-up will be requested at first sign-in.")
    return 0


def seed_demo() -> int:
    settings = get_settings()
    if settings.app_env not in ("development", "test"):
        print("seed-demo is only allowed when APP_ENV is development or test.", file=sys.stderr)
        return 1
    created = 0
    password_hash = hash_password(DEMO_PASSWORD)
    with get_sessionmaker()() as db:
        profiles_by_key = {p.key: p for p in db.scalars(select(Profile)).all() if p.key}
        roles_by_key = {r.key: r for r in db.scalars(select(Role)).all() if r.key}
        for email, name, profile_key, role_key in DEMO_USERS:
            if db.scalar(select(User.id).where(User.email == email)) is not None:
                continue
            profile = profiles_by_key.get(profile_key)
            if profile is None:
                print(f"Profile {profile_key} not found for {email}, skipping.", file=sys.stderr)
                continue
            user = User(
                email=email,
                name=name,
                profile_id=profile.id,
                role_id=roles_by_key[role_key].id if role_key and role_key in roles_by_key else None,
                password_hash=password_hash,
            )
            db.add(user)
            db.flush()
            audit.record(
                db,
                action=AuditAction.CREATE,
                entity_type="user",
                entity_id=user.id,
                actor_id=None,
                summary=f"Demo user {email} seeded",
            )
            created += 1
        db.commit()
        import app.apps  # noqa: F401 - object hooks (prices, totals, SLAs) must run for sample data
        from app.demo_data import seed_sample_data

        records = seed_sample_data(db)
    print(
        f"Seeded {created} demo user(s) and {records} sample record(s). "
        f"Password for all users: {DEMO_PASSWORD}"
    )
    return 0


def seed_load(count: int, object_api_name: str) -> int:
    """Synthetic rows for load tests. Refuses to run in staging/production."""
    settings = get_settings()
    if settings.app_env not in ("development", "test"):
        print("seed-load is only allowed when APP_ENV is development or test.", file=sys.stderr)
        return 1
    from app.demo_data import seed_load_data

    with get_sessionmaker()() as db:
        owners = list(db.scalars(select(User.id).where(User.is_active.is_(True))))
        if not owners:
            print("Create users first (seed-demo).", file=sys.stderr)
            return 1
        n = seed_load_data(db, object_api_name, count, owners)
    print(f"Inserted {n} {object_api_name} row(s). Run ANALYZE records; before measuring.")
    return 0


def sync_indexes() -> int:
    """Create every missing expression index for indexed / unique fields in every tenant (after deploys)."""
    global _TENANT
    from app.db.session import get_engine
    from app.engine.indexes import apply_concurrently, index_statements
    from app.engine.meta import load_registry
    from app.tenancy import active_tenants

    for tenant in active_tenants():
        _TENANT = tenant.slug
        with get_sessionmaker()() as db:
            registry = load_registry(db)
        statements = [
            stmt
            for obj in registry.objects.values()
            for f in obj.data_fields
            for stmt in index_statements(obj, f, concurrently=True)
        ]
        apply_concurrently(get_engine(), statements, tenant.schema)
        print(f"{tenant.slug or tenant.schema}: checked {len(statements)} index(es).")
    return 0


def refresh_domain_layouts() -> int:
    """Re-apply profession related lists and forms in every domain workspace (safe to repeat)."""
    from app.domains import upgrade_all_domain_workspaces

    for workspace, changed in upgrade_all_domain_workspaces(force=True).items():
        print(f"{workspace}: {changed} change(s).")
    return 0


def migrate() -> int:
    from app.db.migrate import migrate_all

    schemas = migrate_all()
    print(f"Platform and {len(schemas)} tenant schema(s) are up to date.")
    return 0


def create_tenant_cmd(name: str, domain: str, slug: str | None) -> int:
    from app.db.migrate import create_tenant

    _, slug, schema = create_tenant(name, domain, slug=slug)
    print(f"Created workspace {slug} ({schema}). Add an administrator with: create-admin --tenant {slug}")
    return 0


def list_tenants() -> int:
    from app.tenancy import tenants

    for t in tenants():
        print(f"{t.slug or '-':<30} {t.domain:<12} {t.status:<12} {t.schema:<20} {t.name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    global _TENANT
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    parser.add_argument("--tenant", help="Workspace address (default: the first workspace)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="Run platform and tenant migrations")
    p_tenant = sub.add_parser("create-tenant", help="Create a workspace (firm) with its own schema")
    p_tenant.add_argument("--name", required=True)
    p_tenant.add_argument(
        "--domain", default="general", choices=["legal", "migration", "accounting", "lending", "general"]
    )
    p_tenant.add_argument("--slug")
    sub.add_parser("list-tenants", help="List workspaces")
    p_admin = sub.add_parser("create-admin", help="Create an administrator account")
    p_admin.add_argument("--email", required=True)
    p_admin.add_argument("--name", required=True)
    p_admin.add_argument("--password", help="Omit to be prompted (recommended)")
    sub.add_parser("seed-demo", help="Create one demo user per default staff profile (development only)")
    sub.add_parser("sync-indexes", help="Create missing field indexes (run after deploys)")
    sub.add_parser(
        "refresh-domain-layouts", help="Re-apply profession related lists in every domain workspace"
    )
    p_load = sub.add_parser("seed-load", help="Insert synthetic rows for load tests (development only)")
    p_load.add_argument("--count", type=int, default=100_000)
    p_load.add_argument("--object", default="account")
    args = parser.parse_args(argv)
    _TENANT = args.tenant
    if args.command == "migrate":
        return migrate()
    if args.command == "create-tenant":
        return create_tenant_cmd(args.name, args.domain, args.slug)
    if args.command == "list-tenants":
        return list_tenants()
    if args.command == "create-admin":
        return create_admin(args.email, args.name, args.password)
    if args.command == "sync-indexes":
        return sync_indexes()
    if args.command == "refresh-domain-layouts":
        return refresh_domain_layouts()
    if args.command == "seed-load":
        return seed_load(args.count, args.object)
    return seed_demo()


if __name__ == "__main__":
    raise SystemExit(main())

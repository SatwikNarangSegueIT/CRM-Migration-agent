"""Management commands.

uv run python -m app.cli create-admin --email you@agency.com.au --name "Your Name"
uv run python -m app.cli seed-demo            # development/test only
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from app.auth.security import hash_password, password_policy_errors
from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.models import Profile, Role, User
from app.security.policy import SYSTEM_ADMIN_KEY
from app.services import audit
from app.services.audit import AuditAction

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
    print(f"Seeded {created} demo user(s). Password for all: {DEMO_PASSWORD}")
    return 0


def sync_indexes() -> int:
    """Create every missing expression index for indexed / unique fields (run after each deploy)."""
    from app.db.session import get_engine
    from app.engine.indexes import apply_concurrently, index_statements
    from app.engine.meta import load_registry

    with get_sessionmaker()() as db:
        registry = load_registry(db)
    statements = [
        stmt
        for obj in registry.objects.values()
        for f in obj.data_fields
        for stmt in index_statements(obj, f, concurrently=True)
    ]
    apply_concurrently(get_engine(), statements)
    print(f"Checked {len(statements)} index(es).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p_admin = sub.add_parser("create-admin", help="Create an administrator account")
    p_admin.add_argument("--email", required=True)
    p_admin.add_argument("--name", required=True)
    p_admin.add_argument("--password", help="Omit to be prompted (recommended)")
    sub.add_parser("seed-demo", help="Create one demo user per default staff profile (development only)")
    sub.add_parser("sync-indexes", help="Create missing field indexes (run after deploys)")
    args = parser.parse_args(argv)
    if args.command == "create-admin":
        return create_admin(args.email, args.name, args.password)
    if args.command == "sync-indexes":
        return sync_indexes()
    return seed_demo()


if __name__ == "__main__":
    raise SystemExit(main())

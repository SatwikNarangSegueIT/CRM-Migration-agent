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
from app.models import User
from app.permissions.matrix import Role
from app.services import audit
from app.services.audit import AuditAction

DEMO_PASSWORD = "Demo-Password-2026!"  # noqa: S105 - documented development-only credential
DEMO_USERS: list[tuple[str, str, Role, str | None]] = [
    ("admin@demo.example.com", "Alex Admin", Role.ADMIN, None),
    ("manager@demo.example.com", "Morgan Manager", Role.PRACTICE_MANAGER, None),
    ("agent@demo.example.com", "Riley Agent", Role.MIGRATION_AGENT, "1234567"),
    ("officer@demo.example.com", "Casey Officer", Role.CASE_OFFICER, None),
    ("intake@demo.example.com", "Jordan Intake", Role.INTAKE_CONSULTANT, None),
    ("accounts@demo.example.com", "Taylor Accounts", Role.ACCOUNTS, None),
    ("auditor@demo.example.com", "Avery Auditor", Role.AUDITOR, None),
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
        user = User(
            email=email, name=name.strip(), role=Role.ADMIN.value, password_hash=hash_password(password)
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
        for email, name, role, mara in DEMO_USERS:
            if db.scalar(select(User.id).where(User.email == email)) is not None:
                continue
            user = User(
                email=email, name=name, role=role.value, password_hash=password_hash, mara_number=mara
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p_admin = sub.add_parser("create-admin", help="Create an administrator account")
    p_admin.add_argument("--email", required=True)
    p_admin.add_argument("--name", required=True)
    p_admin.add_argument("--password", help="Omit to be prompted (recommended)")
    sub.add_parser("seed-demo", help="Create one demo user per staff role (development only)")
    args = parser.parse_args(argv)
    if args.command == "create-admin":
        return create_admin(args.email, args.name, args.password)
    return seed_demo()


if __name__ == "__main__":
    raise SystemExit(main())

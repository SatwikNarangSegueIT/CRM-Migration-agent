from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient

# ---- Test environment (set before the app reads its settings; overrides backend/.env) ----
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://crm:crm@localhost:5432/crm_test")
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": TEST_DATABASE_URL,
        "DATABASE_URL_DIRECT": TEST_DATABASE_URL,
        "REDIS_URL": TEST_REDIS_URL,
        "MFA_REQUIRED_FOR_STAFF": "true",
        "RATE_LIMIT_ENABLED": "false",
        "SIGNUP_WARM_POOL_SIZE": "0",
        "PASSWORD_BREACH_CHECK": "false",
        # Existing tests exercise the e-mail confirmation flow; the instant mode has its own tests.
        "SIGNUP_EMAIL_VERIFICATION": "required",
        "EMAIL_DELIVERY": "auto",
        "EMAIL_BACKEND": "console",
        "LOG_JSON": "true",
        "LOG_LEVEL": "WARNING",
        "PUBLIC_APP_URL": "http://localhost:5173",
    }
)

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.core.cache import clear_all as clear_all_caches  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.core.redis_client import get_redis  # noqa: E402
from app.db.seeds import apply_seeds  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.engine.meta import invalidate_cache  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, User  # noqa: E402
from app.security.seed_v1 import stable_id  # noqa: E402
from app.tenancy import invalidate_catalogue  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
PASSWORD = "Correct-Horse-Battery-9"


def run_alembic(*args: str) -> str:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", "-x", f"url={TEST_DATABASE_URL}", *args],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout + result.stderr


@pytest.fixture(scope="session", autouse=True)
def _migrated_database() -> None:
    from app.db.migrate import migrate_all

    migrate_all(TEST_DATABASE_URL)


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture(autouse=True)
def _clean_state() -> None:
    """Empty every table (TRUNCATE bypasses the audit-log row trigger), re-apply the shipped defaults
    (profiles, roles, metadata) and empty the Redis test DB."""
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with get_sessionmaker()() as db:
        # Workspaces created by a test are dropped; the public schema is the first workspace.
        for schema in db.scalars(
            text("SELECT schema_name FROM platform.tenants WHERE schema_name <> 'public'")
        ):
            db.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        for schema in db.scalars(text("SELECT schema_name FROM platform.warm_schemas")):
            db.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        db.execute(text("DELETE FROM platform.warm_schemas"))
        db.execute(text("DELETE FROM platform.signup_requests"))
        db.execute(text("DELETE FROM platform.tenants WHERE schema_name <> 'public'"))
        db.execute(text("DELETE FROM platform.user_directory"))
        db.execute(text("DELETE FROM platform.settings"))
        db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        apply_seeds(db.connection())
        # A firm that issues tax invoices has an ABN (tests that need it missing clear it).
        db.execute(
            text(
                "UPDATE org_settings SET value = jsonb_set(value, '{abn}', '\"51 824 753 556\"') "
                "WHERE key = 'company'"
            )
        )
        db.commit()
    invalidate_cache()
    invalidate_catalogue()
    # TRUNCATE resets the revision counters, so revision-keyed caches must be emptied too.
    clear_all_caches()
    get_redis().flushdb()
    from app.services.mail_settings import forget_cached
    from app.worker.dispatch import forget_worker_check

    forget_cached()
    forget_worker_check()


@pytest.fixture
def db() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session


@dataclass
class Outbox:
    messages: list[tuple[str, str, str]] = field(default_factory=list)

    def send(self, to: str, subject: str, body: str, **_options: object) -> None:
        self.messages.append((to, subject, body))

    def token_for(self, to: str) -> str:
        for recipient, _, body in reversed(self.messages):
            if recipient == to:
                return body.split("#token=", 1)[1].split()[0]
        raise AssertionError(f"No e-mail sent to {to}")


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> Outbox:
    box = Outbox()
    monkeypatch.setattr("app.routers.auth.queue_email", box.send)
    monkeypatch.setattr("app.routers.admin_users.queue_email", box.send)
    monkeypatch.setattr("app.routers.portal.queue_email", box.send)
    monkeypatch.setattr("app.routers.signup.queue_email", box.send)
    # E-mails sent once a change is saved (a service agreement sent to the client, a reminder).
    monkeypatch.setattr("app.services.email.queue_email", box.send)
    return box


@pytest.fixture
def client(settings: Settings, outbox: Outbox) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c


def make_user(
    db: Session,
    *,
    profile: str = "system_administrator",
    role: str | None = None,
    email: str | None = None,
    name: str = "Test User",
    password: str | None = PASSWORD,
    mfa_secret: str | None = None,
    is_active: bool = True,
    mara_number: str | None = None,
) -> User:
    from app.auth.security import encrypt_field

    user = User(
        email=email or f"{profile}-{uuid.uuid4().hex[:8]}@example.com",
        name=name,
        profile_id=stable_id("profile", profile),
        role_id=stable_id("role", role) if role else None,
        password_hash=hash_password(password) if password else None,
        is_active=is_active,
        mfa_enabled=mfa_secret is not None,
        mfa_secret_encrypted=encrypt_field(mfa_secret) if mfa_secret else None,
        mara_number=mara_number,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_csrf(client: TestClient) -> None:
    client.headers["X-CSRF-Token"] = client.cookies.get("crm_csrf") or ""


def login(client: TestClient, email: str, password: str = PASSWORD, *, mfa_secret: str | None = None) -> str:
    """Sign in (completing MFA when a secret is given). Returns the final login state."""
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    state: str = r.json()["state"]
    set_csrf(client)
    if state == "mfa_required" and mfa_secret:
        r = client.post("/api/v1/auth/mfa/verify", json={"code": pyotp.TOTP(mfa_secret).now()})
        assert r.status_code == 200, r.text
        set_csrf(client)
        state = "authenticated"
    return state


@pytest.fixture
def no_mfa(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    """Disable mandatory staff MFA (most API tests don't exercise MFA)."""
    monkeypatch.setattr(settings, "mfa_required_for_staff", False)


@pytest.fixture
def admin_client(client: TestClient, db: Session, no_mfa: None) -> TestClient:
    admin = make_user(db, email="admin@example.com", name="Ada Admin")
    login(client, admin.email)
    return client


def client_as(
    settings: Settings, outbox: Outbox, db: Session, profile: str, role: str | None = None
) -> TestClient:
    """A separate signed-in client for a user with `profile` (call within a test using no_mfa)."""
    user = make_user(db, profile=profile, role=role)
    c = TestClient(create_app(settings))
    login(c, user.email)
    return c

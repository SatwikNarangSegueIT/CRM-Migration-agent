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
        "EMAIL_BACKEND": "console",
        "LOG_JSON": "true",
        "LOG_LEVEL": "WARNING",
        "PUBLIC_APP_URL": "http://localhost:5173",
    }
)

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.core.redis_client import get_redis  # noqa: E402
from app.db.seeds import apply_seeds  # noqa: E402
from app.engine.meta import invalidate_cache  # noqa: E402
from app.db.session import get_sessionmaker  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, User  # noqa: E402
from app.security.seed_v1 import stable_id  # noqa: E402

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
    run_alembic("upgrade", "head")


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture(autouse=True)
def _clean_state() -> None:
    """Empty every table (TRUNCATE bypasses the audit-log row trigger), re-apply the shipped defaults
    (profiles, roles, metadata) and empty the Redis test DB."""
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with get_sessionmaker()() as db:
        db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        apply_seeds(db.connection())
        db.commit()
    invalidate_cache()
    get_redis().flushdb()


@pytest.fixture
def db() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session


@dataclass
class Outbox:
    messages: list[tuple[str, str, str]] = field(default_factory=list)

    def send(self, to: str, subject: str, body: str) -> None:
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

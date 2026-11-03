from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

# Tests never read the developer's .env; they use explicit settings.
os.environ.setdefault("APP_ENV", "test")
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://crm:crm@localhost:5432/crm_test")
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")

from app.core.config import Settings, get_settings  # noqa: E402
from app.db import session as db_session  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=TEST_DATABASE_URL,
        redis_url=TEST_REDIS_URL,
        log_json=True,
    )


@pytest.fixture
def client(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    get_settings.cache_clear()
    db_session.get_engine.cache_clear()
    db_session.get_sessionmaker.cache_clear()
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.routers.health.get_settings", lambda: settings)
    monkeypatch.setattr("app.db.session.get_settings", lambda: settings)
    app = create_app(settings)
    with TestClient(app) as c:
        yield c
    db_session.get_engine.cache_clear()
    db_session.get_sessionmaker.cache_clear()

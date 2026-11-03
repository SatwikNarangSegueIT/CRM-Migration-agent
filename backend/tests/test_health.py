import pytest
from fastapi.testclient import TestClient


def test_live(client: TestClient) -> None:
    r = client.get("/api/v1/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "app": "MigrateCRM", "environment": "test"}


def test_ready_with_database_and_redis(client: TestClient) -> None:
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}


def test_ready_reports_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.health._check_redis", lambda: "error")
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 503
    assert r.json()["checks"] == {"database": "ok", "redis": "error"}

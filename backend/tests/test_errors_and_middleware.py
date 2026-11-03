from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.main import create_app


class Payload(BaseModel):
    name: str = Field(min_length=2)
    age: int


def _app(settings: Settings) -> FastAPI:
    app = create_app(settings)

    @app.post("/api/v1/_test/validate")
    def validate(_: Payload) -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/v1/_test/not-found")
    def not_found() -> None:
        raise NotFoundError("Matter not found.")

    @app.get("/api/v1/_test/conflict")
    def conflict() -> None:
        raise ConflictError("Record was changed by someone else.", fields={"updated_at": "stale"})

    @app.get("/api/v1/_test/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    return app


def test_validation_error_format(settings: Settings) -> None:
    with TestClient(_app(settings)) as c:
        r = c.post("/api/v1/_test/validate", json={"name": "x"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error"
    assert set(err["fields"]) == {"name", "age"}
    assert err["request_id"] == r.headers["X-Request-ID"]


def test_app_errors(settings: Settings) -> None:
    with TestClient(_app(settings)) as c:
        r = c.get("/api/v1/_test/not-found")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "not_found"
        assert r.json()["error"]["message"] == "Matter not found."
        r = c.get("/api/v1/_test/conflict")
        assert r.status_code == 409
        assert r.json()["error"]["fields"] == {"updated_at": "stale"}


def test_unknown_route_and_method(settings: Settings) -> None:
    with TestClient(_app(settings)) as c:
        r = c.get("/api/v1/does-not-exist")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "not_found"
        r = c.delete("/api/v1/health/live")
        assert r.status_code == 405
        assert r.json()["error"]["code"] == "method_not_allowed"


def test_unhandled_error_hides_details(settings: Settings) -> None:
    with TestClient(_app(settings), raise_server_exceptions=False) as c:
        r = c.get("/api/v1/_test/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "internal_error"
    assert "secret" not in r.text
    assert body["error"]["request_id"] == r.headers["X-Request-ID"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_request_id_and_security_headers(settings: Settings) -> None:
    with TestClient(_app(settings)) as c:
        r = c.get("/api/v1/health/live", headers={"X-Request-ID": "abc12345-req"})
        assert r.headers["X-Request-ID"] == "abc12345-req"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert r.headers["Cache-Control"] == "no-store"
        assert "Strict-Transport-Security" not in r.headers
        # Malformed inbound ids are replaced.
        r = c.get("/api/v1/health/live", headers={"X-Request-ID": "bad id!"})
        assert r.headers["X-Request-ID"] != "bad id!"
        assert len(r.headers["X-Request-ID"]) == 32


def test_hsts_in_production(settings: Settings) -> None:
    prod = settings.model_copy(update={"app_env": "production"})
    with TestClient(create_app(prod)) as c:
        r = c.get("/api/v1/health/live")
        assert "max-age" in r.headers["Strict-Transport-Security"]
        # API docs are disabled in production.
        assert c.get("/api/v1/docs").status_code == 404

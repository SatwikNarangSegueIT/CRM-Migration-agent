"""Serverless hosting (Vercel): no work is left in background threads, and scheduled jobs run over HTTP."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings, get_settings

API = "/api/v1"


def test_serverless_is_detected_on_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    assert Settings(serverless=None).is_serverless is False
    monkeypatch.setenv("VERCEL", "1")
    assert Settings(serverless=None).is_serverless is True
    assert Settings(serverless=False).is_serverless is False  # an explicit setting wins


def test_vercel_deployment_addresses_are_allowed_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL_URL", "segue-crm-abc123.vercel.app")
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "segue-crm.vercel.app")
    origins = Settings(public_app_url="https://crm.example.com.au").allowed_origins
    assert {
        "https://crm.example.com.au",
        "https://segue-crm-abc123.vercel.app",
        "https://segue-crm.vercel.app",
    } <= origins


def test_serverless_sends_email_and_runs_jobs_before_responding(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import email
    from app.worker import dispatch

    settings = get_settings()
    monkeypatch.setattr(settings, "serverless", True)
    monkeypatch.setattr(settings, "email_delivery", "inline")
    sent: list[str] = []
    monkeypatch.setattr(email, "deliver_email", lambda to, *_: sent.append(to))
    monkeypatch.setattr(email, "_send_in_background", lambda *_: pytest.fail("no threads when serverless"))
    email.queue_email("client@example.com", "Hello", "Body")
    assert sent == ["client@example.com"]

    def broken(*_: Any) -> None:
        raise RuntimeError("mail server down")

    monkeypatch.setattr(email, "deliver_email", broken)
    email.queue_email("client@example.com", "Hello", "Body")  # logged, not raised

    ran: list[str] = []

    class Task:
        name = "test.task"

        def run(self, value: str) -> None:
            ran.append(value)

    monkeypatch.setattr(dispatch, "worker_available", lambda: False)
    monkeypatch.setattr(dispatch, "run_in_thread", lambda *_: pytest.fail("no threads when serverless"))
    assert dispatch.dispatch(Task(), "done") == "inline"
    assert ran == ["done"]


def test_cron_jobs_need_the_secret(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "cron_secret", None)
    assert client.get(f"{API}/cron/purge").status_code == 404  # off until CRON_SECRET is set
    monkeypatch.setattr(settings, "cron_secret", SecretStr("s3cret-value"))
    assert client.get(f"{API}/cron/purge").status_code == 401
    assert client.get(f"{API}/cron/purge", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get(f"{API}/cron/nope", headers={"Authorization": "Bearer s3cret-value"}).status_code == 404
    r = client.get(f"{API}/cron/purge", headers={"Authorization": "Bearer s3cret-value"})
    assert r.status_code == 200, r.text
    assert r.json()["job"] == "purge" and set(r.json()["result"]) == {"records", "fields", "retention"}
    r = client.get(f"{API}/cron/activity-reminders", headers={"Authorization": "Bearer s3cret-value"})
    assert r.status_code == 200, r.text


def test_email_links_use_the_vercel_address_when_none_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PUBLIC_APP_URL", raising=False)
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "segue-crm.vercel.app")
    assert Settings(_env_file=None).public_app_url == "https://segue-crm.vercel.app"  # type: ignore[call-arg]
    assert (
        Settings(public_app_url="https://crm.example.com.au").public_app_url == "https://crm.example.com.au"
    )

from __future__ import annotations

from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cli
from app.core.config import Settings
from app.models import AuditLog, User
from app.services import email


def test_create_admin(db: Session, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        cli.main(
            [
                "create-admin",
                "--email",
                "Boss@Example.com",
                "--name",
                "Bo Boss",
                "--password",
                "Strong-Admin-Pass-1",
            ]
        )
        == 0
    )
    user = db.scalars(select(User)).one()
    assert (user.email, user.profile.key, user.mfa_enabled) == (
        "boss@example.com",
        "system_administrator",
        False,
    )
    assert db.scalars(select(AuditLog)).one().action == "CREATE"
    # Duplicate and weak passwords are refused.
    assert (
        cli.main(
            [
                "create-admin",
                "--email",
                "boss@example.com",
                "--name",
                "B",
                "--password",
                "Strong-Admin-Pass-1",
            ]
        )
        == 1
    )
    assert cli.main(["create-admin", "--email", "x@example.com", "--name", "X", "--password", "short"]) == 1
    assert "already exists" in capsys.readouterr().err


def test_seed_demo_is_idempotent_and_dev_only(
    db: Session, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert cli.main(["seed-demo"]) == 0
    assert cli.main(["seed-demo"]) == 0
    users = list(db.scalars(select(User)))
    assert len(users) == 7 and not any(u.profile.is_portal for u in users)
    monkeypatch.setattr(settings, "app_env", "production")
    assert cli.main(["seed-demo"]) == 1


def test_console_email_logs(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO", logger="app.email"):
        email.deliver_email("a@example.com", "Hi", "Body")
    record = caplog.records[-1]
    assert record.__dict__["to"] == "a@example.com"
    # Readable even when a log formatter ignores extra fields (e.g. the Celery worker's).
    assert "To: a@example.com" in record.getMessage()
    assert record.getMessage().endswith("Body")


def test_smtp_email(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict[str, Any] = {}

    class FakeSMTP:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            sent["server"] = (host, port)

        def __enter__(self) -> FakeSMTP:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def starttls(self, context: object) -> None:
            sent["tls"] = True

        def login(self, user: str, password: str) -> None:
            sent["login"] = (user, password)

        def send_message(self, message: Any) -> None:
            sent["message"] = message

    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)
    for key, value in {
        "email_backend": "smtp",
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_username": "mailer",
        "smtp_password": SecretStr("pw"),
        "email_from": "CRM <crm@example.com>",
    }.items():
        monkeypatch.setattr(settings, key, value)
    email.deliver_email("a@example.com", "Subject", "Body text")
    assert sent["server"] == ("smtp.example.com", 587)
    assert sent["tls"] is True
    assert sent["login"] == ("mailer", "pw")
    assert sent["message"]["To"] == "a@example.com"
    assert sent["message"]["From"] == "CRM <crm@example.com>"
    assert sent["message"].get_content().strip() == "Body text"


def test_queue_email_uses_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.worker.celery_app import celery_app

    delivered: list[tuple[str, str, str]] = []
    monkeypatch.setattr("app.worker.tasks.deliver_email", lambda *a: delivered.append(a))
    monkeypatch.setattr("app.worker.dispatch.worker_available", lambda: True)
    celery_app.conf.task_always_eager = True
    try:
        email.queue_email("a@example.com", "S", "B")
    finally:
        celery_app.conf.task_always_eager = False
    assert delivered == [("a@example.com", "S", "B")]
    assert email.app_link("/x") == "http://localhost:5173/x"

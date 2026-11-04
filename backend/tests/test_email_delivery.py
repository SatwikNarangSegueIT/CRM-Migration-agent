"""Outgoing e-mail providers (Zoho SMTP on 465/587, ZeptoMail), settings saved in Setup, sign-up modes,
worker detection and the platform status check."""

from __future__ import annotations

import threading
import uuid
from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services import email, mail_settings
from app.services.email import MailDeliveryError
from app.services.mail_settings import MailConfig
from tests.conftest import Outbox, client_as, set_csrf

API = "/api/v1"
STRONG = "Fresh-Firm-Password-77"


class FakeSMTP:
    """Records what the code under test does with smtplib."""

    calls: ClassVar[list[tuple[str, Any]]] = []

    def __init__(self, host: str, port: int, timeout: float = 0, context: Any = None) -> None:
        FakeSMTP.calls.append(("connect", (type(self).__name__, host, port)))

    def __enter__(self) -> FakeSMTP:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def starttls(self, context: Any = None) -> None:
        FakeSMTP.calls.append(("starttls", None))

    def login(self, user: str, password: str) -> None:
        FakeSMTP.calls.append(("login", (user, password)))

    def send_message(self, message: Any) -> None:
        FakeSMTP.calls.append(("send", message))


class FakeSMTPSSL(FakeSMTP):
    pass


@pytest.fixture
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    FakeSMTP.calls = []
    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr("smtplib.SMTP_SSL", FakeSMTPSSL)
    return FakeSMTP.calls


def zoho(**over: Any) -> MailConfig:
    base = MailConfig(
        provider="smtp",
        from_name="Harbour Legal",
        from_email="no-reply@harbour.example.com",
        smtp_host="smtppro.zoho.com",
        smtp_port=465,
        smtp_security="ssl",
        smtp_username="no-reply@harbour.example.com",
        smtp_password="app-password",
    )
    return MailConfig(**{**base.__dict__, **over})


# ------------------------------------------------------------------ providers


def test_zoho_ssl_on_465(fake_smtp: list[tuple[str, Any]]) -> None:
    email.send("client@example.com", "Hello", "Body", config=zoho())
    assert fake_smtp[0] == ("connect", ("FakeSMTPSSL", "smtppro.zoho.com", 465))
    assert ("starttls", None) not in fake_smtp
    assert ("login", ("no-reply@harbour.example.com", "app-password")) in fake_smtp
    message = fake_smtp[-1][1]
    assert message["From"] == "Harbour Legal <no-reply@harbour.example.com>"
    assert message["To"] == "client@example.com"


def test_zoho_starttls_on_587(fake_smtp: list[tuple[str, Any]]) -> None:
    email.send("client@example.com", "Hello", "Body", config=zoho(smtp_port=587, smtp_security="starttls"))
    assert fake_smtp[0] == ("connect", ("FakeSMTP", "smtppro.zoho.com", 587))
    assert ("starttls", None) in fake_smtp


def test_smtp_errors_are_explained(monkeypatch: pytest.MonkeyPatch) -> None:
    import smtplib

    class Rejects(FakeSMTP):
        def login(self, user: str, password: str) -> None:
            raise smtplib.SMTPAuthenticationError(535, b"Authentication Failed")

    monkeypatch.setattr("smtplib.SMTP_SSL", Rejects)
    with pytest.raises(MailDeliveryError, match="application-specific password"):
        email.send("client@example.com", "Hello", "Body", config=zoho())

    class Relay(FakeSMTP):
        def send_message(self, message: Any) -> None:
            raise smtplib.SMTPSenderRefused(553, b"Sender is not allowed to relay emails", "x@y")

    monkeypatch.setattr("smtplib.SMTP_SSL", Relay)
    with pytest.raises(MailDeliveryError, match="From address must be the mailbox"):
        email.send("client@example.com", "Hello", "Body", config=zoho())

    def refused(*_: Any, **__: Any) -> None:
        raise ConnectionRefusedError(111, "Connection refused")

    monkeypatch.setattr("smtplib.SMTP_SSL", refused)
    with pytest.raises(MailDeliveryError, match=r"Couldn't connect to smtppro\.zoho\.com:465"):
        email.send("client@example.com", "Hello", "Body", config=zoho())


def test_zeptomail_api(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    seen: dict[str, Any] = {}

    def post(url: str, json: dict[str, Any], headers: dict[str, str], timeout: float) -> httpx.Response:
        seen.update(url=url, json=json, headers=headers)
        return httpx.Response(201, json={"message": "OK"})

    monkeypatch.setattr(httpx, "post", post)
    config = zoho(
        provider="zeptomail", zeptomail_token="abc123", zeptomail_api_url=mail_settings.ZEPTOMAIL_DEFAULT_URL
    )
    email.send("client@example.com", "Hello", "Body text", html_body="<p>Body</p>", config=config)
    assert seen["url"] == "https://api.zeptomail.com/v1.1/email"
    assert seen["headers"]["Authorization"] == "Zoho-enczapikey abc123"
    assert seen["json"]["from"] == {"address": "no-reply@harbour.example.com", "name": "Harbour Legal"}
    assert seen["json"]["to"] == [{"email_address": {"address": "client@example.com"}}]
    assert seen["json"]["subject"] == "Hello"
    assert seen["json"]["textbody"] == "Body text" and seen["json"]["htmlbody"] == "<p>Body</p>"

    def unauthorised(*_: Any, **__: Any) -> httpx.Response:
        return httpx.Response(401, json={"error": {"code": "TM_3601", "message": "Invalid API Token"}})

    monkeypatch.setattr(httpx, "post", unauthorised)
    with pytest.raises(MailDeliveryError, match=r"Invalid API Token.*Check the token"):
        email.send("client@example.com", "Hello", "Body", config=config)


# ------------------------------------------------------------------ queueing


def test_without_a_worker_email_is_sent_by_the_api(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr("app.worker.dispatch.worker_available", lambda: False)
    monkeypatch.setattr(email, "deliver_email", lambda to, *_: sent.append(to))
    email.queue_email("a@example.com", "S", "B", wait=True)
    assert sent == ["a@example.com"]

    def broken(*_: Any) -> None:
        raise MailDeliveryError("The mail server rejected the username or password (535).")

    monkeypatch.setattr(email, "deliver_email", broken)
    with pytest.raises(MailDeliveryError):
        email.queue_email("a@example.com", "S", "B", wait=True)


def test_dispatch_runs_jobs_in_the_api_without_a_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.worker import dispatch

    ran = threading.Event()

    class Job:
        name = "test.job"

        def run(self, value: str) -> None:
            assert value == "x"
            ran.set()

        def delay(self, *_: Any) -> None:  # pragma: no cover - must not be used
            raise AssertionError("queued without a worker")

    monkeypatch.setattr(dispatch, "worker_available", lambda: False)
    assert dispatch.dispatch(Job(), "x") == "inline"
    assert ran.wait(5)


def test_worker_heartbeat_is_detected() -> None:
    from app.core.redis_client import get_redis
    from app.worker.dispatch import HEARTBEAT_KEY, forget_worker_check, worker_available

    forget_worker_check()
    assert worker_available() is False
    get_redis().set(HEARTBEAT_KEY, "worker-1", ex=60)
    forget_worker_check()
    assert worker_available() is True


# ------------------------------------------------------------------ settings saved in Setup


def test_operator_configures_zoho_and_sends_a_test(
    admin_client: TestClient, db: Session, fake_smtp: list[tuple[str, Any]]
) -> None:
    c = admin_client
    me = c.get(f"{API}/auth/me").json()
    assert me["is_platform_operator"] is True
    current = c.get(f"{API}/platform/email").json()
    assert current["settings"]["provider"] == "console"
    assert any(h["personal"] == "smtp.zoho.com" for h in current["zoho_smtp_hosts"])

    body = {
        "provider": "smtp",
        "from_name": "Meridian CRM",
        "from_email": "no-reply@harbour.example.com",
        "smtp_host": "smtppro.zoho.com",
        "smtp_port": 465,
        "smtp_security": "ssl",
        "smtp_username": "no-reply@harbour.example.com",
        "smtp_password": "app-password",
    }
    r = c.put(f"{API}/platform/email", json=body)
    assert r.status_code == 200, r.text
    saved = r.json()["settings"]
    assert saved["source"] == "setup" and saved["smtp_password_set"] is True
    assert "app-password" not in r.text
    stored = db.execute(text("SELECT value FROM platform.settings WHERE key = 'email'")).scalar_one()
    assert stored["smtp_password_enc"] and "app-password" not in str(stored)

    # A blank password keeps the saved one.
    r = c.put(f"{API}/platform/email", json={**body, "smtp_password": "", "from_name": "Harbour"})
    assert r.json()["settings"]["smtp_password_set"] is True
    assert mail_settings.mail_config().smtp_password == "app-password"

    r = c.post(f"{API}/platform/email/test", json={"to": "me@example.com"})
    assert r.status_code == 200, r.text
    assert fake_smtp[0] == ("connect", ("FakeSMTPSSL", "smtppro.zoho.com", 465))
    assert fake_smtp[-1][1]["To"] == "me@example.com"

    # Back to the environment settings.
    assert c.delete(f"{API}/platform/email").json()["settings"]["source"] == "environment"


def test_test_email_reports_the_problem(admin_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    r = admin_client.post(f"{API}/platform/email/test", json={"to": "me@example.com"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "email_not_configured"

    import smtplib

    class Rejects(FakeSMTP):
        def login(self, user: str, password: str) -> None:
            raise smtplib.SMTPAuthenticationError(535, b"Authentication Failed")

    monkeypatch.setattr("smtplib.SMTP", Rejects)
    unsaved = {
        "provider": "smtp",
        "from_email": "no-reply@harbour.example.com",
        "smtp_host": "smtp.zoho.com",
        "smtp_port": 587,
        "smtp_security": "starttls",
        "smtp_username": "no-reply@harbour.example.com",
        "smtp_password": "wrong",
    }
    r = admin_client.post(f"{API}/platform/email/test", json={"to": "me@example.com", "settings": unsaved})
    assert r.status_code == 400
    assert "application-specific password" in r.json()["error"]["message"]


def test_only_platform_operators_change_email(
    admin_client: TestClient, settings: Settings, outbox: Outbox, db: Session, no_mfa: None
) -> None:
    staff = client_as(settings, outbox, db, "sales_representative")
    assert staff.get(f"{API}/platform/email").status_code == 403
    assert staff.get(f"{API}/auth/me").json()["is_platform_operator"] is False
    status = admin_client.get(f"{API}/platform/status").json()
    keys = {c["key"] for c in status}
    assert {"platform_schema", "email", "signup", "worker", "warm_pool", "public_url"} <= keys
    assert next(c for c in status if c["key"] == "platform_schema")["status"] == "ok"


# ------------------------------------------------------------------ sign-up modes


def _signup(c: TestClient, **over: Any) -> Any:
    body = {
        "domain": "migration",
        "firm_name": "Quick Visa Co",
        "name": "Quinn Quick",
        "email": "quinn@quick.example.com",
        "password": STRONG,
        "accept_terms": True,
        **over,
    }
    return c.post(f"{API}/signup", json=body)


def test_without_email_the_workspace_is_created_at_once(
    client: TestClient, settings: Settings, outbox: Outbox, no_mfa: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "signup_email_verification", "auto")  # console backend, not production
    r = _signup(client)
    assert r.status_code == 201, r.text
    assert r.json()["state"] == "authenticated"
    assert r.json()["workspace"]["slug"] == "quick-visa-co"
    assert outbox.messages == []
    set_csrf(client)
    me = client.get(f"{API}/auth/me").json()
    assert me["user"]["email"] == "quinn@quick.example.com" and me["is_system_admin"] is True
    # A firm's own administrator is not the platform operator.
    assert me["is_platform_operator"] is False
    assert client.get(f"{API}/platform/email").status_code == 403


def test_production_always_confirms_the_email(
    client: TestClient, settings: Settings, outbox: Outbox, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.signup import verification_required

    monkeypatch.setattr(settings, "signup_email_verification", "auto")
    assert verification_required() is False
    monkeypatch.setattr(settings, "app_env", "production")
    assert verification_required() is True
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "email_backend", "smtp")
    mail_settings.forget_cached()
    assert verification_required() is True


def test_signup_reports_when_the_email_cannot_be_sent(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*_: Any, **__: Any) -> None:
        raise MailDeliveryError("The mail server rejected the username or password (535).")

    monkeypatch.setattr("app.routers.signup.queue_email", fail)
    r = _signup(client, email="fail@quick.example.com")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "email_failed"
    assert "535" not in r.text  # mail-server details stay in the log


def test_a_workspace_made_by_another_process_is_found_at_once(db: Session) -> None:
    from app.tenancy import by_slug, tenants

    tenants()  # load the catalogue
    tenant_id = uuid.uuid4()
    db.execute(
        text(
            "INSERT INTO platform.tenants (id, slug, name, domain, schema_name, status) "
            "VALUES (:id, 'elsewhere', 'Made Elsewhere', 'legal', 'public_elsewhere', 'active')"
        ),
        {"id": tenant_id},
    )
    db.commit()
    found = by_slug("elsewhere")  # not in this process's catalogue yet: looked up in the database
    assert found is not None and found.id == tenant_id

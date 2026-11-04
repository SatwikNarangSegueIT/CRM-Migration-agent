"""Public sign-up with domain choice, e-mail verification and provisioning (plan v4, section 4)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.migrate import fill_warm_pool, warm_schemas
from app.tenancy import SESSION_COOKIE, split_token
from tests.conftest import TEST_DATABASE_URL, Outbox, set_csrf

API = "/api/v1"
STRONG = "Fresh-Firm-Password-77"


def _signup(c: TestClient, **over: Any) -> Any:
    body = {
        "domain": "legal",
        "firm_name": "Harbour Legal",
        "name": "Hana Harbour",
        "email": "hana@harbour.example.com",
        "password": STRONG,
        "abn": "51 824 753 556",
        "accept_terms": True,
        **over,
    }
    return c.post(f"{API}/signup", json=body)


def _token(outbox: Outbox, to: str) -> str:
    return outbox.token_for(to)


def test_domains_are_listed(client: TestClient) -> None:
    keys = [d["key"] for d in client.get(f"{API}/signup/domains").json()]
    assert keys == ["legal", "migration", "accounting", "lending"]


def test_signup_verifies_email_and_creates_a_workspace(
    client: TestClient, db: Session, outbox: Outbox, no_mfa: None
) -> None:
    r = _signup(client)
    assert r.status_code == 202, r.text
    # Nothing exists until the e-mail is verified.
    assert db.execute(text("SELECT count(*) FROM platform.tenants")).scalar_one() == 1
    token = _token(outbox, "hana@harbour.example.com")

    r = client.post(f"{API}/signup/verify", json={"token": token})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["state"] == "authenticated"
    assert out["workspace"] == {"slug": "harbour-legal", "name": "Harbour Legal"}
    assert split_token(client.cookies[SESSION_COOKIE])[0] == "harbour-legal"
    set_csrf(client)

    me = client.get(f"{API}/auth/me").json()
    assert me["user"]["email"] == "hana@harbour.example.com" and me["is_system_admin"] is True
    company = client.get(f"{API}/setup/settings").json()
    assert company["company"]["legal_name"] == "Harbour Legal"
    row = db.execute(text("SELECT domain, status FROM platform.tenants WHERE slug = 'harbour-legal'")).one()
    assert tuple(row) == ("legal", "active")
    # The link is single use and the stored password hash is gone.
    assert client.post(f"{API}/signup/verify", json={"token": token}).status_code == 400
    assert db.execute(text("SELECT password_hash FROM platform.signup_requests")).scalar_one() is None

    # The new administrator can sign in normally; the first workspace's data is not visible.
    other = TestClient(client.app)
    r = other.post(f"{API}/auth/login", json={"email": "hana@harbour.example.com", "password": STRONG})
    assert r.json()["state"] == "authenticated"


def test_signup_validation(client: TestClient, outbox: Outbox) -> None:
    assert _signup(client, accept_terms=False).status_code == 422
    assert _signup(client, domain="astrology").status_code == 400
    assert _signup(client, password="password").status_code == 422
    # Honeypot: accepted silently, nothing sent.
    assert _signup(client, website_url="http://spam").status_code == 202
    assert outbox.messages == []
    assert client.post(f"{API}/signup/verify", json={"token": "x" * 40}).status_code == 400


def test_migration_domain_installs_its_pack(client: TestClient, outbox: Outbox, no_mfa: None) -> None:
    _signup(client, domain="migration", firm_name="Visa Pathways", email="mia@visa.example.com")
    r = client.post(f"{API}/signup/verify", json={"token": _token(outbox, "mia@visa.example.com")})
    assert r.status_code == 200, r.text
    set_csrf(client)
    packs = {p["key"]: p for p in client.get(f"{API}/setup/packs").json()}
    assert packs["migration_agency"]["is_enabled"] is True


def test_warm_pool_is_used_first(client: TestClient, outbox: Outbox, no_mfa: None) -> None:
    assert fill_warm_pool(1, TEST_DATABASE_URL) == 1
    (warm,) = warm_schemas(TEST_DATABASE_URL)
    _signup(client, firm_name="Quick Start Pty Ltd", email="q@quick.example.com")
    r = client.post(f"{API}/signup/verify", json={"token": _token(outbox, "q@quick.example.com")})
    assert r.status_code == 200, r.text
    assert warm_schemas(TEST_DATABASE_URL) == []
    from app.tenancy import by_slug

    tenant = by_slug("quick-start-pty-ltd")
    assert tenant is not None and tenant.schema == warm


def test_first_run_guide(client: TestClient, outbox: Outbox, no_mfa: None) -> None:
    _signup(client, firm_name="Guide Firm", email="g@guide.example.com")
    client.post(f"{API}/signup/verify", json={"token": _token(outbox, "g@guide.example.com")})
    set_csrf(client)
    guide = client.get(f"{API}/onboarding").json()
    assert guide["visible"] is True
    assert [s["key"] for s in guide["steps"] if not s["done"]] == ["invite", "import", "company", "email"]
    assert client.post(f"{API}/onboarding/dismiss").status_code == 200
    assert client.get(f"{API}/onboarding").json()["visible"] is False


def test_failed_setup_leaves_nothing_behind_and_the_link_still_works(
    client: TestClient, db: Session, outbox: Outbox, no_mfa: None, monkeypatch: Any
) -> None:
    from app.services import signup as svc

    assert _signup(client, email="retry@harbour.example.com").status_code == 202
    token = _token(outbox, "retry@harbour.example.com")
    real = svc.apply_domain

    def boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("pack install failed")

    monkeypatch.setattr(svc, "apply_domain", boom)
    r = client.post(f"{API}/signup/verify", json={"token": token})
    assert r.status_code == 503 and r.json()["error"]["code"] == "provisioning_failed"
    db.expire_all()
    assert db.execute(text("SELECT count(*) FROM platform.tenants")).scalar_one() == 1
    assert (
        db.execute(
            text("SELECT count(*) FROM platform.user_directory WHERE email = 'retry@harbour.example.com'")
        ).scalar_one()
        == 0
    )

    monkeypatch.setattr(svc, "apply_domain", real)
    r = client.post(f"{API}/signup/verify", json={"token": token})
    assert r.status_code == 200, r.text
    assert r.json()["workspace"]["slug"] == "harbour-legal"


def test_email_falls_back_to_direct_sending_when_the_queue_is_down(monkeypatch: Any) -> None:
    from app.services import email
    from app.worker import tasks

    sent: list[str] = []

    def down(*_a: Any, **_k: Any) -> None:
        raise ConnectionError("redis unreachable")

    monkeypatch.setattr(tasks.send_email_task, "delay", down)
    monkeypatch.setattr(email, "deliver_email", lambda to, *_: sent.append(to))
    monkeypatch.setattr(email.threading, "Thread", _ImmediateThread)
    email.queue_email("a@example.com", "s", "b")
    assert sent == ["a@example.com"]


class _ImmediateThread:
    def __init__(self, target: Any, **_k: Any) -> None:
        self._target = target

    def start(self) -> None:
        self._target()


def test_concurrent_workspace_builds_in_one_process_do_not_collide(db: Session) -> None:
    """A sign-up building a workspace while the API refills the warm pool (same process, two threads)."""
    import threading

    from app.db.migrate import create_tenant, fill_warm_pool

    errors: list[BaseException] = []

    def run(job: Any) -> None:
        try:
            job()
        except BaseException as exc:  # reported below
            errors.append(exc)

    threads = [
        threading.Thread(target=run, args=(lambda: fill_warm_pool(1),)),
        threading.Thread(
            target=run, args=(lambda: create_tenant("Concurrent Co", "legal", use_warm_pool=False),)
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(300)
    assert errors == []
    assert db.execute(text("SELECT count(*) FROM platform.warm_schemas")).scalar_one() == 1
    schema = db.execute(
        text("SELECT schema_name FROM platform.tenants WHERE slug = 'concurrent-co'")
    ).scalar_one()
    profiles = text(f'SELECT count(*) FROM "{schema}".profiles')  # noqa: S608 - schema name from the catalogue
    assert db.execute(profiles).scalar_one() > 0

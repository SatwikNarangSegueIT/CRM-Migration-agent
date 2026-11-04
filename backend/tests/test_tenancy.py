"""Schema-per-tenant isolation (plan v4, section 3)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.migrate import create_tenant
from app.db.session import get_sessionmaker
from app.tenancy import SESSION_COOKIE, bind_tenant, by_slug, split_token
from tests.conftest import PASSWORD, TEST_DATABASE_URL, Outbox, make_user, set_csrf
from tests.test_records_engine import create

API = "/api/v1"


def _tenant_session(slug: str) -> Session:
    db = get_sessionmaker()()
    bind_tenant(db, by_slug(slug))
    return db


def _login(c: TestClient, email: str, workspace: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"email": email, "password": PASSWORD}
    if workspace:
        body["workspace"] = workspace
    r = c.post(f"{API}/auth/login", json=body)
    assert r.status_code == 200, r.text
    set_csrf(c)
    out: dict[str, Any] = r.json()
    return out


def test_tenants_are_isolated(client: TestClient, db: Session, no_mfa: None, outbox: Outbox) -> None:
    _, slug, schema = create_tenant("Smith Lawyers", "legal", url=TEST_DATABASE_URL)
    assert slug == "smith-lawyers" and schema.startswith("t_")

    make_user(db, email="a@firm-a.example.com")
    with _tenant_session(slug) as db_b:
        make_user(db_b, email="b@firm-b.example.com")
        # The new schema has its own seeded profiles and metadata.
        assert db_b.execute(text("SELECT count(*) FROM profiles")).scalar_one() > 0

    a = client
    assert _login(a, "a@firm-a.example.com")["state"] == "authenticated"
    first_slug, _ = split_token(a.cookies[SESSION_COOKIE])
    assert first_slug == "main"
    create(a, "account", name="Firm A Client")

    b = TestClient(client.app)
    assert _login(b, "b@firm-b.example.com")["state"] == "authenticated"
    assert split_token(b.cookies[SESSION_COOKIE])[0] == slug
    names_b = [r["name"] for r in b.post(f"{API}/objects/account/records/query", json={}).json()["items"]]
    assert "Firm A Client" not in names_b
    create(b, "account", name="Firm B Client")
    names_a = [r["name"] for r in a.post(f"{API}/objects/account/records/query", json={}).json()["items"]]
    assert names_a == ["Firm A Client"]

    # A firm's user cannot sign in to another firm.
    r = b.post(
        f"{API}/auth/login", json={"email": "a@firm-a.example.com", "password": PASSWORD, "workspace": slug}
    )
    assert r.status_code == 401

    # Swapping the cookie's tenant prefix does not reach the other firm's data.
    _, token_a = split_token(a.cookies[SESSION_COOKIE])
    forged = TestClient(client.app)
    forged.cookies.set(SESSION_COOKIE, f"{slug}.{token_a}")
    assert forged.get(f"{API}/auth/me").status_code == 401
    unknown = TestClient(client.app)
    unknown.cookies.set(SESSION_COOKIE, f"nosuchfirm.{token_a}")
    assert unknown.get(f"{API}/auth/me").status_code == 401


def test_same_email_in_two_workspaces_gets_a_picker(
    client: TestClient, db: Session, no_mfa: None, outbox: Outbox
) -> None:
    _, slug, _ = create_tenant("Second Firm", "accounting", url=TEST_DATABASE_URL)
    make_user(db, email="both@example.com", name="In Both")
    with _tenant_session(slug) as db_b:
        make_user(db_b, email="both@example.com", name="In Both")

    out = _login(client, "both@example.com")
    assert out["state"] == "choose_workspace"
    assert {w["slug"] for w in out["workspaces"]} == {"main", slug}
    assert SESSION_COOKIE not in client.cookies

    assert _login(client, "both@example.com", workspace=slug)["state"] == "authenticated"
    assert split_token(client.cookies[SESSION_COOKIE])[0] == slug

    # Password reset e-mails go out per workspace with tenant-qualified links.
    r = client.post(f"{API}/auth/password/forgot", json={"email": "both@example.com"})
    assert r.status_code == 202
    tokens = [body.split("#token=", 1)[1].split()[0] for to, _, body in outbox.messages if "#token=" in body]
    assert {split_token(t)[0] for t in tokens} == {"main", slug}
    r = client.post(
        f"{API}/auth/password/reset", json={"token": tokens[-1], "new_password": "Another-Strong-Pass-42"}
    )
    assert r.status_code == 200, r.text


def test_directory_follows_user_changes(db: Session) -> None:
    user = make_user(db, email="dir@example.com")
    rows = db.execute(
        text("SELECT email FROM platform.user_directory WHERE user_id = :u"), {"u": user.id}
    ).all()
    assert rows == [("dir@example.com",)]
    user.email = "renamed@example.com"
    db.commit()
    assert (
        db.execute(
            text("SELECT email FROM platform.user_directory WHERE user_id = :u"), {"u": user.id}
        ).scalar_one()
        == "renamed@example.com"
    )
    db.delete(user)
    db.commit()
    assert (
        db.execute(
            text("SELECT count(*) FROM platform.user_directory WHERE user_id = :u"), {"u": user.id}
        ).scalar_one()
        == 0
    )


def test_pooled_mode_sets_search_path_per_transaction(db: Session) -> None:
    import pytest

    import app.tenancy as tenancy

    _, slug, schema = create_tenant("Pooled Firm", "lending", url=TEST_DATABASE_URL)
    mp = pytest.MonkeyPatch()
    mp.setattr(tenancy, "_per_transaction", lambda: True)
    try:
        with _tenant_session(slug) as s:
            assert s.execute(text("SELECT current_schema()")).scalar_one() == schema
            s.commit()
            # A later transaction on the same pooled connection is routed again.
            assert s.execute(text("SELECT current_schema()")).scalar_one() == schema
        with get_sessionmaker()() as s:
            assert s.execute(text("SELECT current_schema()")).scalar_one() == "public"
    finally:
        mp.undo()


def test_index_ddl_names_the_tenant_schema() -> None:
    from app.engine.indexes import qualify

    assert qualify("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_rec_f_a_b ON records ((x))", "t_1") == (
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_rec_f_a_b ON "t_1".records ((x))'
    )
    assert qualify("DROP INDEX CONCURRENTLY IF EXISTS ix_rec_f_a_b", "t_1") == (
        'DROP INDEX CONCURRENTLY IF EXISTS "t_1".ix_rec_f_a_b'
    )

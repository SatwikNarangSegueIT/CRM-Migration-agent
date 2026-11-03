from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AuditLog, RecoveryCode, User, UserSession
from app.permissions.matrix import Role
from tests.conftest import Outbox, client_as, login, make_user

API = "/api/v1"


@pytest.mark.parametrize("role", [r for r in Role if r is not Role.ADMIN], ids=lambda r: r.value)
def test_only_admins_manage_users(
    role: Role, settings: Settings, outbox: Outbox, db: Session, no_mfa: None
) -> None:
    c = client_as(settings, outbox, db, role)
    assert c.get(f"{API}/admin/users").status_code == 403
    r = c.post(f"{API}/admin/users", json={"email": "x@example.com", "name": "X", "role": "AUDITOR"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_admin_endpoints_require_sign_in(client: TestClient) -> None:
    assert client.get(f"{API}/admin/users").status_code == 401
    assert client.get(f"{API}/admin/audit-logs").status_code == 401
    assert client.get(f"{API}/meta/roles").status_code == 401


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (Role.ADMIN, True),
        (Role.PRACTICE_MANAGER, True),
        (Role.AUDITOR, True),
        (Role.MIGRATION_AGENT, False),
        (Role.CASE_OFFICER, False),
        (Role.INTAKE_CONSULTANT, False),
        (Role.ACCOUNTS, False),
        (Role.CLIENT, False),
    ],
    ids=lambda v: v.value if isinstance(v, Role) else str(v),
)
def test_audit_log_access(
    role: Role, allowed: bool, settings: Settings, outbox: Outbox, db: Session, no_mfa: None
) -> None:
    c = client_as(settings, outbox, db, role)
    assert c.get(f"{API}/admin/audit-logs").status_code == (200 if allowed else 403)


def test_meta_roles_staff_only(settings: Settings, outbox: Outbox, db: Session, no_mfa: None) -> None:
    staff = client_as(settings, outbox, db, Role.CASE_OFFICER)
    roles = staff.get(f"{API}/meta/roles").json()
    assert roles[0]["value"] == "ADMIN"
    assert next(r for r in roles if r["value"] == "CLIENT")["is_staff"] is False
    client = client_as(settings, outbox, db, Role.CLIENT)
    assert client.get(f"{API}/meta/roles").status_code == 403


def test_create_user_validation(admin_client: TestClient, db: Session) -> None:
    c = admin_client
    ok = c.post(
        f"{API}/admin/users",
        json={
            "email": "agent@example.com",
            "name": " Riley Agent ",
            "role": "MIGRATION_AGENT",
            "mara_number": "1234567",
        },
    )
    assert ok.status_code == 201
    assert ok.json()["name"] == "Riley Agent"
    assert ok.json()["role_label"] == "Registered Migration Agent"

    dup = c.post(f"{API}/admin/users", json={"email": "AGENT@example.com", "name": "Dup", "role": "AUDITOR"})
    assert dup.status_code == 409
    assert dup.json()["error"]["fields"] == {"email": "Already in use"}
    client_role = c.post(f"{API}/admin/users", json={"email": "c@example.com", "name": "C", "role": "CLIENT"})
    assert client_role.status_code == 422
    bad_mara = c.post(
        f"{API}/admin/users",
        json={"email": "m@example.com", "name": "M", "role": "AUDITOR", "mara_number": "12"},
    )
    assert bad_mara.status_code == 422
    assert "mara_number" in bad_mara.json()["error"]["fields"]
    bad_role = c.post(f"{API}/admin/users", json={"email": "r@example.com", "name": "R", "role": "GOD"})
    assert bad_role.status_code == 422
    bad_email = c.post(f"{API}/admin/users", json={"email": "not-an-email", "name": "R", "role": "AUDITOR"})
    assert bad_email.status_code == 422


def test_list_users_filters_and_pagination(admin_client: TestClient, db: Session) -> None:
    make_user(db, role=Role.AUDITOR, email="zed@example.com", name="Zed Auditor")
    make_user(db, role=Role.ACCOUNTS, email="bea@example.com", name="Bea Accounts", is_active=False)
    make_user(db, role=Role.ACCOUNTS, email="under_score@example.com", name="Underscore Person")
    c = admin_client
    page = c.get(f"{API}/admin/users", params={"page_size": 2}).json()
    assert page["total"] == 4 and len(page["items"]) == 2 and page["page"] == 1
    assert [u["name"] for u in page["items"]] == ["Ada Admin", "Bea Accounts"]
    assert c.get(f"{API}/admin/users", params={"role": "ACCOUNTS"}).json()["total"] == 2
    assert c.get(f"{API}/admin/users", params={"is_active": "false"}).json()["total"] == 1
    assert c.get(f"{API}/admin/users", params={"q": "zed"}).json()["items"][0]["email"] == "zed@example.com"
    # LIKE wildcards in the search box are treated literally.
    assert c.get(f"{API}/admin/users", params={"q": "_"}).json()["total"] == 1
    assert c.get(f"{API}/admin/users", params={"page_size": 101}).status_code == 422


def test_update_user_and_audit_diff(admin_client: TestClient, db: Session) -> None:
    target = make_user(db, role=Role.CASE_OFFICER, email="t@example.com", name="Tess")
    c = admin_client
    current = c.get(f"{API}/admin/users/{target.id}").json()
    r = c.patch(
        f"{API}/admin/users/{target.id}",
        json={
            "updated_at": current["updated_at"],
            "role": "MIGRATION_AGENT",
            "title": "Senior agent",
            "phone": "",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "MIGRATION_AGENT"
    assert r.json()["title"] == "Senior agent"

    entry = db.scalars(select(AuditLog).where(AuditLog.action == "UPDATE")).one()
    assert entry.changes == {
        "role": {"from": "CASE_OFFICER", "to": "MIGRATION_AGENT"},
        "title": {"from": None, "to": "Senior agent"},
    }
    assert entry.entity_id == str(target.id)
    assert entry.request_id

    # Stale updated_at -> 409.
    stale = c.patch(
        f"{API}/admin/users/{target.id}", json={"updated_at": current["updated_at"], "name": "Other"}
    )
    assert stale.status_code == 409


def test_role_change_and_deactivation_sign_user_out(
    admin_client: TestClient, db: Session, settings: Settings, outbox: Outbox
) -> None:
    target = make_user(db, role=Role.ACCOUNTS, email="t@example.com")
    victim = TestClient(admin_client.app)
    login(victim, target.email)
    assert victim.get(f"{API}/auth/me").status_code == 200
    current = admin_client.get(f"{API}/admin/users/{target.id}").json()
    r = admin_client.patch(
        f"{API}/admin/users/{target.id}", json={"updated_at": current["updated_at"], "is_active": False}
    )
    assert r.status_code == 200
    assert victim.get(f"{API}/auth/me").status_code == 401
    assert db.scalar(select(UserSession).where(UserSession.user_id == target.id)) is None


def test_self_protection_and_last_admin(admin_client: TestClient, db: Session) -> None:
    c = admin_client
    me = c.get(f"{API}/auth/me").json()["user"]
    current = c.get(f"{API}/admin/users/{me['id']}").json()
    r = c.patch(
        f"{API}/admin/users/{me['id']}", json={"updated_at": current["updated_at"], "role": "AUDITOR"}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "forbidden_self_change"
    r = c.patch(
        f"{API}/admin/users/{me['id']}", json={"updated_at": current["updated_at"], "is_active": False}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "forbidden_self_change"
    # Editing own name is fine.
    r = c.patch(f"{API}/admin/users/{me['id']}", json={"updated_at": current["updated_at"], "name": "Ada A."})
    assert r.status_code == 200

    # Another admin can be demoted while one active admin remains; the last one cannot.
    other = make_user(db, role=Role.ADMIN, email="other-admin@example.com")
    other_now = c.get(f"{API}/admin/users/{other.id}").json()
    r = c.patch(
        f"{API}/admin/users/{other.id}", json={"updated_at": other_now["updated_at"], "role": "AUDITOR"}
    )
    assert r.status_code == 200

    # Make the signed-in admin's account the only admin and try to remove it via a second admin session.
    second = make_user(db, role=Role.ADMIN, email="second@example.com")
    second_client = TestClient(c.app)
    login(second_client, second.email)
    ada = c.get(f"{API}/admin/users/{me['id']}").json()
    assert (
        second_client.patch(
            f"{API}/admin/users/{me['id']}", json={"updated_at": ada["updated_at"], "is_active": False}
        ).status_code
        == 200
    )
    second_now = second_client.get(f"{API}/admin/users/{second.id}").json()
    # `second` is now the last active admin; nobody can deactivate it (self-protection applies too).
    r = second_client.patch(
        f"{API}/admin/users/{second.id}", json={"updated_at": second_now["updated_at"], "role": "AUDITOR"}
    )
    assert r.status_code == 422


def test_last_admin_rule_directly(db: Session, admin_client: TestClient) -> None:
    from app.auth.deps import AuthContext
    from app.schemas.users import UserUpdate
    from app.services.audit import RequestMeta
    from app.services.users import update_user

    only_admin = db.scalars(select(User).where(User.role == "ADMIN")).one()
    actor = make_user(db, role=Role.ADMIN, email="actor@example.com", is_active=False)
    session = UserSession(
        user_id=actor.id, token_hash="x" * 64, csrf_token_hash="y" * 64, expires_at=only_admin.created_at
    )
    ctx = AuthContext(user=actor, session=session)
    with pytest.raises(Exception, match="At least one active administrator"):
        update_user(
            db,
            ctx,
            only_admin.id,
            UserUpdate(updated_at=only_admin.updated_at, is_active=False),
            RequestMeta(),
        )


def test_reset_mfa_unlock_revoke_and_resend(admin_client: TestClient, db: Session, outbox: Outbox) -> None:
    secret_user = make_user(db, role=Role.AUDITOR, email="mfa@example.com", mfa_secret="JBSWY3DPEHPK3PXP")
    db.add(RecoveryCode(user_id=secret_user.id, code_hash="a" * 64))
    db.commit()
    c = admin_client
    r = c.post(f"{API}/admin/users/{secret_user.id}/reset-mfa")
    assert r.status_code == 200 and r.json()["mfa_enabled"] is False
    db.expire_all()
    assert db.get(User, secret_user.id).mfa_secret_encrypted is None  # type: ignore[union-attr]
    assert db.scalar(select(RecoveryCode).where(RecoveryCode.user_id == secret_user.id)) is None

    assert c.post(f"{API}/admin/users/{secret_user.id}/revoke-sessions").json() == {
        "message": "Signed out 0 session(s)."
    }
    # Already has a password -> cannot resend invitation.
    assert c.post(f"{API}/admin/users/{secret_user.id}/resend-invitation").status_code == 409

    invited = c.post(
        f"{API}/admin/users", json={"email": "inv@example.com", "name": "Inv", "role": "AUDITOR"}
    ).json()
    first = outbox.token_for("inv@example.com")
    assert c.post(f"{API}/admin/users/{invited['id']}/resend-invitation").status_code == 200
    second = outbox.token_for("inv@example.com")
    assert first != second
    anon = TestClient(c.app)
    assert anon.post(f"{API}/auth/invitation/inspect", json={"token": first}).status_code == 400
    assert anon.post(f"{API}/auth/invitation/inspect", json={"token": second}).status_code == 200

    assert c.get(f"{API}/admin/users/00000000-0000-0000-0000-000000000000").status_code == 404
    assert c.get(f"{API}/admin/users/not-a-uuid").status_code == 422


def test_audit_log_listing_and_filters(admin_client: TestClient, db: Session) -> None:
    c = admin_client
    c.post(f"{API}/admin/users", json={"email": "a1@example.com", "name": "A1", "role": "AUDITOR"})
    page = c.get(f"{API}/admin/audit-logs").json()
    assert [i["action"] for i in page["items"]] == ["CREATE", "LOGIN"]  # newest first
    created = page["items"][0]
    assert created["actor"]["email"] == "admin@example.com"
    assert created["changes"]["email"] == {"from": None, "to": "a1@example.com"}
    assert "password_hash" not in created["changes"]
    assert c.get(f"{API}/admin/audit-logs", params={"action": "LOGIN"}).json()["total"] == 1
    assert (
        c.get(
            f"{API}/admin/audit-logs", params={"entity_type": "user", "entity_id": created["entity_id"]}
        ).json()["total"]
        == 1
    )
    assert c.get(f"{API}/admin/audit-logs", params={"date_from": "2999-01-01T00:00:00Z"}).json()["total"] == 0


def test_audit_log_is_append_only(db: Session, admin_client: TestClient) -> None:
    assert db.scalar(select(AuditLog.id)) is not None
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("UPDATE audit_logs SET summary = 'tampered'"))
    db.rollback()
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("DELETE FROM audit_logs"))
    db.rollback()

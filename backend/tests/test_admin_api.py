from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AuditLog, RecoveryCode, User, UserSession
from app.security.seed_v1 import PROFILES, stable_id
from tests.conftest import Outbox, client_as, login, make_user

PROFILE_KEYS = [p[0] for p in PROFILES]
READ_ONLY = str(stable_id("profile", "read_only"))
FINANCE = str(stable_id("profile", "finance"))
SALES_REP = str(stable_id("profile", "sales_representative"))
PORTAL = str(stable_id("profile", "customer_portal"))

API = "/api/v1"


@pytest.mark.parametrize("profile", [k for k in PROFILE_KEYS if k != "system_administrator"])
def test_only_admins_manage_users(
    profile: str, settings: Settings, outbox: Outbox, db: Session, no_mfa: None
) -> None:
    c = client_as(settings, outbox, db, profile)
    assert c.get(f"{API}/admin/users").status_code == 403
    r = c.post(f"{API}/admin/users", json={"email": "x@example.com", "name": "X", "profile_id": READ_ONLY})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_admin_endpoints_require_sign_in(client: TestClient) -> None:
    assert client.get(f"{API}/admin/users").status_code == 401
    assert client.get(f"{API}/admin/audit-logs").status_code == 401
    assert client.get(f"{API}/setup/profiles").status_code == 401


@pytest.mark.parametrize(
    ("profile", "allowed"),
    [
        ("system_administrator", True),
        ("read_only", True),
        ("sales_manager", False),
        ("sales_representative", False),
        ("service_agent", False),
        ("marketing_user", False),
        ("finance", False),
        ("customer_portal", False),
    ],
)
def test_audit_log_access(
    profile: str, allowed: bool, settings: Settings, outbox: Outbox, db: Session, no_mfa: None
) -> None:
    c = client_as(settings, outbox, db, profile)
    assert c.get(f"{API}/admin/audit-logs").status_code == (200 if allowed else 403)


def test_portal_users_never_reach_staff_apis(
    settings: Settings, outbox: Outbox, db: Session, no_mfa: None
) -> None:
    portal = client_as(settings, outbox, db, "customer_portal")
    assert portal.get(f"{API}/setup/profiles").status_code == 403
    assert portal.get(f"{API}/admin/users").status_code == 403


def test_create_user_validation(admin_client: TestClient, db: Session) -> None:
    c = admin_client
    ok = c.post(
        f"{API}/admin/users",
        json={
            "email": "agent@example.com",
            "name": " Riley Agent ",
            "profile_id": SALES_REP,
            "role_id": str(stable_id("role", "sales_representative")),
            "mara_number": "1234567",
        },
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["name"] == "Riley Agent"
    assert ok.json()["profile"]["name"] == "Sales Representative"
    assert ok.json()["role"]["name"] == "Sales Representative"

    dup = c.post(
        f"{API}/admin/users", json={"email": "AGENT@example.com", "name": "Dup", "profile_id": READ_ONLY}
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["fields"] == {"email": "Already in use"}
    portal = c.post(f"{API}/admin/users", json={"email": "c@example.com", "name": "C", "profile_id": PORTAL})
    assert portal.status_code == 422
    bad_mara = c.post(
        f"{API}/admin/users",
        json={"email": "m@example.com", "name": "M", "profile_id": READ_ONLY, "mara_number": "12"},
    )
    assert bad_mara.status_code == 422
    assert "mara_number" in bad_mara.json()["error"]["fields"]
    bad_profile = c.post(
        f"{API}/admin/users",
        json={"email": "r@example.com", "name": "R", "profile_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert bad_profile.status_code == 422
    bad_email = c.post(
        f"{API}/admin/users", json={"email": "not-an-email", "name": "R", "profile_id": READ_ONLY}
    )
    assert bad_email.status_code == 422


def test_list_users_filters_and_pagination(admin_client: TestClient, db: Session) -> None:
    make_user(db, profile="read_only", email="zed@example.com", name="Zed Auditor")
    make_user(db, profile="finance", email="bea@example.com", name="Bea Accounts", is_active=False)
    make_user(db, profile="finance", email="under_score@example.com", name="Underscore Person")
    c = admin_client
    page = c.get(f"{API}/admin/users", params={"page_size": 2}).json()
    assert page["total"] == 4 and len(page["items"]) == 2 and page["page"] == 1
    assert [u["name"] for u in page["items"]] == ["Ada Admin", "Bea Accounts"]
    assert c.get(f"{API}/admin/users", params={"profile_id": FINANCE}).json()["total"] == 2
    assert c.get(f"{API}/admin/users", params={"is_active": "false"}).json()["total"] == 1
    assert c.get(f"{API}/admin/users", params={"q": "zed"}).json()["items"][0]["email"] == "zed@example.com"
    # LIKE wildcards in the search box are treated literally.
    assert c.get(f"{API}/admin/users", params={"q": "_"}).json()["total"] == 1
    assert c.get(f"{API}/admin/users", params={"page_size": 101}).status_code == 422


def test_update_user_and_audit_diff(admin_client: TestClient, db: Session) -> None:
    target = make_user(db, profile="service_agent", email="t@example.com", name="Tess")
    c = admin_client
    current = c.get(f"{API}/admin/users/{target.id}").json()
    r = c.patch(
        f"{API}/admin/users/{target.id}",
        json={
            "updated_at": current["updated_at"],
            "profile_id": SALES_REP,
            "title": "Senior agent",
            "phone": "",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["profile"]["name"] == "Sales Representative"
    assert r.json()["title"] == "Senior agent"

    entry = db.scalars(select(AuditLog).where(AuditLog.action == "UPDATE")).one()
    assert entry.changes == {
        "profile_id": {"from": str(stable_id("profile", "service_agent")), "to": SALES_REP},
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
    target = make_user(db, profile="finance", email="t@example.com")
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
        f"{API}/admin/users/{me['id']}", json={"updated_at": current["updated_at"], "profile_id": READ_ONLY}
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
    other = make_user(db, email="other-admin@example.com")
    other_now = c.get(f"{API}/admin/users/{other.id}").json()
    r = c.patch(
        f"{API}/admin/users/{other.id}", json={"updated_at": other_now["updated_at"], "profile_id": READ_ONLY}
    )
    assert r.status_code == 200

    # Make the signed-in admin's account the only admin and try to remove it via a second admin session.
    second = make_user(db, email="second@example.com")
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
        f"{API}/admin/users/{second.id}",
        json={"updated_at": second_now["updated_at"], "profile_id": READ_ONLY},
    )
    assert r.status_code == 422


def test_last_admin_rule_directly(db: Session, admin_client: TestClient) -> None:
    from app.auth.deps import AuthContext
    from app.schemas.users import UserUpdate
    from app.services.audit import RequestMeta
    from app.services.users import update_user

    only_admin = db.scalars(select(User).where(User.email == "admin@example.com")).one()
    actor = make_user(db, email="actor@example.com", is_active=False)
    session = UserSession(
        user_id=actor.id, token_hash="x" * 64, csrf_token_hash="y" * 64, expires_at=only_admin.created_at
    )
    ctx = AuthContext(user=actor, session=session)
    with pytest.raises(Exception, match="At least one active System Administrator"):
        update_user(
            db,
            ctx,
            only_admin.id,
            UserUpdate(updated_at=only_admin.updated_at, is_active=False),
            RequestMeta(),
        )


def test_reset_mfa_unlock_revoke_and_resend(admin_client: TestClient, db: Session, outbox: Outbox) -> None:
    secret_user = make_user(db, profile="read_only", email="mfa@example.com", mfa_secret="JBSWY3DPEHPK3PXP")
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
        f"{API}/admin/users", json={"email": "inv@example.com", "name": "Inv", "profile_id": READ_ONLY}
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
    c.post(f"{API}/admin/users", json={"email": "a1@example.com", "name": "A1", "profile_id": READ_ONLY})
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


def test_sign_in_does_not_make_an_open_edit_stale(admin_client: TestClient, db: Session) -> None:
    """Sign-in bookkeeping (last login, failure counter) must not invalidate an administrator's edit."""
    target = make_user(db, profile="read_only", email="busy@example.com")
    loaded = admin_client.get(f"{API}/admin/users/{target.id}").json()
    # Meanwhile the user signs in, fails once and signs in again.
    other = TestClient(admin_client.app)
    assert (
        other.post(
            f"{API}/auth/login", json={"email": target.email, "password": "wrong-password-x"}
        ).status_code
        == 401
    )
    login(other, target.email)
    r = admin_client.patch(
        f"{API}/admin/users/{target.id}", json={"updated_at": loaded["updated_at"], "title": "Analyst"}
    )
    assert r.status_code == 200, r.text
    # A real edit still changes the token, so a second stale save is refused.
    stale = admin_client.patch(
        f"{API}/admin/users/{target.id}", json={"updated_at": loaded["updated_at"], "title": "X"}
    )
    assert stale.status_code == 409


def test_delete_user_transfers_records_and_releases_the_email(admin_client: TestClient, db: Session) -> None:
    """Edge case from testing: the same person added as staff and as a client. Deleting the staff account
    hands their records over and frees the address, so the client can then be invited to the portal."""
    from app.models import Record

    c = admin_client
    staff = make_user(db, profile="service_agent", email="sam@example.com", name="Sam Both")
    login_c = TestClient(c.app)
    login(login_c, "sam@example.com")
    contact = c.post(
        f"{API}/objects/contact/records",
        json={"fields": {"first_name": "Sam", "last_name": "Both", "email": "sam@example.com"}},
    ).json()
    db.execute(text("UPDATE records SET owner_id = :u WHERE id = :r"), {"u": staff.id, "r": contact["id"]})
    db.commit()
    # The address is taken by the staff account, so the client can't get portal access yet.
    assert c.post(f"{API}/portal-users/invite/{contact['id']}").status_code == 409

    assert c.delete(f"{API}/admin/users/{staff.id}").status_code == 200
    db.expire_all()
    gone = db.get(User, staff.id)
    assert gone is not None and gone.is_deleted and not gone.is_active and gone.password_hash is None
    assert gone.name == "Sam Both (deleted)"
    admin = db.scalars(select(User).where(User.email == "admin@example.com")).one()
    assert db.get(Record, contact["id"]).owner_id == admin.id  # type: ignore[union-attr]
    assert db.scalars(select(UserSession).where(UserSession.user_id == staff.id)).all() == []
    assert login_c.get(f"{API}/auth/me").status_code == 401  # signed out everywhere
    assert c.get(f"{API}/admin/users/{staff.id}").status_code == 404
    emails = [u["email"] for u in c.get(f"{API}/admin/users").json()["items"]]
    assert "sam@example.com" not in emails and not any("deleted.invalid" in e for e in emails)
    entry = db.scalars(
        select(AuditLog).where(AuditLog.entity_id == str(staff.id), AuditLog.action == "DELETE")
    ).one()
    assert "sam@example.com" in entry.summary

    # Now the same person can be a client with portal access...
    invited = c.post(f"{API}/portal-users/invite/{contact['id']}")
    assert invited.status_code == 201, invited.text
    assert invited.json()["email"] == "sam@example.com"


def test_delete_portal_user_and_guards(admin_client: TestClient, db: Session) -> None:
    c = admin_client
    contact = c.post(
        f"{API}/objects/contact/records",
        json={"fields": {"first_name": "Pat", "last_name": "Client", "email": "pat@example.com"}},
    ).json()
    portal = c.post(f"{API}/portal-users/invite/{contact['id']}").json()
    r = c.delete(f"{API}/portal-users/{portal['id']}")
    assert r.status_code == 200, r.text
    assert all(u["id"] != portal["id"] for u in c.get(f"{API}/portal-users").json())
    assert c.get(f"{API}/objects/contact/records/{contact['id']}").status_code == 200  # the client stays
    assert c.post(f"{API}/portal-users/invite/{contact['id']}").status_code == 201  # and can be re-invited
    assert c.delete(f"{API}/portal-users/{portal['id']}").status_code == 404  # already deleted

    admin = db.scalars(select(User).where(User.email == "admin@example.com")).one()
    assert c.delete(f"{API}/admin/users/{admin.id}").json()["error"]["code"] == "self_delete"
    staff = make_user(db, profile="finance", email="fin@example.com")
    assert c.delete(f"{API}/portal-users/{staff.id}").status_code == 404  # not a portal user
    bad = c.delete(f"{API}/admin/users/{staff.id}", params={"transfer_to": str(staff.id)})
    assert bad.status_code == 422
    other_admin = make_user(db, email="admin2@example.com")
    ok = c.delete(f"{API}/admin/users/{staff.id}", params={"transfer_to": str(other_admin.id)})
    assert ok.status_code == 200, ok.text


def test_deleting_a_client_switches_off_their_portal_access(admin_client: TestClient, db: Session) -> None:
    c = admin_client
    contact = c.post(
        f"{API}/objects/contact/records",
        json={"fields": {"first_name": "Kim", "last_name": "Client", "email": "kim@example.com"}},
    ).json()
    portal = c.post(f"{API}/portal-users/invite/{contact['id']}").json()
    assert c.delete(f"{API}/objects/contact/records/{contact['id']}").status_code == 204
    db.expire_all()
    assert db.get(User, portal["id"]).is_active is False  # type: ignore[union-attr]

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AuditLog, User, UserSession
from app.permissions.matrix import Role
from tests.conftest import PASSWORD, Outbox, login, make_user, set_csrf

API = "/api/v1"


def actions(db: Session) -> list[str]:
    return [a.action for a in db.scalars(select(AuditLog).order_by(AuditLog.created_at, AuditLog.id))]


# ------------------------------------------------------------------ login basics


def test_login_unknown_and_wrong_password_look_the_same(client: TestClient, db: Session) -> None:
    make_user(db, email="ann@example.com")
    unknown = client.post(f"{API}/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    wrong = client.post(f"{API}/auth/login", json={"email": "ann@example.com", "password": "nope-nope-nope"})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"]["message"] == wrong.json()["error"]["message"]
    assert unknown.json()["error"]["code"] == "invalid_credentials"
    assert "crm_session" not in client.cookies
    assert actions(db) == ["LOGIN_FAILED", "LOGIN_FAILED"]


def test_login_is_case_insensitive_and_sets_hardened_cookies(
    client: TestClient, db: Session, no_mfa: None
) -> None:
    make_user(db, email="ann@example.com", role=Role.AUDITOR)
    r = client.post(f"{API}/auth/login", json={"email": "  ANN@Example.com ", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json() == {"state": "authenticated"}
    cookies = r.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("crm_session="))
    csrf_cookie = next(c for c in cookies if c.startswith("crm_csrf="))
    assert "HttpOnly" in session_cookie and "SameSite=lax" in session_cookie
    assert "HttpOnly" not in csrf_cookie
    me = client.get(f"{API}/auth/me").json()
    assert me["user"]["email"] == "ann@example.com"
    assert me["user"]["role_label"] == "Auditor (read-only)"
    assert me["permissions"]["audit.read"] == "all"
    assert "user.manage" not in me["permissions"]
    assert actions(db) == ["LOGIN"]


def test_inactive_and_invited_users_cannot_sign_in(client: TestClient, db: Session) -> None:
    make_user(db, email="gone@example.com", is_active=False)
    make_user(db, email="invited@example.com", password=None)
    for email in ("gone@example.com", "invited@example.com"):
        r = client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 401


def test_me_requires_session(client: TestClient) -> None:
    r = client.get(f"{API}/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


def test_logout(client: TestClient, db: Session, no_mfa: None) -> None:
    user = make_user(db)
    login(client, user.email)
    r = client.post(f"{API}/auth/logout")
    assert r.status_code == 200
    assert client.get(f"{API}/auth/me").status_code == 401
    assert db.scalar(select(UserSession).where(UserSession.user_id == user.id)) is None
    assert actions(db)[-1] == "LOGOUT"


# ------------------------------------------------------------------ lockout


def test_lockout_after_repeated_failures_and_admin_unlock(
    client: TestClient, db: Session, settings: Settings, no_mfa: None
) -> None:
    user = make_user(db, email="ann@example.com")
    for _ in range(settings.login_max_failures):
        assert (
            client.post(
                f"{API}/auth/login", json={"email": user.email, "password": "bad-password-x"}
            ).status_code
            == 401
        )
    # Correct password is refused while locked.
    r = client.post(f"{API}/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 423
    assert r.json()["error"]["code"] == "account_locked"
    assert "ACCOUNT_LOCKED" in actions(db)

    admin = make_user(db, role=Role.ADMIN, email="admin@example.com")
    admin_client = TestClient(client.app)
    login(admin_client, admin.email)
    assert admin_client.post(f"{API}/admin/users/{user.id}/unlock").status_code == 200
    assert (
        client.post(f"{API}/auth/login", json={"email": user.email, "password": PASSWORD}).status_code == 200
    )


def test_lock_expires(client: TestClient, db: Session, no_mfa: None) -> None:
    user = make_user(db)
    user.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert (
        client.post(f"{API}/auth/login", json={"email": user.email, "password": PASSWORD}).status_code == 200
    )


# ------------------------------------------------------------------ sessions & CSRF


def test_session_idle_and_absolute_expiry(
    client: TestClient, db: Session, settings: Settings, no_mfa: None
) -> None:
    user = make_user(db)
    login(client, user.email)
    assert client.get(f"{API}/auth/me").status_code == 200

    session = db.scalar(select(UserSession).where(UserSession.user_id == user.id))
    assert session is not None
    session.last_seen_at = datetime.now(UTC) - timedelta(minutes=settings.session_idle_minutes + 1)
    db.commit()
    assert client.get(f"{API}/auth/me").status_code == 401
    assert db.scalar(select(UserSession).where(UserSession.user_id == user.id)) is None

    login(client, user.email)
    session = db.scalar(select(UserSession).where(UserSession.user_id == user.id))
    assert session is not None
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert client.get(f"{API}/auth/me").status_code == 401


def test_deactivated_user_session_stops_working(client: TestClient, db: Session, no_mfa: None) -> None:
    user = make_user(db)
    login(client, user.email)
    db.get(User, user.id).is_active = False  # type: ignore[union-attr]
    db.commit()
    assert client.get(f"{API}/auth/me").status_code == 401


def test_csrf_token_required_for_unsafe_requests(client: TestClient, db: Session, no_mfa: None) -> None:
    user = make_user(db)
    login(client, user.email)
    client.headers.pop("X-CSRF-Token")
    r = client.post(f"{API}/auth/logout")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "csrf_failed"
    r = client.post(f"{API}/auth/logout", headers={"X-CSRF-Token": "forged-token-value"})
    assert r.status_code == 403
    # GET requests do not need the token.
    assert client.get(f"{API}/auth/me").status_code == 200


def test_cross_site_origin_rejected(client: TestClient, db: Session) -> None:
    make_user(db, email="ann@example.com")
    r = client.post(
        f"{API}/auth/login",
        json={"email": "ann@example.com", "password": PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "csrf_failed"
    ok = client.post(
        f"{API}/auth/login",
        json={"email": "ann@example.com", "password": PASSWORD},
        headers={"Origin": "http://localhost:5173"},
    )
    assert ok.status_code == 200


# ------------------------------------------------------------------ MFA


def test_staff_must_enrol_mfa_before_using_the_app(client: TestClient, db: Session) -> None:
    user = make_user(db, role=Role.ADMIN, email="ann@example.com")
    assert login(client, user.email) == "mfa_setup_required"
    me = client.get(f"{API}/auth/me").json()
    assert me["session"] == {**me["session"], "mfa_verified": False, "mfa_setup_required": True}
    assert me["permissions"] == {}
    blocked = client.get(f"{API}/admin/users")
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "mfa_required"

    old_session = client.cookies.get("crm_session")
    setup = client.post(f"{API}/auth/mfa/setup").json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    assert setup["qr_svg_data_uri"].startswith("data:image/svg+xml;base64,")
    bad = client.post(f"{API}/auth/mfa/enable", json={"code": "000000"})
    assert bad.status_code == 422

    r = client.post(f"{API}/auth/mfa/enable", json={"code": pyotp.TOTP(setup["secret"]).now()})
    assert r.status_code == 200, r.text
    codes = r.json()["recovery_codes"]
    assert len(codes) == 10
    # Session rotated after MFA (no fixation) and now fully authorised.
    assert client.cookies.get("crm_session") != old_session
    set_csrf(client)
    me = client.get(f"{API}/auth/me").json()
    assert me["session"]["mfa_verified"] is True
    assert me["session"]["recovery_codes_remaining"] == 10
    assert client.get(f"{API}/admin/users").status_code == 200
    db.expire_all()
    stored = db.get(User, user.id)
    assert stored is not None and stored.mfa_enabled
    assert setup["secret"] not in (stored.mfa_secret_encrypted or "")
    assert {"MFA_ENABLED", "LOGIN"} <= set(actions(db))

    # Cannot enrol again without an admin reset.
    assert client.post(f"{API}/auth/mfa/setup").status_code == 409


def test_mfa_login_with_totp_replay_protection_and_recovery_codes(client: TestClient, db: Session) -> None:
    secret = pyotp.random_base32()
    user = make_user(db, role=Role.MIGRATION_AGENT, email="ann@example.com", mfa_secret=secret)
    totp = pyotp.TOTP(secret)

    assert login(client, user.email) == "mfa_required"
    assert client.get(f"{API}/admin/users").status_code == 403
    wrong = client.post(f"{API}/auth/mfa/verify", json={"code": "123456"})
    assert wrong.status_code == 422
    assert wrong.json()["error"]["code"] == "invalid_code"
    code = totp.now()
    r = client.post(f"{API}/auth/mfa/verify", json={"code": code})
    assert r.status_code == 200
    assert r.json()["session"]["mfa_verified"] is True
    assert r.json()["permissions"]["matter.lodge"] == "all"
    set_csrf(client)
    assert client.post(f"{API}/auth/mfa/verify", json={"code": code}).status_code == 409  # already verified

    # Replay of the same code in a new sign-in is refused.
    client.post(f"{API}/auth/logout")
    login(client, user.email)
    assert client.post(f"{API}/auth/mfa/verify", json={"code": code}).status_code == 422
    nxt = totp.at(int(time.time()) + 30)
    assert client.post(f"{API}/auth/mfa/verify", json={"code": nxt}).status_code == 200

    # Recovery codes: regenerate (password required), then each works once.
    set_csrf(client)
    bad = client.post(f"{API}/auth/mfa/recovery-codes", json={"password": "wrong-password-x"})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "incorrect_password"
    codes = client.post(f"{API}/auth/mfa/recovery-codes", json={"password": PASSWORD}).json()[
        "recovery_codes"
    ]
    client.post(f"{API}/auth/logout")
    login(client, user.email)
    assert client.post(f"{API}/auth/mfa/verify", json={"code": codes[0].lower()}).status_code == 200
    set_csrf(client)
    assert client.get(f"{API}/auth/me").json()["session"]["recovery_codes_remaining"] == 9
    client.post(f"{API}/auth/logout")
    login(client, user.email)
    assert client.post(f"{API}/auth/mfa/verify", json={"code": codes[0]}).status_code == 422
    assert "RECOVERY_CODE_USED" in actions(db)


def test_repeated_mfa_failures_lock_account(client: TestClient, db: Session, settings: Settings) -> None:
    secret = pyotp.random_base32()
    user = make_user(db, email="ann@example.com", mfa_secret=secret)
    login(client, user.email)
    for _ in range(settings.login_max_failures - 1):
        assert client.post(f"{API}/auth/mfa/verify", json={"code": "000000"}).status_code == 422
    assert client.post(f"{API}/auth/mfa/verify", json={"code": "000000"}).status_code == 422
    # Locked: pending session revoked and sign-in refused.
    assert client.get(f"{API}/auth/me").status_code == 401
    r = client.post(f"{API}/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 423


def test_client_role_mfa_is_optional(client: TestClient, db: Session) -> None:
    user = make_user(db, role=Role.CLIENT, email="client@example.com")
    assert login(client, user.email) == "authenticated"
    me = client.get(f"{API}/auth/me").json()
    assert me["permissions"]["portal.access"] == "all"
    assert me["user"]["is_staff"] is False
    # Clients may opt in; the current session is kept.
    secret = client.post(f"{API}/auth/mfa/setup").json()["secret"]
    session_before = client.cookies.get("crm_session")
    assert client.post(f"{API}/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()}).status_code == 200
    assert client.cookies.get("crm_session") == session_before
    assert client.get(f"{API}/auth/me").status_code == 200


# ------------------------------------------------------------------ passwords


def test_change_password(
    client: TestClient, db: Session, no_mfa: None, settings: Settings, outbox: Outbox
) -> None:
    user = make_user(db, email="ann@example.com", name="Ann Lee")
    other = TestClient(client.app)
    login(other, user.email)
    login(client, user.email)

    wrong = client.post(
        f"{API}/auth/password/change", json={"current_password": "nope", "new_password": "x" * 12}
    )
    assert wrong.status_code == 422
    assert wrong.json()["error"]["fields"] == {"current_password": "Incorrect password"}
    weak = client.post(
        f"{API}/auth/password/change", json={"current_password": PASSWORD, "new_password": "short"}
    )
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "weak_password"

    new = "Brand-New-Passphrase-77"
    r = client.post(f"{API}/auth/password/change", json={"current_password": PASSWORD, "new_password": new})
    assert r.status_code == 200
    # This session stays; the other device is signed out.
    assert client.get(f"{API}/auth/me").status_code == 200
    assert other.get(f"{API}/auth/me").status_code == 401
    assert (
        client.post(f"{API}/auth/login", json={"email": user.email, "password": PASSWORD}).status_code == 401
    )
    assert login(TestClient(client.app), user.email, new) == "authenticated"


def test_forgot_and_reset_password(client: TestClient, db: Session, outbox: Outbox, no_mfa: None) -> None:
    user = make_user(db, email="ann@example.com")
    signed_in = TestClient(client.app)
    login(signed_in, user.email)

    unknown = client.post(f"{API}/auth/password/forgot", json={"email": "nobody@example.com"})
    known = client.post(f"{API}/auth/password/forgot", json={"email": "ANN@example.com"})
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    assert [m[0] for m in outbox.messages] == ["ann@example.com"]
    assert "http://localhost:5173/reset-password#token=" in outbox.messages[0][2]
    token = outbox.token_for("ann@example.com")

    weak = client.post(f"{API}/auth/password/reset", json={"token": token, "new_password": "short"})
    assert weak.status_code == 422
    new = "Reset-Passphrase-2026"
    assert (
        client.post(f"{API}/auth/password/reset", json={"token": token, "new_password": new}).status_code
        == 200
    )
    # Single use, all sessions revoked, new password works.
    again = client.post(f"{API}/auth/password/reset", json={"token": token, "new_password": new + "x"})
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "invalid_token"
    assert signed_in.get(f"{API}/auth/me").status_code == 401
    assert login(TestClient(client.app), user.email, new) == "authenticated"


def test_new_reset_link_invalidates_old_and_links_expire(
    client: TestClient, db: Session, outbox: Outbox
) -> None:
    from app.models import UserToken

    make_user(db, email="ann@example.com")
    client.post(f"{API}/auth/password/forgot", json={"email": "ann@example.com"})
    first = outbox.token_for("ann@example.com")
    client.post(f"{API}/auth/password/forgot", json={"email": "ann@example.com"})
    second = outbox.token_for("ann@example.com")
    body = {"new_password": "Reset-Passphrase-2026"}
    assert client.post(f"{API}/auth/password/reset", json={"token": first, **body}).status_code == 400

    for row in db.scalars(select(UserToken)):
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert client.post(f"{API}/auth/password/reset", json={"token": second, **body}).status_code == 400


# ------------------------------------------------------------------ invitations


def test_invitation_flow(client: TestClient, db: Session, outbox: Outbox, no_mfa: None) -> None:
    admin = make_user(db, role=Role.ADMIN, email="admin@example.com", name="Ada Admin")
    login(client, admin.email)
    r = client.post(
        f"{API}/admin/users",
        json={"email": "New.Officer@Example.com", "name": "Nia Officer", "role": "CASE_OFFICER"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["has_password"] is False
    token = outbox.token_for("new.officer@example.com")
    assert "Ada Admin" in outbox.messages[-1][2]

    anon = TestClient(client.app)
    info = anon.post(f"{API}/auth/invitation/inspect", json={"token": token})
    assert info.json() == {"email": "new.officer@example.com", "name": "Nia Officer"}
    weak = anon.post(f"{API}/auth/invitation/accept", json={"token": token, "password": "nia-officer-123"})
    assert weak.status_code == 422  # contains the name
    ok = anon.post(f"{API}/auth/invitation/accept", json={"token": token, "password": "Welcome-Aboard-2026"})
    assert ok.status_code == 200
    assert anon.post(f"{API}/auth/invitation/inspect", json={"token": token}).status_code == 400
    assert (
        anon.post(
            f"{API}/auth/invitation/accept", json={"token": token, "password": "Other-Pass-20266"}
        ).status_code
        == 400
    )
    assert login(anon, "new.officer@example.com", "Welcome-Aboard-2026") == "authenticated"
    assert "INVITATION_ACCEPTED" in actions(db)


def test_invalid_token_values(client: TestClient) -> None:
    assert client.post(f"{API}/auth/invitation/inspect", json={"token": "x" * 43}).status_code == 400
    assert client.post(f"{API}/auth/invitation/inspect", json={"token": "short"}).status_code == 422


# ------------------------------------------------------------------ rate limiting


def test_login_rate_limit(
    client: TestClient, db: Session, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "login_max_failures", 50)
    make_user(db, email="ann@example.com")
    codes = [
        client.post(
            f"{API}/auth/login", json={"email": "ann@example.com", "password": "wrong-pass-123"}
        ).status_code
        for _ in range(11)
    ]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


def test_rate_limiter_fails_open_without_redis(
    client: TestClient, db: Session, settings: Settings, monkeypatch: pytest.MonkeyPatch, no_mfa: None
) -> None:
    import redis

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(
        "app.core.rate_limit.get_redis", lambda: redis.Redis.from_url("redis://127.0.0.1:1/0")
    )
    user = make_user(db)
    assert login(client, user.email) == "authenticated"

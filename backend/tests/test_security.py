from __future__ import annotations

import pyotp
import pytest

from app.auth import security


def test_password_hash_roundtrip() -> None:
    h = security.hash_password("Correct-Horse-Battery-9")
    assert h.startswith("$argon2id$")
    assert security.verify_password(h, "Correct-Horse-Battery-9")
    assert not security.verify_password(h, "wrong")
    assert not security.verify_password(None, "anything")
    assert not security.verify_password("not-a-hash", "anything")


@pytest.mark.parametrize(
    ("password", "fragment"),
    [
        ("short", "at least 12"),
        ("x" * 129, "at most 128"),
        ("password1234", "too common"),
        ("aaaaaaaaaaaaaaaa", "too common"),
        ("jane.doe-likes-tea", "e-mail"),
        ("Smithfield-2026-xx", "name"),
    ],
)
def test_password_policy_rejections(password: str, fragment: str) -> None:
    errors = security.password_policy_errors(password, email="jane.doe@example.com", name="Ann Smithfield")
    assert any(fragment in e for e in errors), errors


def test_password_policy_accepts_good_password() -> None:
    assert (
        security.password_policy_errors("Correct-Horse-Battery-9", email="a@example.com", name="Ann Lee")
        == []
    )


def test_tokens() -> None:
    a, b = security.generate_token(), security.generate_token()
    assert a != b and len(a) >= 43
    assert security.hash_token(a) == security.hash_token(a)
    assert len(security.hash_token(a)) == 64
    assert security.tokens_equal("abc", "abc") and not security.tokens_equal("abc", "abd")


def test_field_encryption() -> None:
    cipher = security.encrypt_field("JBSWY3DPEHPK3PXP")
    assert "JBSWY3DPEHPK3PXP" not in cipher
    assert security.decrypt_field(cipher) == "JBSWY3DPEHPK3PXP"
    with pytest.raises(ValueError, match="cannot be decrypted"):
        security.decrypt_field("gAAAAA-not-valid")


def test_totp_drift_and_replay() -> None:
    secret = security.new_totp_secret()
    totp = pyotp.TOTP(secret)
    now = 1_800_000_000
    step = int(now // 30)
    assert security.verify_totp(secret, totp.at(now), last_used_step=None, now=now) == step
    # One step of drift either way is accepted.
    assert security.verify_totp(secret, totp.at(now - 30), last_used_step=None, now=now) == step - 1
    assert security.verify_totp(secret, totp.at(now + 30), last_used_step=None, now=now) == step + 1
    assert security.verify_totp(secret, totp.at(now + 90), last_used_step=None, now=now) is None
    # Replay of an already-used step is rejected.
    assert security.verify_totp(secret, totp.at(now), last_used_step=step, now=now) is None
    assert security.verify_totp(secret, "12ab56", last_used_step=None, now=now) is None
    assert security.verify_totp(secret, "123", last_used_step=None, now=now) is None


def test_totp_uri() -> None:
    uri = security.totp_uri("JBSWY3DPEHPK3PXP", "a@example.com")
    assert uri.startswith("otpauth://totp/MigrateCRM:a%40example.com?")
    assert "issuer=MigrateCRM" in uri


def test_recovery_codes() -> None:
    codes = security.generate_recovery_codes()
    assert len(codes) == 10 and len(set(codes)) == 10
    assert all(len(c) == 11 and c[5] == "-" for c in codes)
    code = codes[0]
    assert security.hash_recovery_code(code) == security.hash_recovery_code(
        f" {code.lower().replace('-', '')} "
    )

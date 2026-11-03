"""Password hashing, password policy, opaque tokens, field encryption and TOTP helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from functools import lru_cache

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import get_settings

# ---------------------------------------------------------------- passwords

# argon2-cffi defaults follow RFC 9106 recommendations (Argon2id).
_hasher = PasswordHasher()

# Constant used to keep login timing similar for unknown users.
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128

_COMMON_PASSWORDS = frozenset(
    {
        "password1234",
        "password12345",
        "password123!",
        "passw0rd1234",
        "123456789012",
        "qwertyuiop12",
        "qwerty123456",
        "iloveyou1234",
        "welcome12345",
        "letmein12345",
        "administrator",
        "changeme1234",
        "migration123",
        "australia123",
        "abc123456789",
        "111111111111",
        "000000000000",
        "aaaaaaaaaaaa",
        "123123123123",
        "monkey123456",
    }
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Verify a password. Always spends similar time, even without a stored hash."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_policy_errors(password: str, *, email: str | None = None, name: str | None = None) -> list[str]:
    """Return human-readable policy violations (empty list = acceptable). NIST SP 800-63B style:
    length and block-lists rather than composition rules."""
    errors: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
    if len(password) > PASSWORD_MAX_LENGTH:
        errors.append(f"Password must be at most {PASSWORD_MAX_LENGTH} characters.")
    lowered = password.lower()
    if lowered in _COMMON_PASSWORDS or len(set(password)) < 4:
        errors.append("Password is too common or too simple.")
    if email:
        local = email.split("@", 1)[0].lower()
        if len(local) >= 4 and local in lowered:
            errors.append("Password must not contain your e-mail address.")
    if name:
        for part in name.lower().split():
            if len(part) >= 4 and part in lowered:
                errors.append("Password must not contain your name.")
                break
    return errors


# ---------------------------------------------------------------- opaque tokens


def generate_token() -> str:
    """256-bit URL-safe random token (sessions, CSRF, invitations, resets)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


# ---------------------------------------------------------------- field encryption

_DEV_SECRET = "insecure-development-secret-key-do-not-use-in-production"  # noqa: S105


@lru_cache
def _fernet(secret: str) -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"migratecrm-field-encryption").derive(
        secret.encode()
    )
    return Fernet(base64.urlsafe_b64encode(key))


def _secret() -> str:
    settings = get_settings()
    if settings.secret_key is not None:
        return settings.secret_key.get_secret_value()
    if settings.app_env in ("development", "test"):
        return _DEV_SECRET
    raise RuntimeError("SECRET_KEY is not configured")


def encrypt_field(value: str) -> str:
    return _fernet(_secret()).encrypt(value.encode()).decode()


def decrypt_field(value: str) -> str:
    try:
        return _fernet(_secret()).decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Encrypted value cannot be decrypted with the current SECRET_KEY") from exc


# ---------------------------------------------------------------- TOTP (RFC 6238)

TOTP_INTERVAL = 30
TOTP_ISSUER = "MigrateCRM"


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret, interval=TOTP_INTERVAL).provisioning_uri(name=email, issuer_name=TOTP_ISSUER)


def verify_totp(
    secret: str, code: str, *, last_used_step: int | None, now: float | None = None
) -> int | None:
    """Verify a 6-digit code allowing +/- one time-step of clock drift.

    Returns the matched time-step (store it to block replay) or None when invalid/replayed.
    """
    code = code.strip().replace(" ", "")
    if len(code) != 6 or not code.isdigit():
        return None
    now = time.time() if now is None else now
    totp = pyotp.TOTP(secret, interval=TOTP_INTERVAL)
    current_step = int(now // TOTP_INTERVAL)
    for step in (current_step - 1, current_step, current_step + 1):
        if last_used_step is not None and step <= last_used_step:
            continue
        if tokens_equal(totp.generate_otp(step), code):
            return step
    return None


# ---------------------------------------------------------------- recovery codes

RECOVERY_CODE_COUNT = 10
_RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


def generate_recovery_codes() -> list[str]:
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def normalize_recovery_code(code: str) -> str:
    return code.strip().upper().replace("-", "").replace(" ", "")


def hash_recovery_code(code: str) -> str:
    return hash_token(normalize_recovery_code(code))

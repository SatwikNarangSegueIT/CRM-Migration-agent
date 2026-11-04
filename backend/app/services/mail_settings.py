"""Outgoing e-mail configuration for the whole platform.

Environment variables (EMAIL_BACKEND, SMTP_*, ZEPTOMAIL_*) give the defaults. A platform administrator can
override them in Setup -> E-mail & Sign-up; that copy is stored in ``platform.settings`` (key "email") with
the SMTP password and ZeptoMail token encrypted with SECRET_KEY, and takes effect within seconds in every API
and worker process without a redeploy.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field, replace
from email.utils import formataddr, parseaddr
from typing import Any, Literal

from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.auth.security import decrypt_field, encrypt_field
from app.core.config import get_settings

logger = logging.getLogger("app.email")

SETTING_KEY = "email"
_CACHE_SECONDS = 20.0

Provider = Literal["console", "smtp", "zeptomail"]
Security = Literal["starttls", "ssl", "none"]

# Zoho Mail data centres: (label, SMTP host for personal / free accounts, for paid organisation accounts).
# The .com hosts are from Zoho's documentation; check the others in Zoho Mail -> Settings -> Mail Accounts ->
# IMAP / SMTP, which shows the exact host for the account. Ports: 465 (SSL) or 587 (STARTTLS).
ZOHO_SMTP_HOSTS: dict[str, tuple[str, str, str]] = {
    "com": ("United States (zoho.com)", "smtp.zoho.com", "smtppro.zoho.com"),
    "com.au": ("Australia (zoho.com.au)", "smtp.zoho.com.au", "smtppro.zoho.com.au"),
    "eu": ("Europe (zoho.eu)", "smtp.zoho.eu", "smtppro.zoho.eu"),
    "in": ("India (zoho.in)", "smtp.zoho.in", "smtppro.zoho.in"),
}
# ZeptoMail (Zoho's transactional e-mail service). Accounts in other data centres see their own API URL in
# ZeptoMail -> Mail Agents -> SMTP/API.
ZEPTOMAIL_DEFAULT_URL = "https://api.zeptomail.com/v1.1/email"


@dataclass(frozen=True)
class MailConfig:
    provider: Provider
    from_name: str
    from_email: str
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_security: Security = "starttls"
    smtp_username: str | None = None
    smtp_password: str | None = field(default=None, repr=False)
    zeptomail_api_url: str = ZEPTOMAIL_DEFAULT_URL
    zeptomail_token: str | None = field(default=None, repr=False)
    source: Literal["environment", "setup"] = "environment"

    @property
    def configured(self) -> bool:
        """Mail actually leaves the building (not just written to the log)."""
        return self.provider != "console"

    @property
    def sender(self) -> str:
        return formataddr((self.from_name, self.from_email)) if self.from_name else self.from_email

    def public(self) -> dict[str, Any]:
        """Safe to show an administrator: secrets are reduced to whether they are set."""
        return {
            "provider": self.provider,
            "from_name": self.from_name,
            "from_email": self.from_email,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_security": self.smtp_security,
            "smtp_username": self.smtp_username or "",
            "smtp_password_set": bool(self.smtp_password),
            "zeptomail_api_url": self.zeptomail_api_url,
            "zeptomail_token_set": bool(self.zeptomail_token),
            "source": self.source,
        }


def _secret(value: SecretStr | None) -> str | None:
    return value.get_secret_value() if value is not None and value.get_secret_value() else None


def from_environment() -> MailConfig:
    s = get_settings()
    name, address = parseaddr(s.email_from)
    return MailConfig(
        provider=s.email_backend,
        from_name=name,
        from_email=address or "no-reply@localhost",
        smtp_host=s.smtp_host,
        smtp_port=s.smtp_port,
        smtp_security=s.effective_smtp_security,  # type: ignore[arg-type]
        smtp_username=s.smtp_username or None,
        smtp_password=_secret(s.smtp_password),
        zeptomail_api_url=s.zeptomail_api_url,
        zeptomail_token=_secret(s.zeptomail_token),
    )


def _decrypt(value: Any) -> str | None:
    if not value:
        return None
    try:
        return decrypt_field(str(value))
    except ValueError:
        logger.error("Saved e-mail secret can't be decrypted: SECRET_KEY changed? Re-enter it in Setup.")
        return None


def from_saved(value: dict[str, Any]) -> MailConfig:
    base = from_environment()
    return replace(
        base,
        provider=value.get("provider") or base.provider,
        from_name=value.get("from_name", base.from_name) or "",
        from_email=value.get("from_email") or base.from_email,
        smtp_host=value.get("smtp_host") or "",
        smtp_port=int(value.get("smtp_port") or 587),
        smtp_security=value.get("smtp_security") or "starttls",
        smtp_username=value.get("smtp_username") or None,
        smtp_password=_decrypt(value.get("smtp_password_enc")),
        zeptomail_api_url=value.get("zeptomail_api_url") or base.zeptomail_api_url,
        zeptomail_token=_decrypt(value.get("zeptomail_token_enc")),
        source="setup",
    )


# ------------------------------------------------------------------ storage


def load_saved() -> dict[str, Any] | None:
    from app.db.session import get_engine

    try:
        with get_engine().connect() as conn:
            row = conn.execute(
                text("SELECT value FROM platform.settings WHERE key = :k"), {"k": SETTING_KEY}
            ).scalar()
    except DBAPIError as exc:
        if "does not exist" in str(exc.orig):  # platform schema not upgraded yet (run migrate / SQL v6)
            return None
        raise
    return dict(row) if row else None


_lock = threading.Lock()
_cached: tuple[float, MailConfig] | None = None


def mail_config() -> MailConfig:
    """The configuration to send with now (cached for a few seconds per process)."""
    global _cached
    with _lock:
        if _cached is not None and time.monotonic() - _cached[0] < _CACHE_SECONDS:
            return _cached[1]
    try:
        saved = load_saved()
    except Exception:
        logger.warning("Could not read saved e-mail settings; using environment settings", exc_info=True)
        saved = None
    config = from_saved(saved) if saved else from_environment()
    with _lock:
        _cached = (time.monotonic(), config)
    return config


def forget_cached() -> None:
    global _cached
    with _lock:
        _cached = None


def stored_value(values: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    """What to store for ``values`` (from the Setup form). A blank password or token keeps the saved one."""
    previous = previous or {}
    stored = {
        k: values.get(k)
        for k in (
            "provider",
            "from_name",
            "from_email",
            "smtp_host",
            "smtp_port",
            "smtp_security",
            "smtp_username",
            "zeptomail_api_url",
        )
    }
    password = values.get("smtp_password")
    stored["smtp_password_enc"] = encrypt_field(password) if password else previous.get("smtp_password_enc")
    token = values.get("zeptomail_token")
    stored["zeptomail_token_enc"] = encrypt_field(token) if token else previous.get("zeptomail_token_enc")
    return stored


def save(values: dict[str, Any], updated_by: str) -> MailConfig:
    from app.db.session import get_engine

    with get_engine().begin() as conn:
        previous = conn.execute(
            text("SELECT value FROM platform.settings WHERE key = :k FOR UPDATE"), {"k": SETTING_KEY}
        ).scalar()
        import json

        conn.execute(
            text(
                "INSERT INTO platform.settings (key, value, updated_at, updated_by) "
                "VALUES (:k, CAST(:v AS jsonb), now(), :by) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now(), "
                "updated_by = EXCLUDED.updated_by"
            ),
            {"k": SETTING_KEY, "v": json.dumps(stored_value(values, previous)), "by": updated_by},
        )
    forget_cached()
    return mail_config()


def clear() -> MailConfig:
    """Go back to the environment settings."""
    from app.db.session import get_engine

    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM platform.settings WHERE key = :k"), {"k": SETTING_KEY})
    forget_cached()
    return mail_config()


def candidate(values: dict[str, Any]) -> MailConfig:
    """Configuration from unsaved form values (for "Send test e-mail"); blank secrets reuse saved ones."""
    current = mail_config()
    return replace(
        current,
        provider=values.get("provider") or current.provider,
        from_name=values.get("from_name") or "",
        from_email=values.get("from_email") or current.from_email,
        smtp_host=values.get("smtp_host") or "",
        smtp_port=int(values.get("smtp_port") or 587),
        smtp_security=values.get("smtp_security") or "starttls",
        smtp_username=values.get("smtp_username") or None,
        smtp_password=values.get("smtp_password") or current.smtp_password,
        zeptomail_api_url=values.get("zeptomail_api_url") or current.zeptomail_api_url,
        zeptomail_token=values.get("zeptomail_token") or current.zeptomail_token,
        source="setup",
    )

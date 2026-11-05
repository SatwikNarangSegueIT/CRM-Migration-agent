"""Application settings, loaded from environment variables (and `.env` in development)."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]


def normalize_database_url(url: str) -> str:
    """Return a SQLAlchemy URL that uses the psycopg 3 driver.

    Neon (and most providers) hand out ``postgres://`` or ``postgresql://`` URLs.
    """
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    if url.startswith("postgresql+psycopg://"):
        return url
    raise ValueError(
        "DATABASE_URL must be a PostgreSQL URL (postgres://, postgresql:// or postgresql+psycopg://)"
    )


def is_pooled_url(url: str) -> bool:
    """True when the URL points at a Neon pooled (PgBouncer, transaction mode) endpoint."""
    host = urlsplit(url).hostname or ""
    return "-pooler." in host


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True
    )

    app_name: str = "MigrateCRM"
    app_env: Environment = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = True

    # Secret used to sign tokens/encrypt fields in later phases. Mandatory outside development/test.
    secret_key: SecretStr | None = None

    # Neon pooled endpoint for the API and workers.
    database_url: str = Field(default="postgresql+psycopg://crm:crm@localhost:5432/crm")
    # Neon direct (non-pooled) endpoint, used for Alembic migrations. Defaults to database_url.
    database_url_direct: str | None = None
    # None = auto-detect from the host name ("-pooler." => disable prepared statements).
    database_disable_prepared_statements: bool | None = None
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)
    db_pool_recycle_seconds: int = Field(default=300, ge=30)
    db_connect_timeout_seconds: int = Field(default=10, ge=1, le=60)
    # Server-side cap on any single statement (0 = off). Applied as a startup option on direct connections;
    # for Neon's pooled endpoint set it on the role instead (ALTER ROLE ... SET statement_timeout), see
    # docs/operations.md.
    db_statement_timeout_ms: int = Field(default=30_000, ge=0, le=600_000)

    redis_url: str = "redis://localhost:6379/0"

    timezone: str = "Australia/Sydney"

    # ---- Web / auth ----
    # Public URL of the SPA (used for links in e-mails and the Origin check on unsafe requests).
    public_app_url: str = "http://localhost:5173"
    # Extra allowed origins (comma separated), e.g. a staging domain.
    extra_allowed_origins: str = ""
    # None = secure cookies everywhere except development/test.
    cookie_secure: bool | None = None
    session_absolute_hours: int = Field(default=12, ge=1, le=72)
    session_idle_minutes: int = Field(default=60, ge=5, le=24 * 60)
    mfa_required_for_staff: bool = True
    login_max_failures: int = Field(default=5, ge=3, le=20)
    login_lockout_minutes: int = Field(default=15, ge=1, le=24 * 60)
    password_reset_minutes: int = Field(default=30, ge=5, le=24 * 60)
    invitation_hours: int = Field(default=72, ge=1, le=24 * 14)
    # Public sign-up (plan v4, section 4).
    signup_enabled: bool = True
    # "off" (default for now, while the mail service is unavailable): create the workspace straight away and
    # sign the person in. "required": e-mail a confirmation link first. "auto": required in production or
    # whenever e-mail delivery is set up, otherwise off. Set "auto" or "required" once e-mail works again.
    signup_email_verification: Literal["auto", "required", "off"] = "off"
    # Serverless (e.g. Vercel functions): send e-mail and run jobs before the response instead of in
    # background threads, and leave start-up warm-up and pool refills to the scheduled jobs (/api/v1/cron).
    # None = detect (the VERCEL variable is set on Vercel).
    serverless: bool | None = None
    # Bearer secret for /api/v1/cron/<job> (Vercel Cron sends CRON_SECRET in the Authorization header).
    cron_secret: SecretStr | None = None
    signup_verification_hours: int = Field(default=24, ge=1, le=24 * 7)
    # Pre-built workspaces kept ready so sign-up is instant (topped up by the API and the worker).
    signup_warm_pool_size: int = Field(default=2, ge=0, le=50)
    # Workspaces kept ready, already set up, for each profession: sign-up then takes about a second.
    signup_ready_per_domain: int = Field(default=1, ge=0, le=10)
    # Workspace (slug) whose System Administrators run the platform: e-mail delivery and platform status
    # in Setup. Default: the first workspace (the one created by `migrate`, slug "main").
    platform_operator_workspace: str | None = None
    rate_limit_enabled: bool = True
    # Reject passwords found in known breaches (Have I Been Pwned range API, k-anonymity; fails open).
    password_breach_check: bool = True

    # ---- E-mail ----
    # Defaults for outgoing e-mail; a platform administrator can override them in Setup -> E-mail & Sign-up.
    # "console" logs e-mails instead of sending them (development). "smtp": any SMTP server, e.g. Zoho Mail.
    # "zeptomail": Zoho ZeptoMail's HTTP API (works where a host blocks outbound SMTP ports).
    email_backend: Literal["console", "smtp", "zeptomail"] = "console"
    # "auto": the Celery worker sends e-mail when one is running, otherwise the API sends it itself.
    # "queue": always hand e-mail to the worker. "inline": always send from the API.
    email_delivery: Literal["auto", "queue", "inline"] = "auto"
    email_from: str = "Segue CRM <no-reply@localhost>"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    # "starttls" (port 587), "ssl" (implicit TLS, port 465) or "none". Empty: from SMTP_STARTTLS and port.
    smtp_security: Literal["starttls", "ssl", "none"] | None = None
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = True
    # Zoho ZeptoMail: the API URL of your account's data centre and a "Send Mail" token.
    zeptomail_api_url: str = "https://api.zeptomail.com/v1.1/email"
    zeptomail_token: SecretStr | None = None
    # Optional bounce address (a bounce domain configured in the ZeptoMail Mail Agent).
    zeptomail_bounce_address: str | None = None

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        return normalize_database_url(v)

    @field_validator("database_url_direct", mode="before")
    @classmethod
    def _normalize_direct_url(cls, v: str | None) -> str | None:
        if v is None or str(v).strip() == "":
            return None
        return normalize_database_url(v)

    @model_validator(mode="after")
    def _public_url_on_vercel(self) -> Settings:
        """Links in e-mails use PUBLIC_APP_URL. On Vercel, when it is unset or still a local address (e.g. a
        copied .env's http://localhost:5173), the project's production address is used instead."""
        production = (os.environ.get("VERCEL_PROJECT_PRODUCTION_URL") or "").strip().rstrip("/")
        if not production:
            return self
        host = (urlsplit(self.public_app_url.strip()).hostname or "").lower()
        local = host in ("", "localhost", "::1") or host.startswith(("127.", "0."))
        if "public_app_url" not in self.model_fields_set or local:
            self.public_app_url = production if "://" in production else f"https://{production}"
        return self

    @model_validator(mode="after")
    def _check_production_requirements(self) -> Settings:
        weak_key = self.secret_key is None or len(self.secret_key.get_secret_value()) < 32
        if self.app_env in ("staging", "production") and weak_key:
            raise ValueError("SECRET_KEY of at least 32 characters is required in staging/production")
        if self.app_env == "production" and not self.mfa_required_for_staff:
            raise ValueError("MFA_REQUIRED_FOR_STAFF cannot be disabled in production")
        # E-mail is only mandatory when sign-up depends on it (confirmation links).
        if (
            self.app_env == "production"
            and self.email_backend == "console"
            and self.signup_email_verification == "required"
        ):
            raise ValueError(
                "EMAIL_BACKEND must be 'smtp' or 'zeptomail' in production when "
                "SIGNUP_EMAIL_VERIFICATION=required"
            )
        if self.app_env == "production" and self.cookie_secure is False:
            raise ValueError("COOKIE_SECURE cannot be disabled in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def effective_smtp_security(self) -> str:
        if self.smtp_security:
            return self.smtp_security
        if self.smtp_port == 465:
            return "ssl"
        return "starttls" if self.smtp_starttls else "none"

    @property
    def secure_cookies(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.app_env not in ("development", "test")

    @property
    def is_serverless(self) -> bool:
        """Running as short-lived functions (Vercel): no background threads outlive the request."""
        if self.serverless is not None:
            return self.serverless
        return bool(os.environ.get("VERCEL"))

    @property
    def allowed_origins(self) -> set[str]:
        origins = {self.public_app_url.rstrip("/")}
        origins |= {o.strip().rstrip("/") for o in self.extra_allowed_origins.split(",") if o.strip()}
        # On Vercel, the deployment's own addresses (production domain, branch and preview URLs).
        for var in ("VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_BRANCH_URL", "VERCEL_URL"):
            host = os.environ.get(var)
            if host:
                origins.add(f"https://{host.strip().rstrip('/')}")
        return origins

    @property
    def migration_database_url(self) -> str:
        return self.database_url_direct or self.database_url

    @property
    def disable_prepared_statements(self) -> bool:
        if self.database_disable_prepared_statements is not None:
            return self.database_disable_prepared_statements
        return is_pooled_url(self.database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()

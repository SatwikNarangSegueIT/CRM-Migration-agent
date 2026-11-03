"""Application settings, loaded from environment variables (and `.env` in development)."""

from __future__ import annotations

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

    redis_url: str = "redis://localhost:6379/0"

    timezone: str = "Australia/Sydney"

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
    def _check_production_requirements(self) -> Settings:
        weak_key = self.secret_key is None or len(self.secret_key.get_secret_value()) < 32
        if self.app_env in ("staging", "production") and weak_key:
            raise ValueError("SECRET_KEY of at least 32 characters is required in staging/production")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

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

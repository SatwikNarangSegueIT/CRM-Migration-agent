import pytest
from pydantic import ValidationError

from app.core.config import Settings, is_pooled_url, normalize_database_url

NEON_POOLED = "postgresql://u:p@ep-cool-sun-123456-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require"
NEON_DIRECT = "postgresql://u:p@ep-cool-sun-123456.ap-southeast-2.aws.neon.tech/neondb?sslmode=require"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql://u:p@h/db?sslmode=require", "postgresql+psycopg://u:p@h/db?sslmode=require"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ],
)
def test_normalize_database_url(raw: str, expected: str) -> None:
    assert normalize_database_url(raw) == expected


def test_normalize_rejects_non_postgres() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        normalize_database_url("sqlite:///x.db")


def test_pooled_detection() -> None:
    assert is_pooled_url(NEON_POOLED)
    assert not is_pooled_url(NEON_DIRECT)


def _settings(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)  # type: ignore[arg-type]


def test_prepared_statements_auto_disabled_for_pooler() -> None:
    assert _settings(database_url=NEON_POOLED).disable_prepared_statements is True
    assert _settings(database_url=NEON_DIRECT).disable_prepared_statements is False


def test_prepared_statements_override() -> None:
    s = _settings(database_url=NEON_DIRECT, database_disable_prepared_statements=True)
    assert s.disable_prepared_statements is True


def test_migration_url_prefers_direct() -> None:
    s = _settings(database_url=NEON_POOLED, database_url_direct=NEON_DIRECT)
    assert s.migration_database_url == normalize_database_url(NEON_DIRECT)
    assert _settings(database_url=NEON_POOLED).migration_database_url == normalize_database_url(NEON_POOLED)


def test_production_requires_secret_key() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _settings(app_env="production")
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _settings(app_env="production", secret_key="too-short")
    assert _settings(app_env="production", secret_key="x" * 32).is_production

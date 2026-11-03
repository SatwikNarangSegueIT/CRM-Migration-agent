"""Alembic chain must upgrade to head and downgrade to base cleanly."""

from __future__ import annotations

from tests.conftest import run_alembic


def test_upgrade_downgrade_roundtrip() -> None:
    run_alembic("downgrade", "base")
    run_alembic("upgrade", "head")
    run_alembic("downgrade", "-1")
    run_alembic("upgrade", "head")


def test_single_head_and_models_match_migrations() -> None:
    heads = [line for line in run_alembic("heads").splitlines() if "(head)" in line]
    assert len(heads) == 1
    # Fails if a model change has no migration.
    assert "No new upgrade operations detected" in run_alembic("check")

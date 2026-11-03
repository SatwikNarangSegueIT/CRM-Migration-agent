"""Alembic chain must upgrade to head and downgrade to base cleanly."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.conftest import TEST_DATABASE_URL

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic(*args: str) -> str:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", "-x", f"url={TEST_DATABASE_URL}", *args],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout + result.stderr


def test_upgrade_downgrade_roundtrip() -> None:
    _alembic("upgrade", "head")
    _alembic("downgrade", "base")
    _alembic("upgrade", "head")


def test_single_head() -> None:
    heads = [line for line in _alembic("heads").splitlines() if "(head)" in line]
    assert len(heads) == 1

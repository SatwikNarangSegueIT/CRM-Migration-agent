"""Organisation settings (org_settings), with shipped defaults."""

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Setting

EDITABLE_KEYS = (
    "branding",
    "company",
    "billing",
    "case_sla",
    "service",
    "locale",
    "retention",
    "marketing",
    "lead_conversion",
)


def defaults() -> dict[str, Any]:
    from app.engine.standard_v1 import DEFAULT_SETTINGS

    return copy.deepcopy(DEFAULT_SETTINGS)


def get_setting(db: Session, key: str) -> Any:
    row = db.get(Setting, key)
    base = defaults().get(key)
    if row is None:
        return base
    if isinstance(base, dict) and isinstance(row.value, dict):
        return {**base, **row.value}
    return row.value


def all_settings(db: Session) -> dict[str, Any]:
    out = defaults()
    for row in db.scalars(select(Setting)):
        if isinstance(out.get(row.key), dict) and isinstance(row.value, dict):
            out[row.key] = {**out[row.key], **row.value}
        else:
            out[row.key] = row.value
    return out


def set_setting(db: Session, key: str, value: Any) -> Setting:
    row = db.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.flush()
    return row

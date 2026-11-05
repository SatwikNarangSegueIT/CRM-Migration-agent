"""Organisation settings (org_settings), with shipped defaults."""

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import new_cache, revisions, tenant_of
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


# All of a workspace's stored settings, read in one query and cached in memory per workspace and metadata
# revision (app.core.cache). Saving a setting bumps the revision in the same transaction, so every process
# sees the change once it commits, and the saving session itself reads past the cache until then.
_stored_cache = new_cache(256)


def _stored(db: Session) -> dict[str, Any]:
    key = (tenant_of(db), "settings", revisions(db).metadata)
    return _stored_cache.get_or_build(db, key, lambda: {r.key: r.value for r in db.scalars(select(Setting))})


def get_setting(db: Session, key: str) -> Any:
    stored = _stored(db)
    base = defaults().get(key)
    if key not in stored:
        return base
    value = copy.deepcopy(stored[key])  # the cached copy is shared: callers may change what they get
    if isinstance(base, dict) and isinstance(value, dict):
        return {**base, **value}
    return value


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
    from app.engine.meta import bump_revision

    bump_revision(db)  # cached settings (and metadata) are rebuilt once this commits
    return row

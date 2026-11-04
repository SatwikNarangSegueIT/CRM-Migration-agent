"""Bring an installed profession pack up to the code's version without touching what an administrator owns.

Re-installing a pack would also re-apply its profiles' object permissions, undoing an administrator's
changes. This upgrade only adds: new objects and fields, list views, reports and field security (all
inserted with ON CONFLICT DO NOTHING), new picklist values, and new fields placed on the existing forms.
Each form placement is recorded and applied once, so a field an administrator later takes off a form is
not put back by a later upgrade.

A pack's definition module may declare:
    NEW_ON_FORMS:  [(object, field, after_field)]   fields to place on the existing page layout
    NEW_PICKLIST_VALUES: [(object, field, value, after_value, colour)]
    upgrade(conn): add-only extras (reports, field security for new fields)
"""

from __future__ import annotations

import importlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.installer import install_bundle
from app.models import FieldDefinition, ObjectDefinition

_APPLIED = "pack_form_additions"


def _definition(pack_key: str) -> Any:
    return importlib.import_module(f"app.packs.{pack_key}.definition")


def _field(db: Session, obj: str, api: str) -> FieldDefinition | None:
    return db.scalar(
        select(FieldDefinition)
        .join(ObjectDefinition, ObjectDefinition.id == FieldDefinition.object_id)
        .where(ObjectDefinition.api_name == obj, FieldDefinition.api_name == api)
    )


def place_new_fields(db: Session, additions: list[tuple[str, str, str | None]]) -> int:
    """Put each new field on its object's form, after `after_field` (once per workspace)."""
    from app.services.settings import get_setting, set_setting

    applied = set(get_setting(db, _APPLIED) or [])
    changed = 0
    for obj_api, field, after in additions:
        key = f"{obj_api}.{field}"
        if key in applied:
            continue
        obj = db.scalar(select(ObjectDefinition).where(ObjectDefinition.api_name == obj_api))
        if obj is None or _field(db, obj_api, field) is None:
            continue  # the object or field isn't installed here; try again next upgrade
        applied.add(key)
        layout = [dict(sec, fields=list(sec.get("fields", []))) for sec in obj.page_layout or []]
        if not layout or any(field in sec["fields"] for sec in layout):
            continue
        target = next((sec for sec in layout if after and after in sec["fields"]), None)
        if target is None:
            target = next((sec for sec in layout if sec.get("label") != "System Information"), layout[0])
            target["fields"].append(field)
        else:
            target["fields"].insert(target["fields"].index(after) + 1, field)
        obj.page_layout = layout
        changed += 1
    set_setting(db, _APPLIED, sorted(applied))
    return changed


def place_new_tabs(db: Session, tabs: list[tuple[str, dict[str, Any], str | None]]) -> int:
    """Add each new tab to the pack's app, after the tab for `after` (once per workspace)."""
    from app.models import App
    from app.services.settings import get_setting, set_setting

    applied = set(get_setting(db, _APPLIED) or [])
    changed = 0
    for app_key, tab, after in tabs:
        key = f"tab:{app_key}.{tab.get('object') or tab.get('kind')}"
        app = db.scalar(select(App).where(App.key == app_key))
        if key in applied or app is None:
            continue
        applied.add(key)
        current = [dict(t) for t in app.tabs or []]
        if any(t.get("kind") == tab.get("kind") and t.get("object") == tab.get("object") for t in current):
            continue
        at = next((i + 1 for i, t in enumerate(current) if t.get("object") == after), len(current))
        current.insert(at, dict(tab))
        app.tabs = current
        changed += 1
    set_setting(db, _APPLIED, sorted(applied))
    return changed


def add_picklist_values(db: Session, values: list[tuple[str, str, str, str | None, str | None]]) -> int:
    changed = 0
    for obj_api, field, value, after, colour in values:
        f = _field(db, obj_api, field)
        if f is None:
            continue
        options = dict(f.options or {})
        current = [dict(v) for v in options.get("values", [])]
        if any(v.get("value") == value for v in current):
            continue
        new = {"value": value, "label": value, "active": True, **({"color": colour} if colour else {})}
        at = next((i + 1 for i, v in enumerate(current) if v.get("value") == after), len(current))
        current.insert(at, new)
        f.options = {**options, "values": current}
        changed += 1
    return changed


def upgrade_pack(db: Session, pack_key: str | None) -> int:
    """Add what this version of the pack brings. Returns how many form or value changes were made."""
    from app import packs
    from app.models import PackInstallation

    if not pack_key:
        return 0
    row = db.scalar(select(PackInstallation).where(PackInstallation.pack_key == pack_key))
    if row is None:
        return 0
    pack = packs.get(pack_key)
    conn = db.connection()
    install_bundle(conn, pack.bundle(), pack_key=pack.key)
    definition = _definition(pack_key)
    extra = getattr(definition, "upgrade", None)
    if extra is not None:
        extra(conn)
    db.flush()
    changed = add_picklist_values(db, list(getattr(definition, "NEW_PICKLIST_VALUES", [])))
    changed += place_new_fields(db, list(getattr(definition, "NEW_ON_FORMS", [])))
    changed += place_new_tabs(db, list(getattr(definition, "NEW_APP_TABS", [])))
    if row.version != pack.version:
        row.version = pack.version
        changed += 1
    return changed


def mark_forms_current(db: Session, pack_key: str | None) -> None:
    """A freshly installed pack already has its fields on the forms: record them as placed."""
    from app.services.settings import get_setting, set_setting

    if not pack_key:
        return
    definition = _definition(pack_key)
    additions = getattr(definition, "NEW_ON_FORMS", [])
    tabs = getattr(definition, "NEW_APP_TABS", [])
    applied = (
        set(get_setting(db, _APPLIED) or [])
        | {f"{o}.{f}" for o, f, _ in additions}
        | {f"tab:{a}.{t.get('object') or t.get('kind')}" for a, t, _ in tabs}
    )
    set_setting(db, _APPLIED, sorted(applied))

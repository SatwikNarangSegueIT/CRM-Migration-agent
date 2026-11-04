"""/setup/practice-settings: each installed profession pack's settings (rates, thresholds, due dates and
reminder lead times), described by the pack's SETTINGS_FIELDS so Setup can show a form for them.

Values are validated by kind; a key like "return_due.FBT Return" sets one entry of a nested setting.
Changing them needs Customize Application.
"""

from __future__ import annotations

import importlib
import re
from datetime import date
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.engine.deps import Records
from app.models import PackInstallation
from app.security.catalog import SystemPermission
from app.services import audit
from app.services.audit import AuditAction
from app.services.settings import get_setting, set_setting

router = APIRouter(prefix="/setup/practice-settings", tags=["setup: practice settings"])

DD_MM = re.compile(r"^(\d{2})-(\d{2})$")


class PracticeSettingsIn(BaseModel):
    values: dict[str, Any]


def _definition(pack_key: str) -> Any | None:
    try:
        return importlib.import_module(f"app.packs.{pack_key}.definition")
    except ModuleNotFoundError:
        return None


def _value(stored: dict[str, Any], defaults: dict[str, Any], key: str) -> Any:
    if "." in key:
        parent, child = key.split(".", 1)
        return {**(defaults.get(parent) or {}), **(stored.get(parent) or {})}.get(child)
    return stored.get(key, defaults.get(key))


def _pack_settings(svc: Any, row: PackInstallation) -> dict[str, Any] | None:
    from app import packs

    definition = _definition(row.pack_key)
    fields = getattr(definition, "SETTINGS_FIELDS", None)
    if not fields:
        return None
    defaults = dict(getattr(definition, "SETTINGS_DEFAULTS", {}))
    stored = get_setting(svc.db, row.pack_key) or {}
    return {
        "pack_key": row.pack_key,
        "title": packs.get(row.pack_key).name,
        "fields": fields,
        "values": {f["key"]: _value(stored, defaults, f["key"]) for f in fields},
    }


def _can_read(svc: Any) -> bool:
    return any(
        svc.policy.has(p) for p in (SystemPermission.VIEW_SETUP, SystemPermission.CUSTOMIZE_APPLICATION)
    )


@router.get("")
def read_practice_settings(svc: Records) -> list[dict[str, Any]]:
    if not _can_read(svc):
        raise PermissionDeniedError("You don't have access to Setup.")
    rows = svc.db.scalars(select(PackInstallation).where(PackInstallation.is_enabled)).all()
    return [s for s in (_pack_settings(svc, r) for r in rows) if s is not None]


def _invalid(key: str, message: str) -> AppError:
    return AppError(message, status_code=422, code="validation_error", fields={key: message})


def _clean(field: dict[str, Any], value: Any) -> Any:
    key, kind = field["key"], field["kind"]
    if kind in ("currency", "number"):
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise _invalid(key, "Enter a number.") from exc
        if number < 0:
            raise _invalid(key, "Enter zero or more.")
        return int(number) if number.is_integer() and kind == "number" else round(number, 2)
    if kind == "checkbox":
        return bool(value)
    if kind == "days":
        items = value if isinstance(value, list) else str(value or "").replace(";", ",").split(",")
        try:
            days = sorted({int(str(v).strip()) for v in items if str(v).strip()}, reverse=True)
        except ValueError as exc:
            raise _invalid(key, "Enter whole numbers of days, separated by commas.") from exc
        if any(d < 0 or d > 365 for d in days):
            raise _invalid(key, "Use 0 to 365 days.")
        return days
    if kind == "multi":
        options = set(field.get("options") or [])
        chosen = [v for v in (value or []) if v in options]
        if len(chosen) != len(value or []):
            raise _invalid(key, "Choose from the list.")
        return chosen
    if kind == "select":
        allowed = {o["value"] for o in field.get("options") or []}
        if value not in allowed:
            raise _invalid(key, "Choose from the list.")
        return value
    text = str(value or "").strip()[:120]
    if key.startswith("return_due."):
        m = DD_MM.match(text)
        try:
            date(2024, int(m.group(2)), int(m.group(1))) if m else None  # 2024: allows 29-02
        except ValueError:
            m = None
        if not m:
            raise _invalid(key, "Use DD-MM, e.g. 31-10.")
    if key == "tax_agent_number" and text and not re.fullmatch(r"\d{8}", text):
        raise _invalid(key, "A registered tax agent number has 8 digits.")
    return text


@router.put("/{pack_key}")
def write_practice_settings(pack_key: str, body: PracticeSettingsIn, svc: Records) -> dict[str, Any]:
    if not svc.policy.has(SystemPermission.CUSTOMIZE_APPLICATION):
        raise PermissionDeniedError("You don't have permission to change practice settings.")
    row = svc.db.scalar(select(PackInstallation).where(PackInstallation.pack_key == pack_key))
    definition = _definition(pack_key)
    fields = {f["key"]: f for f in getattr(definition, "SETTINGS_FIELDS", None) or []}
    if row is None or not fields:
        raise NotFoundError("Practice settings not found.")
    unknown = set(body.values) - set(fields)
    if unknown:
        raise _invalid(sorted(unknown)[0], "Unknown setting.")
    before = dict(get_setting(svc.db, pack_key) or {})
    merged = dict(before)
    for key, value in body.values.items():
        clean = _clean(fields[key], value)
        if "." in key:
            parent, child = key.split(".", 1)
            defaults = dict(getattr(definition, "SETTINGS_DEFAULTS", {}).get(parent) or {})
            merged[parent] = {**defaults, **(merged.get(parent) or {}), child: clean}
        else:
            merged[key] = clean
    set_setting(svc.db, pack_key, merged)
    audit.record(
        svc.db,
        action=AuditAction.UPDATE,
        entity_type="org_setting",
        entity_id=pack_key,
        summary=f"Updated practice settings ({pack_key})",
        actor_id=svc.user_id,
        changes=audit.diff(before, merged),
        meta=svc.request_meta,
    )
    svc.db.commit()
    result = _pack_settings(svc, row)
    assert result is not None
    return result

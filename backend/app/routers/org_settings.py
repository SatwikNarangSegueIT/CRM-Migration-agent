"""/setup/settings: organisation settings (branding, company, billing, SLAs, marketing, retention...).

Billing settings need Manage Billing Settings; everything else needs Customize Application.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.errors import AppError, PermissionDeniedError
from app.core.validators import digits, is_valid_abn
from app.engine.deps import Records
from app.security.catalog import SystemPermission
from app.services import audit
from app.services.audit import AuditAction
from app.services.settings import EDITABLE_KEYS, all_settings, defaults, get_setting, set_setting

router = APIRouter(prefix="/setup/settings", tags=["setup: settings"])

BILLING_KEYS = {"billing", "company"}
HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{6}")
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class SettingIn(BaseModel):
    value: dict[str, Any]


def _can_read(svc: Any) -> bool:
    return any(
        svc.policy.has(p)
        for p in (
            SystemPermission.VIEW_SETUP,
            SystemPermission.CUSTOMIZE_APPLICATION,
            SystemPermission.MANAGE_BILLING_SETTINGS,
        )
    )


@router.get("")
def read_settings(svc: Records) -> dict[str, Any]:
    if not _can_read(svc):
        raise PermissionDeniedError("You don't have access to Setup.")
    return {k: v for k, v in all_settings(svc.db).items() if k in EDITABLE_KEYS}


@router.put("/{key}")
def write_setting(key: str, body: SettingIn, svc: Records) -> dict[str, Any]:
    if key not in EDITABLE_KEYS:
        raise AppError("Unknown setting.", status_code=404, code="not_found")
    needed = (
        SystemPermission.MANAGE_BILLING_SETTINGS
        if key in BILLING_KEYS
        else SystemPermission.CUSTOMIZE_APPLICATION
    )
    if not (
        svc.policy.has(needed)
        or (key == "company" and svc.policy.has(SystemPermission.CUSTOMIZE_APPLICATION))
    ):
        raise PermissionDeniedError("You don't have permission to change these settings.")
    template = defaults().get(key)
    if isinstance(template, dict):
        unknown = set(body.value) - set(template)
        if unknown:
            raise AppError(
                f"Unknown setting {sorted(unknown)[0]!r}.", status_code=422, code="validation_error"
            )
    if key == "case_sla":
        for priority, sla in body.value.items():
            if not isinstance(sla, dict) or not all(
                isinstance(sla.get(k), int | float) and sla[k] > 0
                for k in ("first_response_hours", "resolution_hours")
            ):
                raise AppError(
                    f"Enter positive hours for {priority}.", status_code=422, code="validation_error"
                )
    if (
        key == "branding"
        and body.value.get("primary_color")
        and not HEX_COLOUR.fullmatch(str(body.value["primary_color"]))
    ):
        raise AppError(
            "Colours are hex values such as #0176d3.",
            status_code=422,
            code="validation_error",
            fields={"primary_color": "Use a hex colour such as #0176d3."},
        )
    if key == "company":
        abn = str(body.value.get("abn") or "")
        if digits(abn) and not is_valid_abn(abn):
            raise AppError(
                "That ABN isn't valid.",
                status_code=422,
                code="validation_error",
                fields={"abn": "Not a valid ABN."},
            )
        email = str(body.value.get("email") or "").strip()
        if email and not EMAIL.fullmatch(email):
            raise AppError(
                "Enter a valid e-mail address.",
                status_code=422,
                code="validation_error",
                fields={"email": "Not a valid e-mail address."},
            )
    before = get_setting(svc.db, key)
    merged = {**(before or {}), **body.value} if isinstance(before, dict) else body.value
    set_setting(svc.db, key, merged)
    audit.record(
        svc.db,
        action=AuditAction.UPDATE,
        entity_type="org_setting",
        entity_id=key,
        summary=f"Updated {key} settings",
        actor_id=svc.user_id,
        changes=audit.diff(before if isinstance(before, dict) else {}, merged),
        meta=svc.request_meta,
    )
    svc.db.commit()
    return merged

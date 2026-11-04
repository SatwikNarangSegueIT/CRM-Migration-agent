"""/onboarding: the first-run guide on the home page for a new workspace's administrators."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select

from app.auth.deps import DbSession, StaffAuth
from app.models import ImportJob, User
from app.services.settings import get_setting, set_setting

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _steps(db: DbSession) -> list[dict[str, Any]]:
    company = get_setting(db, "company") or {}
    marketing = get_setting(db, "marketing") or {}
    users = db.scalar(select(func.count()).select_from(User)) or 0
    imports = db.scalar(select(func.count()).select_from(ImportJob)) or 0
    return [
        {
            "key": "invite",
            "label": "Invite your colleagues",
            "description": "Give each person their own sign-in and profile.",
            "href": "/admin/users/new",
            "done": users > 1,
        },
        {
            "key": "import",
            "label": "Import your clients",
            "description": "Bring in clients and contacts from a CSV file.",
            "href": "/import",
            "done": imports > 0,
        },
        {
            "key": "company",
            "label": "Add your firm's details",
            "description": "Address, phone and ABN appear on letters, invoices and e-mails.",
            "href": "/setup/settings/company",
            "done": bool(company.get("address") and company.get("phone")),
        },
        {
            "key": "email",
            "label": "Set up e-mail sending",
            "description": "Choose the name and address your client e-mails come from.",
            "href": "/setup/settings/marketing",
            "done": bool(marketing.get("from_email")),
        },
    ]


@router.get("")
def onboarding(db: DbSession, auth: StaffAuth) -> dict[str, Any]:
    if not auth.policy.is_system_admin:
        return {"visible": False, "steps": []}
    state = get_setting(db, "onboarding") or {}
    steps = _steps(db)
    visible = not state.get("dismissed") and not all(s["done"] for s in steps)
    return {"visible": visible, "steps": steps}


@router.post("/dismiss")
def dismiss(db: DbSession, auth: StaffAuth) -> dict[str, Any]:
    if auth.policy.is_system_admin:
        set_setting(db, "onboarding", {"dismissed": True})
        db.commit()
    return {"visible": False, "steps": []}

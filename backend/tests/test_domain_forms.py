"""Forms (page layouts) shaped for each profession, and the records they create."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains import FORMS_VERSION, apply_domain, upgrade_domain_workspace
from app.models import FieldDefinition, ObjectDefinition
from app.services.settings import get_setting

API = "/api/v1"


def _obj(db: Session, api: str) -> ObjectDefinition:
    obj = db.scalar(select(ObjectDefinition).where(ObjectDefinition.api_name == api))
    assert obj is not None
    return obj


def _section(db: Session, api: str, label: str) -> list[str]:
    return next(s["fields"] for s in _obj(db, api).page_layout if s["label"] == label)


def _layout(db: Session, api: str) -> set[str]:
    return {f for s in _obj(db, api).page_layout for f in s["fields"]}


def _field(db: Session, api: str, name: str) -> FieldDefinition:
    obj = _obj(db, api)
    f = db.scalar(
        select(FieldDefinition).where(FieldDefinition.object_id == obj.id, FieldDefinition.api_name == name)
    )
    assert f is not None
    return f


@pytest.mark.parametrize(
    ("domain", "obj", "section", "fields"),
    [
        ("legal", "contact", "Identity", ["date_of_birth", "id_verified", "id_verified_date"]),
        (
            "migration",
            "contact",
            "Immigration and Privacy",
            ["citizenship", "country_of_birth", "passport_number"],
        ),
        (
            "migration",
            "account",
            "Sponsorship",
            ["is_sponsor", "sponsorship_approval_date", "sponsorship_expiry"],
        ),
        (
            "accounting",
            "account",
            "Tax and Entity",
            ["entity_type", "tfn", "gst_registered", "bas_frequency"],
        ),
        ("lending", "contact", "Borrower Details", ["date_of_birth", "residency_status", "first_home_buyer"]),
    ],
)
def test_profession_fields_are_on_the_forms_in_order(
    db: Session, domain: str, obj: str, section: str, fields: list[str]
) -> None:
    apply_domain(db, domain, None)
    db.flush()
    placed = _section(db, obj, section)
    assert placed[: len(fields)] == fields
    db.rollback()


def test_sales_fields_are_taken_off_and_lifecycle_fields_hidden_on_create(db: Session) -> None:
    apply_domain(db, "migration", None)
    db.flush()
    assert not {"department", "reports_to"} & _layout(db, "contact")
    assert not {"rating", "campaign", "annual_revenue"} & _layout(db, "lead")
    assert "opportunity" not in _layout(db, "invoice")
    assert "matter" in _section(db, "invoice", "Invoice Information")
    assert _field(db, "lead", "company").required is False
    for name in ("stage", "immi_trn", "outcome", "visa_expiry"):
        assert _field(db, "matter", name).options.get("hide_on_create") is True
    assert _field(db, "matter", "client").options.get("hide_on_create") is None
    assert _obj(db, "contact").page_layout[0]["label"] == "Client Information"
    assert _field(db, "matter", "professional_fee").help_text
    assert _obj(db, "checklist_item").name_label == "Document"
    db.rollback()


def test_the_upgrade_is_recorded_and_repeatable(db: Session) -> None:
    apply_domain(db, "legal", None)
    db.flush()
    assert get_setting(db, "workspace")["forms_version"] == FORMS_VERSION
    assert upgrade_domain_workspace(db) == 0  # already current
    assert upgrade_domain_workspace(db, force=True) == 0  # nothing left to change
    db.rollback()


def _new(c: TestClient, obj: str, fields: dict[str, Any], name: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"fields": fields}
    if name:
        body["name"] = name
    r = c.post(f"{API}/objects/{obj}/records", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_records_named_by_the_system(admin_client: TestClient, db: Session) -> None:
    c = admin_client
    for key in ("legal_practice", "migration_agency"):
        assert c.post(f"{API}/setup/packs/{key}/install").status_code in (200, 201)
    client = _new(c, "contact", {"last_name": "Citizen", "first_name": "Jane"})
    legal = _new(c, "legal_matter", {"title": "Citizen v State", "client": client["id"]})
    hearing = _new(
        c,
        "court_date",
        {"legal_matter": legal["id"], "type": "Hearing", "date_time": "2026-03-12T10:00:00+11:00"},
    )
    assert hearing["name"] == "Hearing 2026-03-12"
    matter = _new(c, "matter", {"client": client["id"]})
    applicant = _new(
        c, "matter_applicant", {"matter": matter["id"], "contact": client["id"], "role": "Dependent"}
    )
    assert applicant["name"] == "Jane Citizen (Dependent)"


def test_an_individual_enquiry_converts_without_an_organisation(
    admin_client: TestClient, db: Session
) -> None:
    from app.domains import apply_forms
    from app.engine.meta import bump_revision
    from app.services.settings import set_setting

    set_setting(db, "workspace", {"domain": "legal", "primary_app": "legal_practice"})
    apply_forms(db, "legal")
    bump_revision(db)
    db.commit()
    c = admin_client
    lead = _new(c, "lead", {"last_name": "Nguyen", "first_name": "Linh"})
    r = c.post(f"{API}/objects/lead/records/{lead['id']}/actions/convert", json={})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["account_id"] is None and out["contact_id"]
    contact = c.get(f"{API}/objects/contact/records/{out['contact_id']}").json()
    assert not contact["fields"].get("account")

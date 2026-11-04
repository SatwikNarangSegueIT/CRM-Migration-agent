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


def test_principals_can_edit_their_teams_records_and_headers_have_highlights(db: Session) -> None:
    from app.models import Profile, ProfileObjectPermission

    apply_domain(db, "legal", None)
    db.flush()
    principal = db.scalar(select(Profile).where(Profile.key == "lp_principal"))
    assert principal is not None
    perm = db.scalar(
        select(ProfileObjectPermission).where(
            ProfileObjectPermission.profile_id == principal.id,
            ProfileObjectPermission.object_api_name == "legal_matter",
        )
    )
    assert perm is not None and perm.view_all and perm.modify_all
    # A workspace built before highlights shipped gets them on upgrade.
    check = _obj(db, "conflict_check")
    check.compact_layout = []
    db.flush()
    assert upgrade_domain_workspace(db, force=True) >= 1
    assert _obj(db, "conflict_check").compact_layout[:2] == ["legal_matter", "result"]
    db.rollback()


def test_date_defaults_use_the_firms_calendar_day(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from app.core import clock

    # 23:30 UTC on 4 November is 10:30 on 5 November in Sydney.
    fixed = datetime(2026, 11, 4, 23, 30, tzinfo=UTC)

    class _Clock(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def, override]
            return fixed.astimezone(tz) if tz else fixed

    monkeypatch.setattr(clock, "datetime", _Clock)
    assert clock.local_today().isoformat() == "2026-11-05"
    assert clock.local_now().tzinfo == ZoneInfo("Australia/Sydney")


def test_in_process_migrations_leave_app_logging_alone() -> None:
    from app.db.migrate import _config

    assert _config("alembic").attributes.get("configure_logger") is False


def test_profession_workspaces_use_profession_wording(admin_client: TestClient, db: Session) -> None:
    """No sales vocabulary left over: sources, statuses, organisation types, requests, reports."""
    from app.domain_content import apply_content
    from app.domains import swap_words

    apply_domain(db, "lending", None)
    db.commit()
    c = admin_client
    lead = c.get(f"{API}/meta/objects/lead").json()
    labels = lambda f: [v["label"] for v in lead["fields"][f]["options"]["values"] if v.get("active", True)]  # noqa: E731
    assert "Purchased List" not in labels("lead_source") and "Client Referral" in labels("lead_source")
    assert "Phone Enquiry" in labels("lead_source")
    assert "Not Proceeding" in labels("status") and "Nurturing" not in labels("status")
    assert {"loan_purpose", "loan_amount"} <= set(lead["fields"])
    form = [f for s in lead["page_layout"] for f in s["fields"]]
    assert "loan_purpose" in form and "website" not in form and "converted_opportunity" not in form
    org = c.get(f"{API}/meta/objects/account").json()
    assert "Supplier" in [v["label"] for v in org["fields"]["type"]["options"]["values"]]
    assert c.get(f"{API}/meta/objects/case").json()["label"] == "Client Request"
    # Reports and dashboards for apps the firm doesn't use (pipeline, cases, invoices for a broker) are hidden.
    reports = {r["name"] for r in c.get(f"{API}/reports").json()}
    assert not {"Win Rate", "Total Open Pipeline", "SLA Compliance", "Aged Receivables"} & reports
    dashboards = {d["name"] for d in c.get(f"{API}/dashboards").json()}
    assert not {"Sales Dashboard", "Service Dashboard", "Billing Dashboard"} & dashboards
    assert apply_content(db, "lending") == 0  # idempotent
    # A client's trust account is not an organisation.
    assert swap_words("Client Account Balances", [("Account", "Organisation")]) == "Client Account Balances"

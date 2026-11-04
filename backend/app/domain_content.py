"""Profession wording and content for the standard records a profession workspace keeps using.

A law firm, migration agency, accounting practice or broker still uses enquiries, clients, organisations
and client requests from the standard CRM. This module replaces the sales vocabulary they arrive with
("Purchased List", "Prospect / Customer / Vendor", "Nurturing", "Cases", "Customer Support") and adds the
one question each profession asks of a new enquiry (area of law, visa interest, service, loan purpose).

Values keep their stored keys and only change labels (reports and filters keep working); values that make
no sense for a profession are switched off, not deleted. Idempotent: run on set-up and on upgrade.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.installer import install_field
from app.models import FieldDefinition, ObjectDefinition, Queue

# ------------------------------------------------------------------ shared by every profession

# Where enquiries come from in a professional practice.
SOURCE_LABELS = {"Phone Inquiry": "Phone Enquiry", "Partner Referral": "Professional Referral"}
SOURCE_OFF = {"Purchased List"}
SOURCE_ADD = ["Client Referral", "Search Engine", "Walk-in"]

ENQUIRY_STATUS_LABELS = {"Nurturing": "Follow-up", "Unqualified": "Not Proceeding"}

ORGANISATION_TYPE_LABELS = {
    "Prospect": "Prospective Client",
    "Customer": "Client",
    "Partner": "Referral Partner",
    "Vendor": "Supplier",
}

# Client requests from the portal (the standard "case"): a practice doesn't run a support desk.
REQUEST_LABELS = ("Client Request", "Client Requests")
REQUEST_QUEUE = "Client Requests"

# ------------------------------------------------------------------ the profession's enquiry question

_PICK = "picklist"
ENQUIRY_FIELDS: dict[str, list[dict[str, Any]]] = {
    "legal": [
        {
            "api_name": "practice_area",
            "label": "Area of Law",
            "type": _PICK,
            "values": [
                "Family",
                "Property & Conveyancing",
                "Wills & Estates",
                "Commercial",
                "Litigation",
                "Employment",
                "Criminal",
                "Personal Injury",
                "Immigration",
                "Other",
            ],
        }
    ],
    "migration": [
        {
            "api_name": "visa_interest",
            "label": "Visa Interest",
            "type": _PICK,
            "values": [
                "Skilled",
                "Employer Sponsored",
                "Partner / Family",
                "Student",
                "Graduate",
                "Visitor",
                "Business / Investor",
                "Citizenship",
                "Other",
            ],
        },
        {"api_name": "current_visa_expiry", "label": "Current Visa Expiry", "type": "date"},
    ],
    "accounting": [
        {
            "api_name": "service_required",
            "label": "Service Required",
            "type": _PICK,
            "values": [
                "Individual Tax Return",
                "Company / Trust Tax Return",
                "BAS / Bookkeeping",
                "SMSF",
                "Payroll",
                "Business Advisory",
                "Other",
            ],
        },
        {
            "api_name": "entity_type",
            "label": "Entity Type",
            "type": _PICK,
            "values": ["Individual", "Sole Trader", "Company", "Trust", "Partnership", "SMSF"],
        },
    ],
    "lending": [
        {
            "api_name": "loan_purpose",
            "label": "Loan Purpose",
            "type": _PICK,
            "values": [
                "Home Purchase",
                "First Home",
                "Refinance",
                "Investment Property",
                "Construction",
                "Commercial",
                "Car / Personal",
                "Other",
            ],
        },
        {"api_name": "loan_amount", "label": "Approximate Loan Amount", "type": "currency"},
    ],
}


def _values(options: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(v) for v in options.get("values", [])]


def _relabel(
    f: FieldDefinition,
    labels: dict[str, str],
    off: set[str] = frozenset(),  # type: ignore[assignment]
    add: list[str] | None = None,
) -> int:
    options = dict(f.options or {})
    values = _values(options)
    before = [dict(v) for v in values]
    for v in values:
        if v.get("value") in labels and v.get("label") in (v.get("value"), None):
            v["label"] = labels[v["value"]]
        if v.get("value") in off:
            v["active"] = False
    known = {v.get("value") for v in values}
    for value in add or []:
        if value not in known:
            values.append({"value": value, "label": value, "active": True})
    if values == before:
        return 0
    f.options = {**options, "values": values}
    return 1


def _field(db: Session, obj: str, api: str) -> FieldDefinition | None:
    return db.scalar(
        select(FieldDefinition)
        .join(ObjectDefinition, ObjectDefinition.id == FieldDefinition.object_id)
        .where(ObjectDefinition.api_name == obj, FieldDefinition.api_name == api)
    )


def _add_enquiry_fields(db: Session, domain: str) -> int:
    lead = db.scalar(select(ObjectDefinition).where(ObjectDefinition.api_name == "lead"))
    if lead is None:
        return 0
    changed = 0
    wanted = ENQUIRY_FIELDS.get(domain, [])
    conn = db.connection()
    for i, spec in enumerate(wanted):
        if _field(db, "lead", spec["api_name"]) is not None:
            continue
        field: dict[str, Any] = {
            "api_name": spec["api_name"],
            "label": spec["label"],
            "type": spec["type"],
            "filterable": True,
            "indexed": spec["type"] == _PICK,
        }
        if spec["type"] == _PICK:
            field["options"] = {"values": [{"value": v, "label": v, "active": True} for v in spec["values"]]}
        install_field(conn, "lead", field, order=9000 + i, standard=False)
        changed += 1
    # On the form, right after where the enquiry came from.
    names = [s["api_name"] for s in wanted]
    layout = [dict(sec, fields=list(sec.get("fields", []))) for sec in lead.page_layout or []]
    placed = {f for sec in layout for f in sec["fields"]}
    missing = [n for n in names if n not in placed]
    if missing and layout:
        target = next((s for s in layout if "lead_source" in s["fields"]), layout[0])
        at = (
            target["fields"].index("lead_source") + 1
            if "lead_source" in target["fields"]
            else len(target["fields"])
        )
        target["fields"][at:at] = missing
        lead.page_layout = layout
        changed += 1
    return changed


def apply_content(db: Session, domain: str) -> int:
    """Profession wording and enquiry fields (idempotent). Returns how many things changed."""
    changed = 0
    for obj in ("lead", "contact"):
        f = _field(db, obj, "lead_source")
        if f is not None:
            changed += _relabel(f, SOURCE_LABELS, SOURCE_OFF, SOURCE_ADD)
    status = _field(db, "lead", "status")
    if status is not None:
        changed += _relabel(status, ENQUIRY_STATUS_LABELS)
    org_type = _field(db, "account", "type")
    if org_type is not None:
        changed += _relabel(org_type, ORGANISATION_TYPE_LABELS)

    case = db.scalar(select(ObjectDefinition).where(ObjectDefinition.api_name == "case"))
    if case is not None and (case.label, case.plural_label) == ("Case", "Cases"):
        case.label, case.plural_label = REQUEST_LABELS
        changed += 1
    queue = db.scalar(select(Queue).where(Queue.name == "Customer Support"))
    if queue is not None and db.scalar(select(Queue).where(Queue.name == REQUEST_QUEUE)) is None:
        queue.name = REQUEST_QUEUE
        changed += 1

    db.flush()
    changed += _add_enquiry_fields(db, domain)
    return changed

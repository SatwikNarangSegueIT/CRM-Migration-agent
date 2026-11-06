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

# The role tree keeps its shape (who sees whose records); each profession names it for itself. A role an
# administrator renamed is left alone.
ROLE_NAMES: dict[str, dict[str, str]] = {
    "legal": {
        "ceo": "Managing Principal",
        "sales_director": "Principal",
        "sales_manager": "Senior Associate",
        "sales_representative": "Solicitor",
        "service_manager": "Practice Manager",
        "service_agent": "Paralegal",
        "marketing_manager": "Business Development Manager",
        "marketing_user": "Business Development Coordinator",
        "finance_manager": "Finance Manager",
        "finance_officer": "Trust Accountant",
    },
    "migration": {
        "ceo": "Principal",
        "sales_director": "Practice Manager",
        "sales_manager": "Senior Migration Agent",
        "sales_representative": "Registered Migration Agent",
        "service_manager": "Case Manager",
        "service_agent": "Case Officer",
        "marketing_manager": "Client Services Manager",
        "marketing_user": "Intake Consultant",
        "finance_manager": "Accounts Manager",
        "finance_officer": "Accounts Officer",
    },
    "accounting": {
        "ceo": "Managing Partner",
        "sales_director": "Partner",
        "sales_manager": "Client Manager",
        "sales_representative": "Accountant",
        "service_manager": "Bookkeeping Manager",
        "service_agent": "Bookkeeper",
        "marketing_manager": "Client Services Manager",
        "marketing_user": "Client Services Coordinator",
        "finance_manager": "Practice Manager",
        "finance_officer": "Practice Administrator",
    },
    "lending": {
        "ceo": "Principal Broker",
        "sales_director": "Broking Manager",
        "sales_manager": "Senior Broker",
        "sales_representative": "Broker",
        "service_manager": "Processing Manager",
        "service_agent": "Loan Processor",
        "marketing_manager": "Marketing Manager",
        "marketing_user": "Marketing Coordinator",
        "finance_manager": "Finance Manager",
        "finance_officer": "Commissions Administrator",
    },
}


def _name_roles(db: Session, domain: str) -> int:
    from app.models import Role
    from app.security.seed_v1 import ROLES

    shipped = {key: name for key, name, _parent in ROLES}
    wanted = ROLE_NAMES.get(domain, {})
    taken = {r.name for r in db.scalars(select(Role))}
    changed = 0
    for role in db.scalars(select(Role).where(Role.key.in_(list(wanted)))):
        new = wanted[role.key or ""]
        if role.name == shipped.get(role.key or "") and new not in taken:
            taken.discard(role.name)
            role.name = new
            taken.add(new)
            changed += 1
    return changed


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
            # The loan application's purposes, so the enquiry carries straight over.
            "values": [
                "Purchase - Owner Occupied",
                "Purchase - Investment",
                "Refinance",
                "Construction",
                "Equity Release",
                "First Home Buyer",
                "Commercial",
                "Car / Asset Finance",
                "Personal",
            ],
        },
        {"api_name": "loan_amount", "label": "Approximate Loan Amount", "type": "currency"},
    ],
}


# The professional registration each profession records on its people (users.mara_number holds it):
# (label, pattern, message). Shown on staff records and captured on client agreements.
REGISTRATION_NUMBERS: dict[str, tuple[str, str, str]] = {
    "migration": ("MARN", r"^\d{7}$", "A MARN (Migration Agents Registration Number) has 7 digits."),
    "accounting": ("Tax agent number", r"^\d{8}$", "A registered tax agent number has 8 digits."),
    "lending": (
        "Credit representative number",
        r"^\d{6,7}$",
        "An ASIC credit representative number has 6 or 7 digits.",
    ),
    "legal": (
        "Practising certificate number",
        r"^[A-Za-z0-9-]{3,20}$",
        "Use the number on your practising certificate (letters, digits and dashes).",
    ),
}


def registration_number_error(domain: str | None, value: str | None) -> str | None:
    """Why a professional registration number isn't valid for this profession (None when it is)."""
    import re

    if not value:
        return None
    label, pattern, message = REGISTRATION_NUMBERS.get(
        domain or "", ("Registration number", r"^[A-Za-z0-9-]{3,20}$", "Use letters, digits and dashes.")
    )
    _ = label
    return None if re.fullmatch(pattern, value) else message


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
    if case is not None and case.name_label == "Case Number":
        case.name_label = "Request Number"
        changed += 1
    if case is not None:
        from app.models import ListView

        # Shipped list views ("All Cases", "My Open Cases") and related lists on clients and organisations.
        for view in db.scalars(select(ListView).where(ListView.object_api_name == "case")):
            if "Cases" in view.name:
                view.name = view.name.replace("Cases", REQUEST_LABELS[1])
                changed += 1
        for holder in db.scalars(
            select(ObjectDefinition).where(ObjectDefinition.api_name.in_(("contact", "account")))
        ):
            lists = [dict(rl) for rl in holder.related_lists or []]
            renamed = False
            for rl in lists:
                if rl.get("object") == "case" and rl.get("label") == "Cases":
                    rl["label"] = REQUEST_LABELS[1]
                    renamed = True
            if renamed:
                holder.related_lists = lists
                changed += 1
    queue = db.scalar(select(Queue).where(Queue.name == "Customer Support"))
    if queue is not None and db.scalar(select(Queue).where(Queue.name == REQUEST_QUEUE)) is None:
        queue.name = REQUEST_QUEUE
        changed += 1

    changed += _name_roles(db, domain)
    db.flush()
    changed += _add_enquiry_fields(db, domain)
    return changed

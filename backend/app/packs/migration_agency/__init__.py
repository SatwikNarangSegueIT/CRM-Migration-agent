"""Migration Agency (Australia) industry pack: definition plus the rules that need code (plan v3, section 11).

Rules: checklist generated from the visa type; stage gate (past Service Agreement only with a signed
agreement, admin override audited); lodgement/decision stages need the Lodge Applications permission;
client-account balance can never go negative (row-locked); transfers to office only against issued
invoices; visa, passport and sponsorship expiry reminders; case officers / RMAs get access to their matters.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, false, func, select
from sqlalchemy.orm import Session

from app.apps.billing import refresh_invoice_payments
from app.apps.sales import BusinessRuleError, rule
from app.apps.service import notify
from app.engine.hooks import Change, Event, action, on, ref
from app.engine.records import RecordService
from app.engine.types import decimal_to_json, format_datetime, money, to_decimal
from app.models import Notification, Record, RecordShare
from app.packs import Pack, permission_key, register
from app.packs.migration_agency import definition as d
from app.services import audit
from app.services.audit import AuditAction
from app.services.settings import get_setting

K = d.KEY


def _can_lodge(svc: RecordService) -> bool:
    return svc.system or svc.policy.has_custom(permission_key(K, d.LODGE))


# ------------------------------------------------------------------ matters


@on("matter", Event.BEFORE_CREATE, pack_key=K)
def matter_defaults(change: Change) -> None:
    data = change.data
    vt = change.svc.db.get(Record, ref(data.get("visa_type"))) if data.get("visa_type") else None
    if vt is not None:
        data.setdefault("professional_fee", vt.data.get("default_professional_fee"))
        data.setdefault("government_fee", vt.data.get("default_government_fee"))
    if data.get("stage") not in (None, "Consultation") and not change.svc.system:
        raise rule("New matters start at Consultation.", "stage")


def _signed_agreement(svc: RecordService, matter_id: uuid.UUID) -> bool:
    return (
        svc.db.scalar(
            select(Record.id)
            .where(
                Record.object_api_name == "service_agreement",
                Record.is_deleted == false(),
                Record.data["matter"].astext == str(matter_id),
                Record.data["status"].astext == "Signed",
            )
            .limit(1)
        )
        is not None
    )


@on("matter", Event.BEFORE_UPDATE, pack_key=K)
def matter_rules(change: Change) -> None:
    svc, data, old = change.svc, change.data, change.old
    record = change.record
    assert record is not None
    new_stage, old_stage = data.get("stage"), old.get("stage")
    if change.is_changed("stage"):
        new_i = d.STAGE_ORDER.index(new_stage) if new_stage in d.STAGE_ORDER else 0
        gate = d.STAGE_ORDER.index("Service Agreement")
        if new_i > gate and not data.get("agreement_override") and not _signed_agreement(svc, record.id):
            raise rule(
                "A signed service agreement is needed before moving past Service Agreement "
                "(Code of Conduct).",
                "stage",
            )
        if new_stage in d.LODGE_STAGES and old_stage not in d.LODGE_STAGES and not _can_lodge(svc):
            raise rule(
                "Moving a matter to Lodged or beyond needs the Lodge Applications permission.", "stage"
            )
        if new_stage == "Lodged" and not data.get("lodgement_date"):
            data["lodgement_date"] = date.today().isoformat()
    if (change.is_changed("outcome") or change.is_changed("decision_date")) and not _can_lodge(svc):
        raise rule("Recording a decision needs the Lodge Applications permission.", "outcome")
    if data.get("outcome") and not data.get("decision_date"):
        data["decision_date"] = date.today().isoformat()
    if data.get("outcome") and data.get("stage") != "Decision":
        data["stage"] = "Decision"
    if data.get("lodgement_date") and data.get("decision_date"):
        days = (date.fromisoformat(data["decision_date"]) - date.fromisoformat(data["lodgement_date"])).days
        data["processing_days"] = max(days, 0)
    if change.is_changed("visa_type") and data.get("visa_type"):
        _generate_checklist(svc, record, only_if_empty=True)


@on("matter", Event.AFTER_CREATE, pack_key=K)
def matter_created(change: Change) -> None:
    assert change.record is not None
    _generate_checklist(change.svc, change.record, only_if_empty=True)
    _sync_team_shares(change.svc, change.record)


@on("matter", Event.AFTER_UPDATE, pack_key=K)
def matter_updated(change: Change) -> None:
    if change.is_changed("case_officer") or change.is_changed("responsible_rma"):
        assert change.record is not None
        _sync_team_shares(change.svc, change.record)


@on("matter", Event.BEFORE_DELETE, pack_key=K)
def matter_retention(change: Change) -> None:
    assert change.record is not None
    has_ledger = change.svc.db.scalar(
        select(Record.id)
        .where(
            Record.object_api_name == "client_account_transaction",
            Record.data["matter"].astext == str(change.record.id),
        )
        .limit(1)
    )
    if has_ledger:
        raise rule("Matters with client-account transactions must be kept (7-year retention).")


def _sync_team_shares(svc: RecordService, matter: Record) -> None:
    """Case officers and the responsible RMA can read and edit their matters ("Matter RE via sharing")."""
    svc.db.execute(
        delete(RecordShare).where(RecordShare.record_id == matter.id, RecordShare.created_by_id.is_(None))
    )
    for field in ("case_officer", "responsible_rma"):
        uid = matter.data.get(field)
        if uid:
            svc.db.add(
                RecordShare(
                    record_id=matter.id,
                    principal_type="user",
                    principal_id=uuid.UUID(str(uid)),
                    access="read_write",
                    created_by_id=None,
                )
            )
    svc.db.flush()


def _generate_checklist(svc: RecordService, matter: Record, *, only_if_empty: bool) -> int:
    vt = svc.db.get(Record, ref(matter.data.get("visa_type"))) if matter.data.get("visa_type") else None
    if vt is None:
        return 0
    if only_if_empty and svc.db.scalar(
        select(Record.id)
        .where(
            Record.object_api_name == "checklist_item",
            Record.is_deleted == false(),
            Record.data["matter"].astext == str(matter.id),
        )
        .limit(1)
    ):
        return 0
    lines = [
        ln.strip(" -*\t")
        for ln in str(vt.data.get("checklist_template") or "").splitlines()
        if ln.strip(" -*\t")
    ]
    sys = svc.elevated()
    for i, line in enumerate(lines, start=1):
        sys.create(
            "checklist_item",
            {
                "name": line[:255],
                "matter": str(matter.id),
                "sort_order": i,
                "status": "Requested",
                "is_public": True,
            },
        )
    return len(lines)


@action(
    "matter",
    "lodge",
    "Lodge Application",
    pack_key=K,
    visible=lambda r: r.data.get("stage") == "Ready to Lodge",
    guard=lambda svc, r: None if _can_lodge(svc) else "Lodging needs the Lodge Applications permission.",
)
def lodge(svc: RecordService, matter: Record, payload: dict[str, Any]) -> dict[str, Any]:
    trn = str(payload.get("immi_trn") or matter.data.get("immi_trn") or "").strip()
    if not trn:
        raise BusinessRuleError("Enter the ImmiAccount TRN.", fields={"immi_trn": "Required"})
    lodged_on = str(payload.get("lodgement_date") or date.today().isoformat())
    svc.update("matter", matter.id, {"stage": "Lodged", "immi_trn": trn}, record=matter)
    svc.elevated().update("matter", matter.id, {"lodgement_date": lodged_on}, record=matter)
    return svc.serialize(matter)


@action(
    "matter",
    "override_agreement_gate",
    "Override Agreement Gate",
    pack_key=K,
    visible=lambda r: not r.data.get("agreement_override"),
    guard=lambda svc, r: (
        None
        if svc.policy.has_custom(permission_key(K, d.OVERRIDE))
        else "Only administrators can override the agreement gate."
    ),
)
def override_gate(svc: RecordService, matter: Record, payload: dict[str, Any]) -> dict[str, Any]:
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise BusinessRuleError("Enter the reason for the override.", fields={"reason": "Required"})
    svc.elevated().update("matter", matter.id, {"agreement_override": True}, record=matter)
    audit.record(
        svc.db,
        action=AuditAction.UPDATE,
        entity_type="record:matter",
        entity_id=matter.id,
        summary=f"Service-agreement gate overridden on {matter.name}: {reason}"[:500],
        actor_id=svc.user_id,
        changes={"agreement_override": {"from": False, "to": True}, "reason": {"from": None, "to": reason}},
        meta=svc.request_meta,
    )
    return svc.serialize(matter)


@action("matter", "regenerate_checklist", "Generate Checklist", pack_key=K)
def regenerate_checklist(svc: RecordService, matter: Record, payload: dict[str, Any]) -> dict[str, Any]:
    return {"created": _generate_checklist(svc, matter, only_if_empty=False)}


# ------------------------------------------------------------------ applicants


@on("matter_applicant", Event.BEFORE_CREATE, Event.BEFORE_UPDATE, pack_key=K)
def applicant_name(change: Change) -> None:
    """An applicant is named after the person: "Jane Citizen (Primary)"."""
    person = (
        change.svc.db.get(Record, ref(change.data.get("contact"))) if change.data.get("contact") else None
    )
    if person is not None:
        role = change.data.get("role") or "Applicant"
        change.system["name"] = f"{person.name} ({role})"[:255]


# ------------------------------------------------------------------ service agreements


@on("service_agreement", Event.BEFORE_CREATE, pack_key=K)
def agreement_defaults(change: Change) -> None:
    matter = change.svc.db.get(Record, ref(change.data.get("matter")))
    if matter is not None:
        change.data.setdefault("professional_fee", matter.data.get("professional_fee"))
        change.data.setdefault("government_fee", matter.data.get("government_fee"))
    change.data["status"] = "Draft"


@on("service_agreement", Event.BEFORE_UPDATE, pack_key=K)
def agreement_locked(change: Change) -> None:
    if change.old.get("status") in ("Signed", "Cancelled") and not change.svc.system:
        raise rule("Signed or cancelled agreements can't be changed.")


@action(
    "service_agreement",
    "send",
    "Send to Client",
    pack_key=K,
    visible=lambda r: r.data.get("status") == "Draft",
)
def send_agreement(svc: RecordService, agreement: Record, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_setting(svc.db, "migration_agency") or {}
    if settings.get("consumer_guide_required", True) and not agreement.data.get("consumer_guide_provided"):
        raise BusinessRuleError(
            "Confirm the Consumer Guide has been provided (Code of Conduct).",
            fields={"consumer_guide_provided": "Required"},
        )
    svc.elevated().update(
        "service_agreement",
        agreement.id,
        {"status": "Sent", "sent_at": format_datetime(datetime.now(UTC))},
        record=agreement,
    )
    matter = svc.db.get(Record, ref(agreement.data.get("matter")))
    if matter is not None and matter.data.get("stage") == "Consultation":
        svc.elevated().update("matter", matter.id, {"stage": "Service Agreement"}, record=matter)
    return svc.serialize(agreement)


@action(
    "service_agreement",
    "sign",
    "Sign Agreement",
    pack_key=K,
    requires_edit=False,
    portal=True,
    visible=lambda r: r.data.get("status") == "Sent",
)
def sign_agreement(svc: RecordService, agreement: Record, payload: dict[str, Any]) -> dict[str, Any]:
    """Client e-signature from the portal: typed full name, time and IP are recorded."""
    if agreement.data.get("status") != "Sent":
        raise rule("Only agreements sent to you can be signed.")
    name = str(payload.get("full_name") or "").strip()
    if len(name) < 3 or not payload.get("accept"):
        raise BusinessRuleError(
            "Type your full name and accept the agreement.", fields={"full_name": "Required"}
        )
    svc.elevated().update(
        "service_agreement",
        agreement.id,
        {
            "status": "Signed",
            "signed_name": name[:120],
            "signed_at": format_datetime(datetime.now(UTC)),
            "signed_ip": svc.request_meta.ip_address,
        },
        record=agreement,
    )
    audit.record(
        svc.db,
        action=AuditAction.UPDATE,
        entity_type="record:service_agreement",
        entity_id=agreement.id,
        summary=f"Service agreement {agreement.name} signed by {name}"[:500],
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    return svc.serialize(agreement)


# ------------------------------------------------------------------ client account (trust ledger)


def client_balance(db: Session, client_id: uuid.UUID) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(Record.data["signed_amount"].astext.cast(_numeric())), 0)).where(
            Record.object_api_name == "client_account_transaction",
            Record.is_deleted == false(),
            Record.data["client"].astext == str(client_id),
        )
    )
    return money(Decimal(str(total or 0)))


def _numeric() -> Any:
    from sqlalchemy import Numeric

    return Numeric


@on("client_account_transaction", Event.BEFORE_CREATE, pack_key=K)
def ledger_rules(change: Change) -> None:
    svc, data = change.svc, change.data
    client_id = ref(data.get("client"))
    if client_id is None:
        raise rule("Choose the client.", "client")
    # Row-lock the client so concurrent withdrawals can't overdraw the account.
    client = svc.db.scalar(select(Record).where(Record.id == client_id).with_for_update())
    if client is None:
        raise rule("Choose the client.", "client")
    amount = money(to_decimal(data.get("amount")) or 0)
    if amount <= 0:
        raise rule("Enter a positive amount.", "amount")
    kind = data.get("type")
    if data.get("matter"):
        matter = svc.db.get(Record, ref(data["matter"]))
        if matter is None or matter.data.get("client") != str(client_id):
            raise rule("The matter belongs to a different client.", "matter")
    if kind == "Transfer to Office":
        invoice = svc.db.get(Record, ref(data.get("invoice"))) if data.get("invoice") else None
        if invoice is None or invoice.data.get("status") not in ("Issued", "Partially Paid"):
            raise rule("Transfers to the office account need an issued, unpaid invoice.", "invoice")
        if amount > money(to_decimal(invoice.data.get("balance")) or 0):
            raise rule("The transfer is more than the invoice's balance due.", "amount")
    elif data.get("invoice"):
        raise rule("Only transfers to office are linked to invoices.", "invoice")
    signed = amount if kind == "Deposit" else -amount
    balance = client_balance(svc.db, client_id) + signed
    if balance < 0:
        raise rule(
            f"The client account balance can't go negative (available {client_balance(svc.db, client_id)}).",
            "amount",
        )
    data["signed_amount"] = decimal_to_json(signed)
    data["balance_after"] = decimal_to_json(balance)


@on("client_account_transaction", Event.AFTER_CREATE, pack_key=K)
def ledger_transfer_pays_invoice(change: Change) -> None:
    if change.data.get("type") != "Transfer to Office":
        return
    assert change.record is not None
    invoice = change.svc.db.get(Record, ref(change.data.get("invoice")))
    if invoice is None:
        return
    change.svc.elevated().create(
        "payment",
        {
            "invoice": str(invoice.id),
            "amount": change.data.get("amount"),
            "payment_date": change.data.get("transaction_date"),
            "method": "Other",
            "reference": f"Client account {change.record.name}",
        },
    )
    refresh_invoice_payments(change.svc, invoice)


@on("client_account_transaction", Event.BEFORE_UPDATE, Event.BEFORE_DELETE, pack_key=K)
def ledger_is_append_only(change: Change) -> None:
    if not change.svc.system:
        raise rule(
            "Client-account transactions can't be changed or deleted; record a correcting transaction."
        )


def statement(svc: RecordService, client_id: uuid.UUID) -> dict[str, Any]:
    """Client account statement with running balance (reconciliation)."""
    client = svc.get("contact", client_id)
    res = svc.query(
        "client_account_transaction",
        filters={
            "logic": "and",
            "conditions": [{"field": "client", "op": "equals", "value": str(client_id)}],
        },
        sort=[{"field": "created_at", "direction": "asc"}],
        limit=200,
    )
    running = Decimal(0)
    rows = []
    for r in res.records:
        running += to_decimal(r.data.get("signed_amount")) or Decimal(0)
        rows.append(
            {
                "id": str(r.id),
                "number": r.name,
                "date": r.data.get("transaction_date"),
                "type": r.data.get("type"),
                "amount": r.data.get("amount"),
                "signed_amount": r.data.get("signed_amount"),
                "reference": r.data.get("reference"),
                "running_balance": decimal_to_json(money(running)),
            }
        )
    return {
        "client": {"id": str(client.id), "name": client.name},
        "transactions": rows,
        "balance": decimal_to_json(client_balance(svc.db, client_id)),
    }


# ------------------------------------------------------------------ expiry reminders


def expiry_reminders(db: Session, today: date | None = None) -> int:
    today = today or date.today()
    days = (get_setting(db, "migration_agency") or {}).get("expiry_reminder_days", [90, 30])
    targets: list[tuple[str, str, str, Callable[[Record], str | None]]] = [
        (
            "matter",
            "visa_expiry",
            "Visa expires",
            lambda r: r.data.get("responsible_rma") or (str(r.owner_id) if r.owner_id else None),
        ),
        ("contact", "passport_expiry", "Passport expires", lambda r: str(r.owner_id) if r.owner_id else None),
        (
            "contact",
            "current_visa_expiry",
            "Current visa expires",
            lambda r: str(r.owner_id) if r.owner_id else None,
        ),
        (
            "account",
            "sponsorship_expiry",
            "Sponsorship expires",
            lambda r: str(r.owner_id) if r.owner_id else None,
        ),
    ]
    count = 0
    for obj, field, label, who in targets:
        for n in days:
            day = (today + timedelta(days=int(n))).isoformat()
            rows = db.scalars(
                select(Record).where(
                    Record.object_api_name == obj,
                    Record.is_deleted == false(),
                    Record.data[field].astext == day,
                )
            ).all()
            for r in rows:
                uid = who(r)
                if not uid:
                    continue
                title = f"{label} in {n} days: {r.name}"
                exists = db.scalar(
                    select(Notification.id)
                    .where(Notification.record_id == r.id, Notification.title == title)
                    .limit(1)
                )
                if exists:
                    continue
                notify(db, uuid.UUID(str(uid)), title, f"{label} on {day}.", f"/o/{obj}/{r.id}", r.id)
                db.flush()
                count += 1
    return count


PACK = register(
    Pack(
        key=K,
        name="Migration Agency (Australia)",
        version=d.VERSION,
        region="AU",
        description="Matters, visa types, document checklists, service agreements (Code of Conduct), "
        "client account (trust) "
        "ledger, lodgement controls, expiry reminders, practice profiles, reports and a client portal.",
        bundle=d.bundle,
        install=d.install,
        custom_permissions={d.LODGE: "Lodge Applications", d.OVERRIDE: "Override Agreement Gate"},
        daily_job=expiry_reminders,
    )
)

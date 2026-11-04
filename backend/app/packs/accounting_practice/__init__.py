"""Accounting Practice (Australia) industry pack: definition plus rules that need code (plan v4, s 6).

Rules: work starts only once the APES 305 engagement letter is signed; a different person reviews before
a return is ready to lodge; lodging needs the Lodge Returns permission and closes the matching deadlines;
default due dates per return type and financial year; BAS/IAS deadlines generated from the client's BAS
frequency; deadlines turn overdue automatically with reminders; time recording with WIP and
recoverability; clients answer document requests in the portal.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, false, select
from sqlalchemy.orm import Session

from app.apps.sales import BusinessRuleError, rule
from app.apps.service import notify
from app.core.clock import local_today
from app.engine.hooks import Change, Event, action, locked_when, on, ref
from app.engine.records import RecordService
from app.engine.types import decimal_to_json, format_datetime, money, to_decimal
from app.models import Record, RecordShare
from app.packs import Pack, permission_key, register
from app.packs.accounting_practice import definition as d
from app.packs.common import date_reminders, first_of, live
from app.services import audit
from app.services.audit import AuditAction
from app.services.settings import get_setting

K = d.KEY
TENTHS = Decimal("0.1")
DOCUMENT_TEMPLATES: dict[str, list[str]] = {
    "Individual Tax Return": [
        "Income statements from employers",
        "Bank interest and dividend statements",
        "Receipts for work-related deductions",
        "Private health insurance statement",
        "Rental property income and expenses",
    ],
    "Company Tax Return": ["Year-end bank statements", "Trial balance", "Loan and asset schedules"],
    "Trust Tax Return": ["Year-end bank statements", "Trustee distribution resolution", "Trial balance"],
    "Partnership Tax Return": ["Year-end bank statements", "Partnership agreement changes", "Trial balance"],
    "SMSF Annual Return": [
        "Fund bank statements",
        "Investment statements",
        "Contribution details",
        "Pension details",
    ],
    "SMSF Audit": ["Financial statements", "Member statements", "Investment strategy", "Trustee minutes"],
    "BAS": ["Sales and purchases for the period", "Bank statements for the period"],
    "IAS": ["PAYG withholding summary for the period"],
}


def _settings(db: Session) -> dict[str, Any]:
    return get_setting(db, K) or {}


def _can_lodge(svc: RecordService) -> bool:
    return svc.system or svc.policy.has_custom(permission_key(K, d.LODGE))


def _get(svc: RecordService, value: Any) -> Record | None:
    rid = ref(value)
    return svc.db.get(Record, rid) if rid else None


def _set(svc: RecordService, record: Record, values: dict[str, Any]) -> None:
    svc.elevated().update(record.object_api_name, record.id, values, record=record)


def financial_year(today: date, *, ended: bool) -> str:
    """Australian financial year label ("2025-26"); ended=True gives the last completed year."""
    start = today.year if today.month >= 7 else today.year - 1
    if ended:
        start -= 1
    return f"{start}-{str(start + 1)[-2:]}"


def default_due_date(db: Session, kind: str, fy: str) -> str | None:
    due = (_settings(db).get("return_due") or {}).get(kind)
    if not due or len(fy) < 4 or not fy[:4].isdigit():
        return None
    day, month = (int(p) for p in due.split("-"))
    year_end = int(fy[:4]) + 1  # FY 2025-26 ends 30 June 2026
    year = year_end if month >= 7 else year_end + 1
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


# ------------------------------------------------------------------ engagements


@on("engagement", Event.BEFORE_CREATE, pack_key=K)
def engagement_defaults(change: Change) -> None:
    data, svc = change.data, change.svc
    if data.get("stage") not in (None, "Not Started") and not svc.system:
        raise rule("New engagements start at Not Started.", "stage")
    kind = data.get("type") or ""
    if not data.get("financial_year"):
        data["financial_year"] = financial_year(
            local_today(), ended=kind.endswith("Return") or "Audit" in kind
        )
    if not data.get("due_date"):
        data["due_date"] = default_due_date(svc.db, kind, data["financial_year"])
    if not data.get("responsible_accountant") and svc.user_id and not svc.system:
        data["responsible_accountant"] = str(svc.user_id)
    data["letter_signed"] = False


@on("engagement", Event.BEFORE_UPDATE, pack_key=K)
def engagement_rules(change: Change) -> None:
    svc, data, old = change.svc, change.data, change.old
    if not change.is_changed("stage") or svc.system:
        return
    new_stage = data.get("stage")
    new_i = d.STAGE_ORDER.index(new_stage) if new_stage in d.STAGE_ORDER else 0
    old_i = d.STAGE_ORDER.index(old["stage"]) if old.get("stage") in d.STAGE_ORDER else 0
    if new_i <= old_i:
        return
    if (
        new_i >= d.STAGE_ORDER.index("In Progress")
        and _settings(svc.db).get("letter_required", True)
        and not data.get("letter_signed")
    ):
        raise rule("The client must sign the engagement letter (APES 305) before work starts.", "stage")
    if new_i >= d.STAGE_ORDER.index("Ready to Lodge") and old_i < d.STAGE_ORDER.index("Ready to Lodge"):
        reviewer = data.get("reviewer")
        if not reviewer:
            raise rule("Assign a reviewer before the work is ready to lodge.", "reviewer")
        if reviewer == data.get("responsible_accountant"):
            raise rule("The reviewer must be someone other than the preparer.", "reviewer")
        if str(svc.user_id) != str(reviewer) and not _can_lodge(svc):
            raise rule("Only the reviewer can sign off the review.", "stage")
    if new_stage in ("Lodged", "Complete") and data.get("type") in d.LODGED_TYPES:
        if old.get("stage") not in ("Lodged",) and not _can_lodge(svc):
            raise rule("Lodging needs the Lodge Returns permission (registered tax agent).", "stage")
        if new_stage == "Lodged" or not data.get("lodged_date"):
            data["lodged_date"] = data.get("lodged_date") or local_today().isoformat()


@on("engagement", Event.AFTER_CREATE, pack_key=K)
def engagement_created(change: Change) -> None:
    eng = change.record
    assert eng is not None
    _sync_team_shares(change.svc, eng)
    sys = change.svc.elevated()
    for i, doc in enumerate(DOCUMENT_TEMPLATES.get(eng.data.get("type") or "", []), start=1):
        sys.create(
            "document_request",
            {
                "name": doc,
                "engagement": str(eng.id),
                "sort_order": i,
                "is_public": True,
                "status": "Requested",
            },
        )
    kind = eng.data.get("type")
    if eng.data.get("due_date") and kind in d.LODGED_TYPES:
        lodgement = "Income Tax Return" if kind and kind.endswith("Tax Return") else kind
        if kind == "SMSF Annual Return":
            lodgement = "SMSF Annual Return"
        sys.create(
            "lodgement_deadline",
            {
                "client": eng.data.get("client"),
                "engagement": str(eng.id),
                "lodgement_type": lodgement,
                "period": eng.data.get("period") or eng.data.get("financial_year"),
                "due_date": eng.data["due_date"],
                "responsible": eng.data.get("responsible_accountant"),
            },
        )


@on("engagement", Event.AFTER_UPDATE, pack_key=K)
def engagement_updated(change: Change) -> None:
    eng = change.record
    assert eng is not None
    if change.is_changed("responsible_accountant") or change.is_changed("reviewer"):
        _sync_team_shares(change.svc, eng)
    if change.is_changed("fee"):
        _refresh_costs(change.svc, eng.id)
    if change.is_changed("stage") and change.data.get("stage") in ("Lodged", "Complete"):
        for dl in live(change.svc.db, "lodgement_deadline", engagement=str(eng.id)):
            if dl.data.get("status") != "Lodged":
                _set(change.svc, dl, {"status": "Lodged", "lodged_on": eng.data.get("lodged_date")})


def _sync_team_shares(svc: RecordService, eng: Record) -> None:
    svc.db.execute(
        delete(RecordShare).where(RecordShare.record_id == eng.id, RecordShare.created_by_id.is_(None))
    )
    for field in ("responsible_accountant", "reviewer"):
        uid = eng.data.get(field)
        if uid:
            svc.db.add(
                RecordShare(
                    record_id=eng.id,
                    principal_type="user",
                    principal_id=uuid.UUID(str(uid)),
                    access="read_write",
                    created_by_id=None,
                )
            )
    svc.db.flush()


@action(
    "engagement",
    "create_invoice",
    "Invoice Engagement",
    pack_key=K,
    visible=lambda r: (
        r.data.get("stage") in ("Lodged", "Complete", "Review", "Ready to Lodge", "In Progress")
    ),
)
def invoice_engagement(svc: RecordService, eng: Record, payload: dict[str, Any]) -> dict[str, Any]:
    """Fixed fee: one line for the agreed fee (time is absorbed). Time-based: one line per unbilled entry."""
    entries = [
        e
        for e in live(svc.db, "engagement_time_entry", engagement=str(eng.id), status="Unbilled")
        if e.data.get("billable", True)
    ]
    fixed = eng.data.get("fee_type", "Fixed Fee") == "Fixed Fee"
    if fixed and not to_decimal(eng.data.get("fee")):
        raise rule("Enter the agreed fee first.", "fee")
    if not fixed and not entries:
        raise rule("There is no unbilled time on this engagement.")
    if fixed and _already_invoiced(svc, eng):
        raise rule("This fixed-fee engagement has already been invoiced.")
    invoice = svc.create(
        "invoice",
        {
            "account": eng.data.get("client"),
            "contact": eng.data.get("contact"),
            "engagement": str(eng.id),
            "notes": f"{eng.data.get('type')} {eng.data.get('financial_year') or ''}".strip(),
        },
    )
    sys = svc.elevated()
    if fixed:
        sys.create(
            "invoice_line",
            {
                "invoice": str(invoice.id),
                "description": f"{eng.data.get('type')} {eng.data.get('financial_year') or ''}".strip()[:255],
                "quantity": 1,
                "unit_price": eng.data.get("fee"),
                "sort_order": 1,
            },
        )
    else:
        entries.sort(key=lambda e: (e.data.get("entry_date") or "", e.name))
        for i, e in enumerate(entries, start=1):
            sys.create(
                "invoice_line",
                {
                    "invoice": str(invoice.id),
                    "description": f"{e.data.get('entry_date')} {e.data.get('narrative') or ''}"[:255],
                    "quantity": e.data.get("hours"),
                    "unit_price": e.data.get("rate"),
                    "sort_order": i,
                },
            )
    for e in entries:
        sys.update("engagement_time_entry", e.id, {"status": "Billed", "invoice": str(invoice.id)}, record=e)
    _refresh_costs(svc, eng.id)
    return {"invoice_id": str(invoice.id), "entries": len(entries)}


def _already_invoiced(svc: RecordService, eng: Record) -> bool:
    return bool(
        svc.db.scalar(
            select(Record.id)
            .where(
                Record.object_api_name == "invoice",
                Record.is_deleted == false(),
                Record.data["engagement"].astext == str(eng.id),
                Record.data["status"].astext != "Void",
            )
            .limit(1)
        )
    )


# ------------------------------------------------------------------ engagement letters (APES 305)


@on("engagement_letter", Event.BEFORE_CREATE, pack_key=K)
def letter_defaults(change: Change) -> None:
    eng = _get(change.svc, change.data.get("engagement"))
    if eng is not None and change.data.get("fee_estimate") is None:
        change.data["fee_estimate"] = eng.data.get("fee")
    change.data["status"] = "Draft"


@on("engagement_letter", Event.BEFORE_UPDATE, pack_key=K)
def letter_locked(change: Change) -> None:
    if change.old.get("status") in ("Signed", "Cancelled") and not change.svc.system:
        raise rule("Signed or cancelled engagement letters can't be changed.")


@action(
    "engagement_letter",
    "send",
    "Send to Client",
    pack_key=K,
    visible=lambda r: r.data.get("status") == "Draft",
)
def send_letter(svc: RecordService, letter: Record, payload: dict[str, Any]) -> dict[str, Any]:
    _set(svc, letter, {"status": "Sent", "sent_at": format_datetime(datetime.now(UTC))})
    audit.record(
        svc.db,
        action=AuditAction.UPDATE,
        entity_type="record:engagement_letter",
        entity_id=letter.id,
        summary=f"Engagement letter {letter.name} sent to the client",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    return svc.serialize(letter)


@action(
    "engagement_letter",
    "sign",
    "Sign Engagement Letter",
    pack_key=K,
    requires_edit=False,
    client_only=True,
    visible=lambda r: r.data.get("status") == "Sent",
)
def sign_letter(svc: RecordService, letter: Record, payload: dict[str, Any]) -> dict[str, Any]:
    """Client e-signature from the portal: typed full name, time and IP are recorded."""
    if letter.data.get("status") != "Sent":
        raise rule("Only letters sent to you can be signed.")
    name = str(payload.get("full_name") or "").strip()
    if len(name) < 3 or not payload.get("accept"):
        raise BusinessRuleError("Type your full name and accept the terms.", fields={"full_name": "Required"})
    _set(
        svc,
        letter,
        {
            "status": "Signed",
            "signed_name": name[:120],
            "signed_at": format_datetime(datetime.now(UTC)),
            "signed_ip": svc.request_meta.ip_address,
        },
    )
    eng = _get(svc, letter.data.get("engagement"))
    if eng is not None:
        values: dict[str, Any] = {"letter_signed": True}
        if eng.data.get("stage") == "Not Started":
            values["stage"] = "Awaiting Information"
        _set(svc, eng, values)
    audit.record(
        svc.db,
        action=AuditAction.UPDATE,
        entity_type="record:engagement_letter",
        entity_id=letter.id,
        summary=f"Engagement letter {letter.name} signed by {name}"[:500],
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    return svc.serialize(letter)


# ------------------------------------------------------------------ document requests


@action(
    "document_request",
    "mark_uploaded",
    "I've Uploaded This",
    pack_key=K,
    requires_edit=False,
    portal=True,
    visible=lambda r: r.data.get("status") == "Requested",
)
def mark_uploaded(svc: RecordService, req: Record, payload: dict[str, Any]) -> dict[str, Any]:
    _set(svc, req, {"status": "Uploaded"})
    eng = _get(svc, req.data.get("engagement"))
    uid = eng.data.get("responsible_accountant") if eng else None
    if uid and eng is not None:
        notify(
            svc.db,
            uuid.UUID(str(uid)),
            f"Documents uploaded: {req.name}",
            eng.name,
            f"/o/engagement/{eng.id}",
            eng.id,
        )
    return svc.serialize(req)


@on("document_request", Event.AFTER_UPDATE, pack_key=K)
def requests_complete(change: Change) -> None:
    """When every request is accepted (or not applicable) the engagement moves on to In Progress."""
    if not change.is_changed("status") or change.data.get("status") not in ("Accepted", "Not Applicable"):
        return
    eng = _get(change.svc, change.data.get("engagement"))
    if eng is None or eng.data.get("stage") != "Awaiting Information" or not eng.data.get("letter_signed"):
        return
    pending = [
        r
        for r in live(change.svc.db, "document_request", engagement=str(eng.id))
        if r.data.get("status") not in ("Accepted", "Not Applicable")
    ]
    if not pending:
        _set(change.svc, eng, {"stage": "In Progress"})


# ------------------------------------------------------------------ time, WIP and recoverability


def _refresh_costs(svc: RecordService, eng_id: uuid.UUID | None) -> None:
    eng = svc.db.get(Record, eng_id) if eng_id else None
    if eng is None:
        return
    cost = unbilled = Decimal(0)
    for e in live(svc.db, "engagement_time_entry", engagement=str(eng.id)):
        amount = to_decimal(e.data.get("amount")) or Decimal(0)
        if e.data.get("status") != "Written Off":
            cost += amount
        if e.data.get("status") == "Unbilled" and e.data.get("billable", True):
            unbilled += amount
    fee = to_decimal(eng.data.get("fee"))
    recover = decimal_to_json(money(fee / cost * 100)) if fee is not None and cost > 0 else None
    values = {
        "time_cost": decimal_to_json(money(cost)),
        "unbilled_amount": decimal_to_json(money(unbilled)),
        "recoverability": recover,
    }
    if any(eng.data.get(k) != v for k, v in values.items()):
        _set(svc, eng, values)


@on("engagement_time_entry", Event.BEFORE_CREATE, Event.BEFORE_UPDATE, pack_key=K)
def time_rules(change: Change) -> None:
    svc, data = change.svc, change.data
    if change.old.get("status") in ("Billed", "Written Off") and not svc.system:
        raise rule("Billed or written-off time can't be changed.")
    eng = _get(svc, data.get("engagement"))
    if eng is None:
        raise rule("Choose the engagement.", "engagement")
    if change.record is None:
        data["status"] = "Unbilled"
        if not data.get("staff") and svc.user_id:
            data["staff"] = str(svc.user_id)
    if data.get("rate") is None:
        data["rate"] = _settings(svc.db).get("default_charge_out_rate")
    units = int(to_decimal(data.get("units")) or 0)
    if units < 1:
        raise rule("Record at least one 6-minute unit.", "units")
    hours = Decimal(units) * TENTHS
    data["hours"] = decimal_to_json(hours)
    data["amount"] = decimal_to_json(money(hours * (to_decimal(data.get("rate")) or Decimal(0))))


@on("engagement_time_entry", Event.AFTER_CREATE, Event.AFTER_UPDATE, Event.AFTER_DELETE, pack_key=K)
def time_changed(change: Change) -> None:
    _refresh_costs(change.svc, ref(change.data.get("engagement") or change.old.get("engagement")))


# ------------------------------------------------------------------ lodgement deadlines


@on("lodgement_deadline", Event.BEFORE_CREATE, Event.BEFORE_UPDATE, pack_key=K)
def deadline_rules(change: Change) -> None:
    data = change.data
    if data.get("status") == "Lodged" and not data.get("lodged_on"):
        data["lodged_on"] = local_today().isoformat()
    if data.get("status") in (None, "Upcoming", "Overdue") and data.get("due_date"):
        data["status"] = "Overdue" if data["due_date"] < local_today().isoformat() else "Upcoming"


def bas_periods(frequency: str, fy_start: int) -> list[tuple[str, date]]:
    """Activity statement periods for the financial year starting 1 July fy_start and their due dates."""
    if frequency == "Quarterly":
        return [
            ("Q1 Jul-Sep", date(fy_start, 10, 28)),
            ("Q2 Oct-Dec", date(fy_start + 1, 2, 28)),
            ("Q3 Jan-Mar", date(fy_start + 1, 4, 28)),
            ("Q4 Apr-Jun", date(fy_start + 1, 7, 28)),
        ]
    if frequency == "Monthly":
        out = []
        for i in range(12):
            month = (7 + i - 1) % 12 + 1
            year = fy_start if month >= 7 else fy_start + 1
            due_m, due_y = (1, year + 1) if month == 12 else (month + 1, year)
            out.append((date(year, month, 1).strftime("%b %Y"), date(due_y, due_m, 21)))
        return out
    if frequency == "Annually":
        return [(f"FY {fy_start}-{str(fy_start + 1)[-2:]}", date(fy_start + 1, 2, 28))]
    return []


@action(
    "account",
    "generate_bas_deadlines",
    "Generate BAS Deadlines",
    pack_key=K,
    visible=lambda r: r.data.get("bas_frequency") in ("Monthly", "Quarterly", "Annually"),
)
def generate_bas_deadlines(svc: RecordService, account: Record, payload: dict[str, Any]) -> dict[str, Any]:
    today = local_today()
    fy_start = today.year if today.month >= 7 else today.year - 1
    existing = {
        r.data.get("period")
        for r in live(svc.db, "lodgement_deadline", client=str(account.id), lodgement_type="BAS")
    }
    created = 0
    for period, due in bas_periods(str(account.data.get("bas_frequency")), fy_start):
        if period in existing or due < today:
            continue
        svc.create(
            "lodgement_deadline",
            {
                "client": str(account.id),
                "lodgement_type": "BAS",
                "period": period,
                "due_date": due.isoformat(),
                "responsible": account.data.get("client_manager"),
            },
        )
        created += 1
    return {"created": created}


def daily_job(db: Session, today: date | None = None) -> int:
    today = today or local_today()
    overdue = 0
    for r in live(db, "lodgement_deadline", status="Upcoming"):
        if str(r.data.get("due_date") or "9999") < today.isoformat():
            r.data = {**r.data, "status": "Overdue"}
            overdue += 1
    db.flush()
    days = _settings(db).get("deadline_reminder_days", [14, 3, 0])
    targets = [("lodgement_deadline", "due_date", "Lodgement due", first_of("responsible"))]
    return overdue + date_reminders(db, targets, days, today)


locked_when("engagement_letter", lambda r: r.data.get("status") in ("Signed", "Cancelled"))
locked_when("engagement_time_entry", lambda r: r.data.get("status") in ("Billed", "Written Off"))

PACK = register(
    Pack(
        key=K,
        name="Accounting Practice (Australia)",
        version=d.VERSION,
        region="AU",
        description="Client entities, engagements, APES 305 engagement letters with e-signature, ATO "
        "lodgement deadlines and reminders, portal document requests, time recording, WIP and "
        "recoverability, practice profiles and reports.",
        bundle=d.bundle,
        install=d.install,
        custom_permissions={d.LODGE: "Lodge Returns (registered tax agent)"},
        daily_job=daily_job,
    )
)

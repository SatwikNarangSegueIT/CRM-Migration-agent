"""Legal Practice (Australia) industry pack: definition plus the rules that need code (plan v4, section 6).

Rules: a conflict search runs when a matter is opened and whenever a party is added; a matter can't be
engaged until conflicts are cleared and (above $750) costs disclosure is given; time is recorded in
6-minute units and billed to an invoice; the trust ledger is append-only and can never be overdrawn
per matter (row-locked); transfers to office only against the matter's issued invoices; a matter can't
close with money in trust; limitation-date and court-date reminders.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import false, func, or_, select
from sqlalchemy.orm import Session

from app.apps.billing import refresh_invoice_payments
from app.apps.sales import BusinessRuleError, rule
from app.apps.service import notify
from app.engine.hooks import Change, Event, action, on, ref
from app.engine.records import RecordService
from app.engine.types import decimal_to_json, format_datetime, money, to_decimal
from app.models import Record, RecordShare
from app.packs import Pack, permission_key, register
from app.packs.common import date_reminders, first_of, ledger_balance, live
from app.packs.legal_practice import definition as d
from app.services import audit
from app.services.audit import AuditAction
from app.services.settings import get_setting

K = d.KEY
TENTHS = Decimal("0.1")


def _settings(db: Session) -> dict[str, Any]:
    return get_setting(db, K) or {}


def _has(svc: RecordService, perm: str) -> bool:
    return svc.system or svc.policy.has_custom(permission_key(K, perm))


def _matter(svc: RecordService, value: Any) -> Record | None:
    rid = ref(value)
    return svc.db.get(Record, rid) if rid else None


def _set(svc: RecordService, record: Record, values: dict[str, Any]) -> None:
    svc.elevated().update(record.object_api_name, record.id, values, record=record)


# ------------------------------------------------------------------ matters


@on("legal_matter", Event.BEFORE_CREATE, pack_key=K)
def matter_defaults(change: Change) -> None:
    data, svc = change.data, change.svc
    if data.get("stage") not in (None, "Intake") and not svc.system:
        raise rule("New matters start at Intake.", "stage")
    if data.get("hourly_rate") is None and data.get("billing_method", "Hourly") == "Hourly":
        data["hourly_rate"] = _settings(svc.db).get("default_hourly_rate")
    if not data.get("responsible_solicitor") and svc.user_id and not svc.system:
        data["responsible_solicitor"] = str(svc.user_id)
    data["conflict_cleared"] = False


def _needs_disclosure(db: Session, data: dict[str, Any]) -> bool:
    if data.get("billing_method") == "Pro Bono":
        return False
    threshold = Decimal(str(_settings(db).get("disclosure_threshold", d.DISCLOSURE_THRESHOLD)))
    estimate = to_decimal(data.get("estimated_costs"))
    return estimate is None or estimate > threshold


@on("legal_matter", Event.BEFORE_UPDATE, pack_key=K)
def matter_rules(change: Change) -> None:
    svc, data, old = change.svc, change.data, change.old
    record = change.record
    assert record is not None
    if data.get("costs_disclosure_provided") and not data.get("costs_disclosure_date"):
        data["costs_disclosure_date"] = date.today().isoformat()
    closing = (change.is_changed("stage") and data.get("stage") == "Closed") or (
        change.is_changed("status") and data.get("status") == "Closed"
    )
    if change.is_changed("stage") and not closing and not svc.system:
        new_i = d.STAGE_ORDER.index(data["stage"]) if data.get("stage") in d.STAGE_ORDER else 0
        old_i = d.STAGE_ORDER.index(old["stage"]) if old.get("stage") in d.STAGE_ORDER else 0
        if new_i > old_i and new_i >= d.STAGE_ORDER.index("Engaged"):
            if not data.get("conflict_cleared"):
                raise rule("Clear the conflict check before engaging on this matter.", "stage")
            if _needs_disclosure(svc.db, data) and not data.get("costs_disclosure_provided"):
                raise rule(
                    "Give the client costs disclosure (Legal Profession Uniform Law s 174) before work "
                    "starts, or record an estimate of $750 or less.",
                    "costs_disclosure_provided",
                )
    if closing:
        balance = ledger_balance(svc.db, "trust_transaction", "legal_matter", record.id)
        if balance != 0:
            raise rule(f"Account for the {balance} held in trust before closing the matter.", "stage")
        data["stage"], data["status"] = "Closed", "Closed"
        data.setdefault("closed_date", None)
        data["closed_date"] = data["closed_date"] or date.today().isoformat()


@on("legal_matter", Event.AFTER_CREATE, pack_key=K)
def matter_created(change: Change) -> None:
    matter = change.record
    assert matter is not None
    _sync_team_shares(change.svc, matter)
    sys = change.svc.elevated()
    sys.create("conflict_check", {"legal_matter": str(matter.id)})
    if matter.data.get("stage") == "Intake":
        _set(change.svc, matter, {"stage": "Conflict Check"})


@on("legal_matter", Event.AFTER_UPDATE, pack_key=K)
def matter_updated(change: Change) -> None:
    if change.is_changed("responsible_solicitor") or change.is_changed("supervising_principal"):
        assert change.record is not None
        _sync_team_shares(change.svc, change.record)


@on("legal_matter", Event.BEFORE_DELETE, pack_key=K)
def matter_retention(change: Change) -> None:
    assert change.record is not None
    if change.svc.db.scalar(
        select(Record.id)
        .where(
            Record.object_api_name.in_(("trust_transaction", "legal_time_entry")),
            Record.data["legal_matter"].astext == str(change.record.id),
        )
        .limit(1)
    ):
        raise rule("Matters with time or trust records must be kept (7-year retention).")


def _sync_team_shares(svc: RecordService, matter: Record) -> None:
    from sqlalchemy import delete

    svc.db.execute(
        delete(RecordShare).where(RecordShare.record_id == matter.id, RecordShare.created_by_id.is_(None))
    )
    for field in ("responsible_solicitor", "supervising_principal"):
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


# ------------------------------------------------------------------ conflict checks


def _client_name(db: Session, matter: Record) -> str:
    client = db.get(Record, ref(matter.data.get("client"))) if matter.data.get("client") else None
    return client.name if client else ""


def _default_terms(db: Session, matter: Record) -> list[str]:
    names = [_client_name(db, matter)]
    names += [p.name for p in live(db, "party", legal_matter=str(matter.id))]
    org = db.get(Record, ref(matter.data.get("organisation"))) if matter.data.get("organisation") else None
    if org is not None:
        names.append(org.name)
    seen: dict[str, str] = {}
    for n in names:
        if n and n.strip() and n.strip().lower() not in seen:
            seen[n.strip().lower()] = n.strip()
    return list(seen.values())


def conflict_search(db: Session, matter: Record, terms: list[str]) -> list[str]:
    """Where else each name appears: as a party on another matter, or as another matter's client.

    The matter's own client is searched only against other matters' parties (acting against a former
    client); every other name is also searched against clients, organisations and contacts.
    """
    client_name = _client_name(db, matter).lower()
    own_ids = {str(matter.data.get(f)) for f in ("client", "organisation") if matter.data.get(f)}
    for p in live(db, "party", legal_matter=str(matter.id)):
        own_ids.update(str(p.data[f]) for f in ("contact", "organisation") if p.data.get(f))
    found: list[str] = []
    for term in terms:
        t = term.strip()
        if len(t) < 2:
            continue
        pattern = f"%{t}%"
        parties = db.scalars(
            select(Record).where(
                Record.object_api_name == "party",
                Record.is_deleted == false(),
                Record.data["legal_matter"].astext != str(matter.id),
                or_(func.lower(Record.name).like(pattern.lower()), Record.data["acn_abn"].astext == t),
            )
        ).all()
        for p in parties:
            other = db.get(Record, ref(p.data.get("legal_matter")))
            found.append(f"{t}: {p.data.get('role', 'Party')} on matter {other.name if other else '?'}")
        if t.lower() == client_name:
            continue
        people = db.scalars(
            select(Record).where(
                Record.object_api_name.in_(("contact", "account")),
                Record.is_deleted == false(),
                func.lower(Record.name).like(pattern.lower()),
            )
        ).all()
        for person in people:
            if str(person.id) in own_ids:
                continue
            matters = db.scalars(
                select(Record.name).where(
                    Record.object_api_name == "legal_matter",
                    Record.is_deleted == false(),
                    Record.id != matter.id,
                    or_(
                        Record.data["client"].astext == str(person.id),
                        Record.data["organisation"].astext == str(person.id),
                    ),
                )
            ).all()
            kind = "Client" if person.object_api_name == "contact" else "Organisation"
            where = f" on matters {', '.join(matters)}" if matters else " (existing record)"
            found.append(f"{t}: {kind} {person.name}{where}")
    return list(dict.fromkeys(found))


def _run_check(svc: RecordService, check: Record) -> Record:
    matter = _matter(svc, check.data.get("legal_matter"))
    if matter is None:
        return check
    terms = [ln.strip() for ln in str(check.data.get("search_terms") or "").splitlines() if ln.strip()]
    matches = conflict_search(svc.db, matter, terms)
    _set(
        svc,
        check,
        {
            "matches": "\n".join(matches) or "No matches.",
            "match_count": len(matches),
            "result": "Potential Conflict" if matches else "Clear",
            "checked_by": str(svc.user_id) if svc.user_id else None,
            "checked_at": format_datetime(datetime.now(UTC)),
        },
    )
    return check


@on("conflict_check", Event.BEFORE_CREATE, pack_key=K)
def check_defaults(change: Change) -> None:
    matter = _matter(change.svc, change.data.get("legal_matter"))
    if matter is None:
        raise rule("Choose the matter.", "legal_matter")
    if not str(change.data.get("search_terms") or "").strip():
        change.data["search_terms"] = "\n".join(_default_terms(change.svc.db, matter))
    change.data["result"] = "Pending"


@on("conflict_check", Event.AFTER_CREATE, pack_key=K)
def check_created(change: Change) -> None:
    assert change.record is not None
    _run_check(change.svc, change.record)


@on("conflict_check", Event.BEFORE_UPDATE, pack_key=K)
def check_clearance(change: Change) -> None:
    svc, data = change.svc, change.data
    if not change.is_changed("result") or svc.system:
        return
    if data.get("result") == "Clear" and int(data.get("match_count") or 0) > 0:
        if not _has(svc, d.CLEAR_CONFLICTS):
            raise rule("Only a principal can clear a check that found matches.", "result")
        if not str(data.get("clearance_notes") or "").strip():
            raise rule("Record why the matches are not a conflict (or the waiver).", "clearance_notes")
        data["cleared_by"] = str(svc.user_id)


@on("conflict_check", Event.AFTER_UPDATE, pack_key=K)
def check_updates_matter(change: Change) -> None:
    if not change.is_changed("result"):
        return
    matter = _matter(change.svc, change.data.get("legal_matter"))
    if matter is None:
        return
    cleared = change.data.get("result") == "Clear"
    if bool(matter.data.get("conflict_cleared")) != cleared:
        _set(change.svc, matter, {"conflict_cleared": cleared})
    if change.data.get("result") in ("Potential Conflict", "Conflict"):
        uid = matter.data.get("responsible_solicitor") or (str(matter.owner_id) if matter.owner_id else None)
        if uid:
            notify(
                change.svc.db,
                uuid.UUID(str(uid)),
                f"Possible conflict on {matter.name}",
                "Review the conflict check before acting.",
                f"/o/conflict_check/{change.record.id if change.record else ''}",
                matter.id,
            )
    if change.data.get("result") == "Clear" and int(change.data.get("match_count") or 0) > 0:
        audit.record(
            change.svc.db,
            action=AuditAction.UPDATE,
            entity_type="record:conflict_check",
            entity_id=change.record.id if change.record else None,
            summary=f"Conflict cleared on {matter.name}: {str(change.data.get('clearance_notes'))[:300]}",
            actor_id=change.svc.user_id,
            meta=change.svc.request_meta,
        )


@action("conflict_check", "run_search", "Run Search Again", pack_key=K)
def rerun_check(svc: RecordService, check: Record, payload: dict[str, Any]) -> dict[str, Any]:
    return svc.serialize(_run_check(svc, check))


@on("party", Event.AFTER_CREATE, pack_key=K)
def party_added(change: Change) -> None:
    """A new party gets its own conflict search; matches put the matter back to "not cleared"."""
    assert change.record is not None
    change.svc.elevated().create(
        "conflict_check",
        {"legal_matter": change.data.get("legal_matter"), "search_terms": change.record.name},
    )


# ------------------------------------------------------------------ time recording


def _refresh_wip(svc: RecordService, matter_id: uuid.UUID | None) -> None:
    matter = svc.db.get(Record, matter_id) if matter_id else None
    if matter is None:
        return
    total = Decimal(0)
    for e in live(svc.db, "legal_time_entry", legal_matter=str(matter.id), status="Unbilled"):
        if e.data.get("billable", True):
            total += to_decimal(e.data.get("amount")) or Decimal(0)
    value = decimal_to_json(money(total))
    if matter.data.get("unbilled_amount") != value:
        _set(svc, matter, {"unbilled_amount": value})


@on("legal_time_entry", Event.BEFORE_CREATE, Event.BEFORE_UPDATE, pack_key=K)
def time_rules(change: Change) -> None:
    svc, data = change.svc, change.data
    if change.old.get("status") in ("Billed", "Written Off") and not svc.system:
        raise rule("Billed or written-off time can't be changed.")
    matter = _matter(svc, data.get("legal_matter"))
    if matter is None:
        raise rule("Choose the matter.", "legal_matter")
    if change.record is None:
        if matter.data.get("status") == "Closed" and not svc.system:
            raise rule("Time can't be recorded on a closed matter.", "legal_matter")
        data["status"] = "Unbilled"
        if not data.get("timekeeper") and svc.user_id:
            data["timekeeper"] = str(svc.user_id)
    if data.get("rate") is None:
        data["rate"] = matter.data.get("hourly_rate") or _settings(svc.db).get("default_hourly_rate")
    units = int(to_decimal(data.get("units")) or 0)
    if units < 1:
        raise rule("Record at least one 6-minute unit.", "units")
    hours = Decimal(units) * TENTHS
    data["hours"] = decimal_to_json(hours)
    data["amount"] = decimal_to_json(money(hours * (to_decimal(data.get("rate")) or Decimal(0))))


@on("legal_time_entry", Event.AFTER_CREATE, Event.AFTER_UPDATE, Event.AFTER_DELETE, pack_key=K)
def time_changed(change: Change) -> None:
    _refresh_wip(change.svc, ref(change.data.get("legal_matter") or change.old.get("legal_matter")))


@action(
    "legal_time_entry",
    "write_off",
    "Write Off",
    pack_key=K,
    visible=lambda r: r.data.get("status") == "Unbilled",
    guard=lambda svc, r: None if _has(svc, d.CLEAR_CONFLICTS) else "Only a principal can write off time.",
)
def write_off(svc: RecordService, entry: Record, payload: dict[str, Any]) -> dict[str, Any]:
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise BusinessRuleError("Enter the reason for the write-off.", fields={"reason": "Required"})
    _set(svc, entry, {"status": "Written Off"})
    audit.record(
        svc.db,
        action=AuditAction.UPDATE,
        entity_type="record:legal_time_entry",
        entity_id=entry.id,
        summary=f"Time {entry.name} written off: {reason}"[:500],
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    return svc.serialize(entry)


def _billing_account(svc: RecordService, matter: Record) -> Record:
    org = _matter(svc, matter.data.get("organisation"))
    if org is not None:
        return org
    client = _matter(svc, matter.data.get("client"))
    if client is None:
        raise rule("The matter has no client.")
    acct = _matter(svc, client.data.get("account"))
    if acct is None:
        acct = svc.elevated().create("account", {"name": client.name, "type": "Customer"})
    _set(svc, matter, {"organisation": str(acct.id)})
    return acct


@action(
    "legal_matter",
    "bill_time",
    "Invoice Unbilled Time",
    pack_key=K,
    visible=lambda r: bool(to_decimal(r.data.get("unbilled_amount"))),
)
def bill_time(svc: RecordService, matter: Record, payload: dict[str, Any]) -> dict[str, Any]:
    entries = [
        e
        for e in live(svc.db, "legal_time_entry", legal_matter=str(matter.id), status="Unbilled")
        if e.data.get("billable", True)
    ]
    if not entries:
        raise rule("There is no unbilled billable time on this matter.")
    entries.sort(key=lambda e: (e.data.get("entry_date") or "", e.name))
    account = _billing_account(svc, matter)
    invoice = svc.create(
        "invoice",
        {
            "account": str(account.id),
            "contact": matter.data.get("client"),
            "legal_matter": str(matter.id),
            "notes": f"Professional fees: {matter.data.get('title') or matter.name}",
        },
    )
    sys = svc.elevated()
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
        sys.update("legal_time_entry", e.id, {"status": "Billed", "invoice": str(invoice.id)}, record=e)
    _refresh_wip(svc, matter.id)
    return {"invoice_id": str(invoice.id), "entries": len(entries)}


# ------------------------------------------------------------------ trust ledger


def trust_balance(db: Session, matter_id: uuid.UUID) -> Decimal:
    return ledger_balance(db, "trust_transaction", "legal_matter", matter_id)


@on("trust_transaction", Event.BEFORE_CREATE, pack_key=K)
def trust_rules(change: Change) -> None:
    svc, data = change.svc, change.data
    if not _has(svc, d.MANAGE_TRUST):
        raise rule("Recording trust money needs the Manage Trust Account permission.")
    matter_id = ref(data.get("legal_matter"))
    # Row-lock the matter so concurrent payments can't overdraw its trust balance.
    matter = (
        svc.db.scalar(select(Record).where(Record.id == matter_id).with_for_update()) if matter_id else None
    )
    if matter is None:
        raise rule("Choose the matter.", "legal_matter")
    data["client"] = matter.data.get("client")
    amount = money(to_decimal(data.get("amount")) or 0)
    if amount <= 0:
        raise rule("Enter a positive amount.", "amount")
    kind = data.get("type")
    if kind == "Transfer to Office":
        invoice = _matter(svc, data.get("invoice"))
        if (
            invoice is None
            or invoice.data.get("legal_matter") != str(matter.id)
            or invoice.data.get("status") not in ("Issued", "Partially Paid")
        ):
            raise rule("Transfers to office need an issued, unpaid invoice on this matter.", "invoice")
        if amount > money(to_decimal(invoice.data.get("balance")) or 0):
            raise rule("The transfer is more than the invoice's balance due.", "amount")
    elif data.get("invoice"):
        raise rule("Only transfers to office are linked to invoices.", "invoice")
    signed = amount if kind == "Receipt" else -amount
    available = trust_balance(svc.db, matter.id)
    if available + signed < 0:
        raise rule(f"Trust money can't be overdrawn (available on this matter: {available}).", "amount")
    data["signed_amount"] = decimal_to_json(signed)
    data["balance_after"] = decimal_to_json(available + signed)


@on("trust_transaction", Event.AFTER_CREATE, pack_key=K)
def trust_posted(change: Change) -> None:
    assert change.record is not None
    matter = _matter(change.svc, change.data.get("legal_matter"))
    if matter is not None:
        _set(change.svc, matter, {"trust_balance": change.data.get("balance_after")})
    if change.data.get("type") != "Transfer to Office":
        return
    invoice = _matter(change.svc, change.data.get("invoice"))
    if invoice is None:
        return
    change.svc.elevated().create(
        "payment",
        {
            "invoice": str(invoice.id),
            "amount": change.data.get("amount"),
            "payment_date": change.data.get("transaction_date"),
            "method": "Other",
            "reference": f"Trust transfer {change.record.name}",
        },
    )
    refresh_invoice_payments(change.svc, invoice)


@on("trust_transaction", Event.BEFORE_UPDATE, Event.BEFORE_DELETE, pack_key=K)
def trust_is_append_only(change: Change) -> None:
    if not change.svc.system:
        raise rule("Trust records can't be changed or deleted; record a correcting transaction.")


def trust_statement(svc: RecordService, matter_id: uuid.UUID) -> dict[str, Any]:
    """Trust ledger for one matter with running balance."""
    matter = svc.get("legal_matter", matter_id)
    res = svc.query(
        "trust_transaction",
        filters={
            "logic": "and",
            "conditions": [{"field": "legal_matter", "op": "equals", "value": str(matter_id)}],
        },
        sort=[{"field": "created_at", "direction": "asc"}],
        limit=500,
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
                "payer_payee": r.data.get("payer_payee"),
                "amount": r.data.get("amount"),
                "signed_amount": r.data.get("signed_amount"),
                "reference": r.data.get("reference"),
                "running_balance": decimal_to_json(money(running)),
            }
        )
    return {
        "matter": {"id": str(matter.id), "name": matter.name, "title": matter.data.get("title")},
        "transactions": rows,
        "balance": decimal_to_json(trust_balance(svc.db, matter_id)),
    }


# ------------------------------------------------------------------ court dates and reminders


@on("court_date", Event.BEFORE_CREATE, pack_key=K)
def court_date_name(change: Change) -> None:
    """Named from the type and date ("Hearing 2026-03-12") unless a name is given."""
    if change.system.get("name"):
        return
    when = str(change.data.get("date_time") or "")
    try:  # the local date: a 10 am Sydney hearing is stored as the previous evening in UTC
        from zoneinfo import ZoneInfo

        from app.core.config import get_settings

        when = datetime.fromisoformat(when).astimezone(ZoneInfo(get_settings().timezone)).date().isoformat()
    except ValueError:
        when = when[:10]
    change.system["name"] = f"{change.data.get('type') or 'Court date'} {when}".strip()[:255]


@on("court_date", Event.AFTER_CREATE, Event.AFTER_UPDATE, Event.AFTER_DELETE, pack_key=K)
def court_date_changed(change: Change) -> None:
    matter = _matter(change.svc, change.data.get("legal_matter") or change.old.get("legal_matter"))
    if matter is None:
        return
    now = format_datetime(datetime.now(UTC))
    upcoming = sorted(
        str(c.data["date_time"])
        for c in live(change.svc.db, "court_date", legal_matter=str(matter.id))
        if c.data.get("date_time") and str(c.data["date_time"]) >= now
    )
    nxt = upcoming[0] if upcoming else None
    if matter.data.get("next_court_date") != nxt:
        _set(change.svc, matter, {"next_court_date": nxt})


def daily_reminders(db: Session, today: date | None = None) -> int:
    s = _settings(db)
    limitation = [("legal_matter", "limitation_date", "Limitation date", first_of("responsible_solicitor"))]
    court = [("court_date", "date_time", "Court date", first_of("appearing"))]
    count = date_reminders(db, limitation, s.get("limitation_reminder_days", [90, 30, 7]), today)
    return count + date_reminders(db, court, s.get("court_reminder_days", [7, 1]), today)


PACK = register(
    Pack(
        key=K,
        name="Legal Practice (Australia)",
        version=d.VERSION,
        region="AU",
        description="Matters, parties, conflict checks, time recording (6-minute units) and billing, court "
        "dates, trust accounting, costs disclosure (Legal Profession Uniform Law), practice profiles, "
        "reports and a client portal.",
        bundle=d.bundle,
        install=d.install,
        custom_permissions={
            d.CLEAR_CONFLICTS: "Clear Conflicts and Write Off Time",
            d.MANAGE_TRUST: "Manage Trust Account",
        },
        daily_job=daily_reminders,
    )
)

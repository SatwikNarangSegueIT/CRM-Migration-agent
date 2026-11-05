"""Legal Practice (Australia) industry pack: definition plus the rules that need code (plan v4, section 6).

Rules: a conflict search runs when a matter is opened and whenever a party is added; a matter can't be
engaged until conflicts are cleared and (above $750) costs disclosure is given; time is recorded in
6-minute units and billed to an invoice; the trust ledger is append-only and can never be overdrawn
per matter (row-locked); transfers to office only against the matter's issued invoices; a matter can't
close with money in trust; limitation-date and court-date reminders.
"""

from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import false, func, or_, select
from sqlalchemy.orm import Session, object_session

from app.apps.billing import billing_account_for, refresh_invoice_payments
from app.apps.sales import BusinessRuleError, rule
from app.apps.service import notify
from app.core.clock import local_today
from app.engine.hooks import Change, Event, action, locked_when, on, ref
from app.engine.records import RecordService
from app.engine.types import decimal_to_json, format_datetime, money, to_decimal
from app.models import Record, RecordShare
from app.packs import Pack, permission_key, register
from app.packs.common import date_reminders, first_of, ledger_balance, live, unless
from app.packs.legal_practice import definition as d
from app.services import audit
from app.services.audit import AuditAction
from app.services.settings import get_setting

K = d.KEY
TENTHS = Decimal("0.1")


def _settings(db: Session) -> dict[str, Any]:
    return get_setting(db, K) or {}


def _cfg(db: Session, key: str) -> Any:
    """A practice setting, with the shipped default for settings saved before it existed."""
    return _settings(db).get(key, d.SETTINGS_DEFAULTS[key])


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
    """Uniform Law s 174: unless pro bono, for a commercial or government client (s 170) or costs are not
    likely to exceed $750."""
    if data.get("billing_method") == "Pro Bono" or data.get("client_type") == "Commercial or Government":
        return False
    threshold = Decimal(str(_cfg(db, "disclosure_threshold")))
    estimate = to_decimal(data.get("estimated_costs"))
    return estimate is None or estimate > threshold


def _significant(db: Session, before: Decimal, after: Decimal) -> bool:
    pct = Decimal(str(_cfg(db, "significant_change_percent")))
    return after > before and (before <= 0 or (after - before) * 100 >= before * pct)


def _disclosure_rules(change: Change) -> None:
    """How the disclosure was given, and changes that need updated disclosure (s 174(1)(b), s 174(5))."""
    svc, data, old = change.svc, change.data, change.old
    if (
        data.get("costs_disclosure_provided")
        and not data.get("disclosure_method")
        and _needs_disclosure(svc.db, data)
    ):
        data["disclosure_method"] = d.FULL_DISCLOSURE
    estimate = to_decimal(data.get("estimated_costs"))
    limit = Decimal(str(_cfg(svc.db, "standard_disclosure_limit")))
    if (
        data.get("disclosure_method") == d.STANDARD_FORM
        and estimate is not None
        and estimate > limit
        and (change.is_changed("disclosure_method") or change.is_changed("estimated_costs"))
    ):
        raise rule(
            f"The uniform standard disclosure form is only for costs up to ${limit:,.0f}; give full written "
            "disclosure (Uniform Law s 174).",
            "disclosure_method",
        )
    if change.is_changed("costs_disclosure_date") and data.get("costs_disclosure_date"):
        data["disclosure_update_due"] = False  # updated disclosure given
    previous = to_decimal(old.get("estimated_costs"))
    if (
        change.record is not None
        and change.is_changed("estimated_costs")
        and old.get("costs_disclosure_provided")
        and previous is not None
        and estimate is not None
        and _significant(svc.db, previous, estimate)
        and not change.is_changed("costs_disclosure_date")
    ):
        data["disclosure_update_due"] = True
        uid = data.get("responsible_solicitor") or (
            str(change.record.owner_id) if change.record.owner_id else None
        )
        if uid:
            notify(
                svc.db,
                uuid.UUID(str(uid)),
                f"Updated costs disclosure due: {change.record.name}",
                f"The estimate went from ${previous:,.2f} to ${estimate:,.2f}. Tell the client in writing "
                "(Uniform Law s 174(1)(b)), then update the disclosure date.",
                f"/o/legal_matter/{change.record.id}",
                change.record.id,
            )


@on("legal_matter", Event.BEFORE_UPDATE, pack_key=K)
def matter_rules(change: Change) -> None:
    svc, data, old = change.svc, change.data, change.old
    record = change.record
    assert record is not None
    if data.get("costs_disclosure_provided") and not data.get("costs_disclosure_date"):
        data["costs_disclosure_date"] = local_today().isoformat()
    if not svc.system:
        _disclosure_rules(change)
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
                threshold = Decimal(str(_cfg(svc.db, "disclosure_threshold")))
                raise rule(
                    "Give the client costs disclosure (Legal Profession Uniform Law s 174) before work "
                    f"starts, or record an estimate of ${threshold:,.0f} or less.",
                    "costs_disclosure_provided",
                )
            _engagement_checks(svc, data)
    if closing and not svc.system and to_decimal(data.get("unbilled_amount")):
        raise rule("Bill or write off the unbilled time before closing the matter.", "stage")
    if closing:
        balance = ledger_balance(svc.db, "trust_transaction", "legal_matter", record.id)
        if balance != 0:
            raise rule(f"Account for the {balance} held in trust before closing the matter.", "stage")
        data["stage"], data["status"] = "Closed", "Closed"
        data.setdefault("closed_date", None)
        data["closed_date"] = data["closed_date"] or local_today().isoformat()


def _engagement_checks(svc: RecordService, data: dict[str, Any]) -> None:
    """Before engaging: verify the client's identity where the practice requires it (conveyancing: ARNECC
    verification of identity), and record the limitation date on claims (unless proceedings are filed)."""
    area = data.get("practice_area")
    if area and area in (_cfg(svc.db, "voi_practice_areas") or []):
        client = _matter(svc, data.get("client"))
        if client is not None and not client.data.get("id_verified"):
            raise rule(
                f"Verify {client.name}'s identity (VOI) before acting on a {area} matter: tick Identity "
                "Verified on the client.",
                "client",
            )
    if (
        area
        and area in (_cfg(svc.db, "limitation_practice_areas") or [])
        and not data.get("limitation_date")
        and not str(data.get("court_file_number") or "").strip()
    ):
        raise rule(
            f"Record the limitation date before engaging on a {area} matter (or the court file number once "
            "proceedings are filed).",
            "limitation_date",
        )


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
    acct = billing_account_for(svc, client)
    _set(svc, matter, {"organisation": str(acct.id)})
    return acct


def _invoiced_total(svc: RecordService, matter: Record, *, issued_only: bool) -> Decimal:
    skip = ("Void", "Draft") if issued_only else ("Void",)
    return sum(
        (
            to_decimal(i.data.get("subtotal")) or Decimal(0)
            for i in live(svc.db, "invoice", legal_matter=str(matter.id))
            if i.data.get("status") not in skip
        ),
        Decimal(0),
    )


def _check_billing_against_disclosure(svc: RecordService, matter: Record, amount: Decimal) -> None:
    """Billing must not run past what the client was told (Uniform Law s 174(1)(b))."""
    if matter.data.get("disclosure_update_due"):
        raise rule(
            "Give the client updated costs disclosure first (Uniform Law s 174(1)(b)), then record the new "
            "disclosure date on the matter."
        )
    estimate = to_decimal(matter.data.get("estimated_costs"))
    if estimate is None or not _needs_disclosure(svc.db, matter.data):
        return
    total = _invoiced_total(svc, matter, issued_only=False) + amount
    if _significant(svc.db, estimate, total):
        raise rule(
            f"This bill takes the matter to ${total:,.2f}, past the ${estimate:,.2f} estimate disclosed to "
            "the client. Disclose the revised estimate (Uniform Law s 174(1)(b)) and update it on the "
            "matter first."
        )


@action(
    "legal_matter",
    "bill_time",
    "Invoice Unbilled Time",
    pack_key=K,
    visible=lambda r: (
        bool(to_decimal(r.data.get("unbilled_amount"))) and r.data.get("billing_method") != "Fixed Fee"
    ),
)
def bill_time(svc: RecordService, matter: Record, payload: dict[str, Any]) -> dict[str, Any]:
    entries = [
        e
        for e in live(svc.db, "legal_time_entry", legal_matter=str(matter.id), status="Unbilled")
        if e.data.get("billable", True)
    ]
    if not entries:
        raise rule("There is no unbilled billable time on this matter.")
    if matter.data.get("billing_method") == "Fixed Fee":
        raise rule("This is a fixed-fee matter: use Invoice Fixed Fee (the time is absorbed).")
    entries.sort(key=lambda e: (e.data.get("entry_date") or "", e.name))
    _check_billing_against_disclosure(
        svc, matter, sum((to_decimal(e.data.get("amount")) or Decimal(0) for e in entries), Decimal(0))
    )
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


@action(
    "legal_matter",
    "bill_fixed_fee",
    "Invoice Fixed Fee",
    pack_key=K,
    visible=lambda r: (
        r.data.get("billing_method") == "Fixed Fee" and bool(to_decimal(r.data.get("fixed_fee")))
    ),
)
def bill_fixed_fee(svc: RecordService, matter: Record, payload: dict[str, Any]) -> dict[str, Any]:
    """One line for the agreed fixed fee; time recorded on the matter is absorbed (marked billed)."""
    fee = to_decimal(matter.data.get("fixed_fee"))
    if matter.data.get("billing_method") != "Fixed Fee" or not fee:
        raise rule("Enter the agreed fixed fee on a fixed-fee matter first.", "fixed_fee")
    if _invoiced_total(svc, matter, issued_only=False) >= money(fee):
        raise rule("The fixed fee has already been invoiced on this matter.")
    _check_billing_against_disclosure(svc, matter, money(fee))
    account = _billing_account(svc, matter)
    invoice = svc.create(
        "invoice",
        {
            "account": str(account.id),
            "contact": matter.data.get("client"),
            "legal_matter": str(matter.id),
            "notes": f"Agreed fixed fee: {matter.data.get('title') or matter.name}",
        },
    )
    sys = svc.elevated()
    sys.create(
        "invoice_line",
        {
            "invoice": str(invoice.id),
            "description": f"Professional fees (agreed fixed fee): {matter.data.get('title') or matter.name}"[
                :255
            ],
            "quantity": 1,
            "unit_price": decimal_to_json(money(fee)),
            "sort_order": 1,
        },
    )
    entries = live(svc.db, "legal_time_entry", legal_matter=str(matter.id), status="Unbilled")
    for e in entries:
        sys.update("legal_time_entry", e.id, {"status": "Billed", "invoice": str(invoice.id)}, record=e)
    _refresh_wip(svc, matter.id)
    return {"invoice_id": str(invoice.id), "entries": len(entries)}


@on("invoice", Event.AFTER_CREATE, Event.AFTER_UPDATE, pack_key=K)
def matter_billed_to_date(change: Change) -> None:
    """The matter's billed-to-date (issued, not void, ex GST) follows its invoices."""
    matter = _matter(change.svc, change.data.get("legal_matter") or change.old.get("legal_matter"))
    if matter is None:
        return
    value = decimal_to_json(money(_invoiced_total(change.svc, matter, issued_only=True)))
    if matter.data.get("billed_to_date") != value:
        _set(change.svc, matter, {"billed_to_date": value})


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
    if kind in ("Payment", "Transfer to Office") and data.get("method") in ("Cash", "Card"):
        raise rule(
            "Trust money is paid out only by EFT, BPAY or cheque, never in cash (Legal Profession Uniform "
            "General Rules).",
            "method",
        )
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
        _significant_cash(change, matter)
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


def _significant_cash(change: Change, matter: Record) -> None:
    """A cash receipt of $10,000 or more is reported to AUSTRAC within 15 business days (Financial
    Transaction Reports Act 1988, s 15A): a task for the person who receipted it."""
    data, record = change.data, change.record
    threshold = Decimal(str(_cfg(change.svc.db, "significant_cash_threshold")))
    amount = to_decimal(data.get("amount")) or Decimal(0)
    if record is None or data.get("type") != "Receipt" or data.get("method") != "Cash" or amount < threshold:
        return
    change.svc.elevated().create(
        "task",
        {
            "name": f"Report significant cash transaction {record.name} to AUSTRAC"[:255],
            "related_to": str(matter.id),
            "priority": "High",
            "due_date": (local_today() + timedelta(days=21)).isoformat(),
            "description": f"Cash receipt of ${amount:,.2f} from {data.get('payer_payee') or 'the payer'} on "
            f"{data.get('transaction_date') or local_today().isoformat()}. Lodge the significant cash "
            "transaction report with AUSTRAC within 15 business days and record the reference on the trust "
            "receipt.",
        },
        owner_id=change.svc.user_id,
    )


@on("trust_transaction", Event.BEFORE_UPDATE, Event.BEFORE_DELETE, pack_key=K)
def trust_is_append_only(change: Change) -> None:
    if change.svc.system:
        return
    if change.record is not None and change.changed and change.changed <= {"austrac_reference"}:
        return  # the AUSTRAC report reference is recorded after the receipt
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


# ------------------------------------------------------------------ monthly trust reconciliation


def _month_end(value: Any) -> date:
    try:
        day = date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise rule("Choose the last day of the month being reconciled.", "period_end") from exc
    if day.day != monthrange(day.year, day.month)[1]:
        raise rule("Choose the last day of the month being reconciled.", "period_end")
    return day


def ledger_total_at(db: Session, period_end: date) -> Decimal:
    """The sum of every matter's trust ledger up to and including the month end."""
    total = Decimal(0)
    for t in live(db, "trust_transaction"):
        if str(t.data.get("transaction_date") or "9999") <= period_end.isoformat():
            total += to_decimal(t.data.get("signed_amount")) or Decimal(0)
    return money(total)


@on("trust_reconciliation", Event.BEFORE_CREATE, Event.BEFORE_UPDATE, pack_key=K)
def reconciliation_rules(change: Change) -> None:
    """Uniform General Rules: reconcile the trust account monthly, within 15 working days after month end.
    The bank balance plus uncleared items must equal the total of the matter ledgers; a principal signs it
    off, after which it can't be changed."""
    svc, data, old = change.svc, change.data, change.old
    if svc.system:
        return
    if not _has(svc, d.MANAGE_TRUST):
        raise rule("Reconciling the trust account needs the Manage Trust Account permission.")
    if old.get("status") == "Reconciled":
        raise rule(
            "A signed-off reconciliation can't be changed; record a correcting entry and reconcile again."
        )
    period_end = _month_end(data.get("period_end"))
    clash = svc.db.scalar(
        select(Record.id)
        .where(
            Record.object_api_name == "trust_reconciliation",
            Record.is_deleted == false(),
            Record.data["period_end"].astext == period_end.isoformat(),
            Record.id != (change.record.id if change.record else uuid.uuid4()),
        )
        .limit(1)
    )
    if clash:
        raise rule(f"{period_end:%B %Y} has already been reconciled or started.", "period_end")
    change.system["name"] = f"Trust reconciliation {period_end:%B %Y}"
    ledger = ledger_total_at(svc.db, period_end)
    bank = money(to_decimal(data.get("bank_balance")) or 0)
    adjustments = money(to_decimal(data.get("adjustments")) or 0)
    data["ledger_total"] = decimal_to_json(ledger)
    data["difference"] = decimal_to_json(money(bank + adjustments - ledger))
    if change.record is None:
        data["prepared_by"] = str(svc.user_id) if svc.user_id else None
        data["status"] = "Draft"
    elif change.is_changed("status") and data.get("status") == "Reconciled":
        difference = money(bank + adjustments - ledger)
        if difference != 0:
            raise rule(
                f"The trust account doesn't reconcile (difference ${difference:,.2f}). Find and correct it, "
                "and explain any uncleared items, before signing off.",
                "status",
            )
        if not _has(svc, d.CLEAR_CONFLICTS):
            raise rule("A principal signs off the trust reconciliation.", "status")
        data["reconciled_by"] = str(svc.user_id)
        data["reconciled_at"] = format_datetime(datetime.now(UTC))


def reconciliation_reminders(db: Session, today: date | None = None) -> int:
    """From the 10th of each month, remind principals and trust accountants until last month is reconciled."""
    from app.models import Notification, Profile, User

    today = today or local_today()
    if today.day < 10:
        return 0
    if not live(db, "trust_transaction"):
        return 0
    first = today.replace(day=1)
    last_month_end = first - timedelta(days=1)
    if any(
        r.data.get("status") == "Reconciled"
        for r in live(db, "trust_reconciliation", period_end=last_month_end.isoformat())
    ):
        return 0
    title = f"Trust reconciliation due: {last_month_end:%B %Y}"
    people = db.scalars(
        select(User)
        .join(Profile, Profile.id == User.profile_id)
        .where(Profile.key.in_(("lp_principal", "lp_accounts")), User.is_active)
    ).all()
    count = 0
    for person in people:
        exists = db.scalar(
            select(Notification.id)
            .where(Notification.user_id == person.id, Notification.title == title)
            .limit(1)
        )
        if exists:
            continue
        notify(
            db,
            person.id,
            title,
            "Reconcile the trust account within 15 working days after month end (Uniform General Rules).",
            "/o/trust_reconciliation",
            None,
        )
        count += 1
    db.flush()
    return count


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
    open_matter = unless(first_of("responsible_solicitor"), lambda r: r.data.get("status") == "Closed")
    limitation = [("legal_matter", "limitation_date", "Limitation date", open_matter)]
    court = [("court_date", "date_time", "Court date", first_of("appearing"))]
    count = date_reminders(db, limitation, s.get("limitation_reminder_days", [90, 30, 7]), today)
    count += reconciliation_reminders(db, today)
    return count + date_reminders(db, court, s.get("court_reminder_days", [7, 1]), today)


locked_when("legal_time_entry", lambda r: r.data.get("status") in ("Billed", "Written Off"))
locked_when("trust_reconciliation", lambda r: r.data.get("status") == "Reconciled")


def _austrac_reference_due(r: Record) -> bool:
    """A cash receipt at or above the practice's significant cash threshold, still without its AUSTRAC
    report reference: the one change the trust ledger accepts after posting."""
    if r.data.get("type") != "Receipt" or r.data.get("method") != "Cash" or r.data.get("austrac_reference"):
        return False
    db = object_session(r)
    threshold = (
        _cfg(db, "significant_cash_threshold")
        if db is not None
        else d.SETTINGS_DEFAULTS["significant_cash_threshold"]
    )
    return (to_decimal(r.data.get("amount")) or Decimal(0)) >= Decimal(str(threshold))


# Trust records are append-only; a large cash receipt stays open until its AUSTRAC reference is recorded.
locked_when("trust_transaction", lambda r: not _austrac_reference_due(r))

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
        key_dates=(
            ("court_date", "date_time", "Court", ("appearing",), []),
            (
                "legal_matter",
                "limitation_date",
                "Limitation date",
                ("responsible_solicitor", "supervising_principal"),
                [{"field": "status", "op": "not_equals", "value": "Closed"}],
            ),
        ),
    )
)

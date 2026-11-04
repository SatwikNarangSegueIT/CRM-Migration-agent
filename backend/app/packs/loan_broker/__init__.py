"""Loan Broker (Australia) industry pack: definition plus the rules that need code (plan v4, section 6).

Rules (NCCP / Best Interests Duty): no credit assistance past fact find until the credit guide and privacy
consent are recorded; an application is lodged with a lender only after the preliminary assessment and
the BID record (requirements, products considered, why the recommendation is in the client's interests);
lodging needs the Submit to Lender permission; assessment records are kept 7 years. LVR is calculated;
settlement creates the expected upfront commission from the lender's rate; the commission ledger
records clawbacks as negative amounts; settlement, approval-expiry, fixed-rate and review reminders.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.apps.sales import BusinessRuleError, rule
from app.core.clock import local_today
from app.engine.hooks import Change, Event, action, on, ref
from app.engine.records import RecordService
from app.engine.types import decimal_to_json, money, to_decimal
from app.models import Record, RecordShare
from app.packs import Pack, permission_key, register
from app.packs.common import date_reminders, first_of, live
from app.packs.loan_broker import definition as d
from app.services import audit
from app.services.audit import AuditAction
from app.services.settings import get_setting

K = d.KEY
BID_FIELDS = ("customer_objectives", "products_considered", "recommendation_reason")


def _settings(db: Session) -> dict[str, Any]:
    return get_setting(db, K) or {}


def _has(svc: RecordService, perm: str) -> bool:
    return svc.system or svc.policy.has_custom(permission_key(K, perm))


def _get(svc: RecordService, value: Any) -> Record | None:
    rid = ref(value)
    return svc.db.get(Record, rid) if rid else None


def _set(svc: RecordService, record: Record, values: dict[str, Any]) -> None:
    svc.elevated().update(record.object_api_name, record.id, values, record=record)


def _index(stage: Any) -> int:
    return d.STAGE_ORDER.index(stage) if stage in d.STAGE_ORDER else 0


def _lvr(data: dict[str, Any]) -> None:
    loan, security = to_decimal(data.get("loan_amount")), to_decimal(data.get("security_value"))
    lvr = money(loan / security * 100) if loan is not None and security else None
    data["lvr"] = decimal_to_json(lvr) if lvr is not None else None
    # Lenders generally require lenders mortgage insurance above 80% LVR.
    data["lmi_likely"] = bool(lvr is not None and lvr > 80)


def monthly_repayment(amount: Decimal, annual_rate: Decimal, years: Decimal) -> Decimal:
    """Principal and interest repayment per month (standard amortisation)."""
    n = int(years * 12)
    if n <= 0:
        return Decimal(0)
    r = annual_rate / Decimal(1200)
    if r == 0:
        return money(amount / n)
    return money(amount * r / (1 - (1 + r) ** -n))


def _serviceability(db: Session, data: dict[str, Any]) -> None:
    """The assessment rate (product rate + buffer, with a floor) and the repayment at that rate."""
    s = _settings(db)
    rate = to_decimal(data.get("interest_rate"))
    amount, years = to_decimal(data.get("loan_amount")), to_decimal(data.get("term_years"))
    if rate is None or amount is None or not years:
        data["assessment_rate"], data["estimated_repayment"] = None, None
        return
    buffer = Decimal(str(s.get("serviceability_buffer", d.SETTINGS_DEFAULTS["serviceability_buffer"])))
    floor = Decimal(str(s.get("minimum_assessment_rate", d.SETTINGS_DEFAULTS["minimum_assessment_rate"])))
    assessed = max(rate + buffer, floor)
    data["assessment_rate"] = decimal_to_json(money(assessed))
    data["estimated_repayment"] = decimal_to_json(monthly_repayment(amount, assessed, years))


# ------------------------------------------------------------------ loan applications


@on("loan_application", Event.BEFORE_CREATE, pack_key=K)
def loan_defaults(change: Change) -> None:
    data, svc = change.data, change.svc
    if data.get("stage") not in (None, "Enquiry", "Fact Find") and not svc.system:
        raise rule("New applications start at Enquiry or Fact Find.", "stage")
    if not data.get("broker") and svc.user_id and not svc.system:
        data["broker"] = str(svc.user_id)
    data["bid_completed"] = False
    _lvr(data)
    _serviceability(svc.db, data)


@on("loan_application", Event.BEFORE_UPDATE, pack_key=K)
def loan_rules(change: Change) -> None:
    svc, data, old = change.svc, change.data, change.old
    _lvr(data)
    _serviceability(svc.db, data)
    if any(change.is_changed(f) for f in BID_FIELDS) and old.get("bid_completed") and not svc.system:
        raise rule("The Best Interests Duty record is locked once the assessment is recorded.")
    if (
        old.get("stage") in d.FINAL_STAGES
        and change.is_changed("stage")
        and not svc.system
        and not svc.policy.object("loan_application").modify_all  # a principal can correct a mistake
    ):
        raise rule(f"The application is {old.get('stage')}; open a new application instead.", "stage")
    # Choosing the lender (or adding a co-borrower) completes the application; switching them changes it.
    material = [
        f
        for f in ("loan_amount", "purpose", "primary_borrower", "lender", "co_borrower")
        if change.is_changed(f) and (f not in ("lender", "co_borrower") or old.get(f))
    ]
    if (
        material
        and old.get("bid_completed")
        and _index(old.get("stage")) < _index("Lodged")
        and not svc.system
    ):
        # The assessment was for a different loan: it has to be made again before lodging (NCCP, BID).
        data["bid_completed"] = False
        audit.record(
            svc.db,
            action=AuditAction.UPDATE,
            entity_type="record:loan_application",
            entity_id=change.record.id if change.record else None,
            summary=f"Preliminary assessment to be redone: {', '.join(material)} changed",
            actor_id=svc.user_id,
            meta=svc.request_meta,
        )
    if not change.is_changed("stage") or svc.system:
        return
    new_stage = data.get("stage")
    if new_stage == "Declined":
        if not str(data.get("decline_reason") or "").strip():
            raise rule("Record why the application was declined or withdrawn.", "decline_reason")
        return
    new_i, old_i = _index(new_stage), _index(old.get("stage"))
    if new_i <= old_i:
        return
    if new_i >= _index("Preliminary Assessment"):
        if not data.get("credit_guide_date"):
            raise rule(
                "Give the client your credit guide before providing credit assistance.", "credit_guide_date"
            )
        if not data.get("privacy_consent_date"):
            raise rule("Record the client's privacy and credit-check consent.", "privacy_consent_date")
        if (to_decimal(data.get("broker_fee")) or 0) > 0 and not data.get("credit_quote_date"):
            raise rule(
                "A fee is charged to the client: give them a credit quote first (NCCP s 114).",
                "credit_quote_date",
            )
    if new_i >= _index("Lodged") and old_i < _index("Lodged"):
        if not data.get("bid_completed"):
            raise rule("Record the preliminary assessment and Best Interests Duty before lodging.", "stage")
        if not data.get("lender"):
            raise rule("Choose the lender.", "lender")
        if not data.get("credit_proposal_date"):
            raise rule(
                "Give the client the credit proposal disclosure (fees, charges and commissions) before "
                "applying to the lender (NCCP s 121).",
                "credit_proposal_date",
            )
        if not _has(svc, d.SUBMIT):
            raise rule("Lodging with a lender needs the Submit to Lender permission.", "stage")
        data["lodged_date"] = data.get("lodged_date") or local_today().isoformat()
    if new_stage == "Settled":
        if not data.get("lender"):
            raise rule("Choose the lender.", "lender")
        data["settlement_date"] = data.get("settlement_date") or local_today().isoformat()
        if not data.get("rate_review_date"):
            data["rate_review_date"] = (
                date.fromisoformat(data["settlement_date"]) + timedelta(days=365)
            ).isoformat()


@on("loan_application", Event.AFTER_CREATE, Event.AFTER_UPDATE, pack_key=K)
def loan_changed(change: Change) -> None:
    loan = change.record
    assert loan is not None
    if not change.old or change.is_changed("broker") or change.is_changed("processor"):
        _sync_team_shares(change.svc, loan)
    if change.is_changed("stage") and change.data.get("stage") == "Settled":
        _expected_upfront(change.svc, loan)


@on("loan_application", Event.BEFORE_DELETE, pack_key=K)
def loan_retention(change: Change) -> None:
    assert change.record is not None
    assessed = change.record.data.get("preliminary_assessment_date")
    years = int(_settings(change.svc.db).get("bid_retention_years", 7))
    if assessed and date.fromisoformat(assessed) > local_today() - timedelta(days=round(365.25 * years)):
        raise rule(f"Preliminary assessments and BID records must be kept for {years} years.")


def _sync_team_shares(svc: RecordService, loan: Record) -> None:
    svc.db.execute(
        delete(RecordShare).where(RecordShare.record_id == loan.id, RecordShare.created_by_id.is_(None))
    )
    for field in ("broker", "processor"):
        uid = loan.data.get(field)
        if uid:
            svc.db.add(
                RecordShare(
                    record_id=loan.id,
                    principal_type="user",
                    principal_id=uuid.UUID(str(uid)),
                    access="read_write",
                    created_by_id=None,
                )
            )
    svc.db.flush()


def _expected_upfront(svc: RecordService, loan: Record) -> None:
    lender = _get(svc, loan.data.get("lender"))
    rate = to_decimal(lender.data.get("upfront_rate")) if lender else None
    amount = to_decimal(loan.data.get("loan_amount"))
    if not rate or not amount:
        return
    if any(
        c.data.get("type") == "Upfront" for c in live(svc.db, "commission", loan_application=str(loan.id))
    ):
        return
    expected = money(amount * rate / 100)
    svc.elevated().create(
        "commission",
        {
            "loan_application": str(loan.id),
            "type": "Upfront",
            "amount": decimal_to_json(expected),
            "status": "Expected",
            "period": loan.data.get("settlement_date"),
        },
    )
    _set(svc, loan, {"expected_upfront": decimal_to_json(expected)})


@action(
    "loan_application",
    "record_assessment",
    "Record Preliminary Assessment",
    pack_key=K,
    visible=lambda r: not r.data.get("bid_completed"),
)
def record_assessment(svc: RecordService, loan: Record, payload: dict[str, Any]) -> dict[str, Any]:
    """Responsible lending: the assessment that the loan is not unsuitable, plus the BID record."""
    data = loan.data
    missing = {f: "Required" for f in BID_FIELDS if not str(data.get(f) or "").strip()}
    if missing:
        raise BusinessRuleError(
            "Complete the requirements, products considered and recommendation reasons first.", fields=missing
        )
    if not data.get("credit_guide_date") or not data.get("privacy_consent_date"):
        raise rule("Record the credit guide and privacy consent first.", "credit_guide_date")
    fact_finds = sorted(
        (
            f
            for f in live(svc.db, "fact_find", loan_application=str(loan.id))
            if f.data.get("status") == "Complete"
        ),
        key=lambda f: f.updated_at,
    )
    if not fact_finds:
        raise rule("Complete a fact find (income, expenses, assets and liabilities) first.")
    latest = fact_finds[-1]
    if not latest.data.get("expenses_verified"):
        raise rule(
            "Verify the client's income and expenses (payslips, bank statements) on the fact find before "
            "the assessment (NCCP reasonable inquiries and verification).",
        )
    if data.get("interest_rate") is None or not data.get("term_years"):
        raise rule(
            "Enter the product's interest rate and the loan term to assess the repayments.", "interest_rate"
        )
    repayment = to_decimal(data.get("estimated_repayment")) or Decimal(0)
    surplus = to_decimal(latest.data.get("monthly_surplus")) or Decimal(0)
    if repayment > surplus:
        raise rule(
            f"The loan looks unsuitable: repayments of ${repayment:,.2f} a month at the "
            f"{data.get('assessment_rate')}% assessment rate exceed the client's monthly surplus of "
            f"${surplus:,.2f} (NCCP: they could only repay with substantial hardship). If the loan replaces "
            "a debt in their commitments, remove that repayment from the fact find."
        )
    values: dict[str, Any] = {"bid_completed": True, "preliminary_assessment_date": local_today().isoformat()}
    if _index(data.get("stage")) < _index("Preliminary Assessment"):
        values["stage"] = "Preliminary Assessment"
    _set(svc, loan, values)
    audit.record(
        svc.db,
        action=AuditAction.UPDATE,
        entity_type="record:loan_application",
        entity_id=loan.id,
        summary=f"Preliminary assessment and Best Interests Duty recorded for {loan.name}",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    return svc.serialize(loan)


@action(
    "loan_application",
    "record_discharge",
    "Record Discharge",
    pack_key=K,
    visible=lambda r: r.data.get("stage") == "Settled" and not r.data.get("discharged_date"),
)
def record_discharge(svc: RecordService, loan: Record, payload: dict[str, Any]) -> dict[str, Any]:
    """The loan was repaid or refinanced away. Within the lender's clawback period an expected clawback of
    the upfront commission is recorded (half after the lender's halving point, if it has one)."""
    if loan.data.get("stage") != "Settled":
        raise rule("Only settled loans can be discharged.")
    if loan.data.get("discharged_date"):
        raise rule(f"The discharge was recorded on {loan.data['discharged_date']}.")
    when = str(payload.get("discharged_date") or local_today().isoformat())[:10]
    try:
        discharged = date.fromisoformat(when)
    except ValueError as exc:
        raise BusinessRuleError("Enter the discharge date.", fields={"discharged_date": "Invalid"}) from exc
    _set(svc, loan, {"discharged_date": discharged.isoformat()})
    lender = _get(svc, loan.data.get("lender"))
    settled = loan.data.get("settlement_date")
    if lender is None or not settled:
        return {"clawback": None}
    months = (discharged.year - date.fromisoformat(settled).year) * 12 + (
        discharged.month - date.fromisoformat(settled).month
    )
    window = int(to_decimal(lender.data.get("clawback_months")) or 0)
    if months >= window:
        return {"clawback": None}
    upfront = sum(
        (
            to_decimal(c.data.get("amount")) or Decimal(0)
            for c in live(svc.db, "commission", loan_application=str(loan.id))
            if c.data.get("type") == "Upfront"
        ),
        Decimal(0),
    )
    if upfront <= 0:
        return {"clawback": None}
    half = to_decimal(lender.data.get("clawback_half_after"))
    share = Decimal("0.5") if half is not None and months >= int(half) else Decimal(1)
    clawback = svc.elevated().create(
        "commission",
        {
            "loan_application": str(loan.id),
            "type": "Clawback",
            "amount": decimal_to_json(money(upfront * share)),
            "status": "Expected",
            "period": discharged.isoformat(),
            "reference": f"Discharged {discharged.isoformat()}, {months} months after settlement",
        },
    )
    return {"clawback": str(clawback.id), "amount": decimal_to_json(money(upfront * share))}


# ------------------------------------------------------------------ fact finds


@on("fact_find", Event.BEFORE_CREATE, Event.BEFORE_UPDATE, pack_key=K)
def fact_find_totals(change: Change) -> None:
    data = change.data

    def n(field: str) -> Decimal:
        return to_decimal(data.get(field)) or Decimal(0)

    data["net_position"] = decimal_to_json(money(n("total_assets") - n("total_liabilities")))
    monthly_income = (n("gross_annual_income") + n("other_annual_income")) / 12
    data["monthly_surplus"] = decimal_to_json(
        money(monthly_income - n("monthly_living_expenses") - n("monthly_commitments"))
    )
    if data.get("status") == "Complete" and (
        data.get("gross_annual_income") is None or data.get("monthly_living_expenses") is None
    ):
        raise rule("Enter income and living expenses before completing the fact find.", "status")


# ------------------------------------------------------------------ commissions


@on("commission", Event.BEFORE_CREATE, pack_key=K)
def commission_rules(change: Change) -> None:
    svc, data = change.svc, change.data
    if not _has(svc, d.COMMISSIONS):
        raise rule("Recording commission needs the Manage Commissions permission.")
    loan = _get(svc, data.get("loan_application"))
    if loan is None:
        raise rule("Choose the loan application.", "loan_application")
    data["lender"] = loan.data.get("lender")
    data["broker"] = loan.data.get("broker")
    amount = money(to_decimal(data.get("amount")) or 0)
    if amount <= 0:
        raise rule("Enter a positive amount.", "amount")
    data["signed_amount"] = decimal_to_json(-amount if data.get("type") == "Clawback" else amount)
    if data.get("status") == "Received" and not data.get("received_date"):
        data["received_date"] = local_today().isoformat()


@on("commission", Event.AFTER_CREATE, pack_key=K)
def commission_visible_to_broker(change: Change) -> None:
    """A broker reads the commission on their own loans (not to change it: that needs Manage Commissions)."""
    record = change.record
    uid = change.data.get("broker")
    if record is None or not uid:
        return
    change.svc.db.add(
        RecordShare(
            record_id=record.id,
            principal_type="user",
            principal_id=uuid.UUID(str(uid)),
            access="read",
            created_by_id=None,
        )
    )
    change.svc.db.flush()


@on("commission", Event.BEFORE_UPDATE, pack_key=K)
def commission_locked(change: Change) -> None:
    if change.svc.system:
        return
    if not _has(change.svc, d.COMMISSIONS):
        raise rule("Changing commission needs the Manage Commissions permission.")
    locked = {"loan_application", "type", "amount"} & change.changed
    if locked:
        raise rule(
            "Commission amounts can't be changed; record a clawback or a new entry.", sorted(locked)[0]
        )
    if change.data.get("status") == "Received" and not change.data.get("received_date"):
        change.data["received_date"] = local_today().isoformat()


# ------------------------------------------------------------------ reminders


def daily_reminders(db: Session, today: date | None = None) -> int:
    s = _settings(db)
    broker = first_of("broker")
    count = 0
    for field, label, key, default in (
        ("settlement_date", "Settlement", "settlement_reminder_days", [7, 1]),
        ("approval_expiry", "Approval expires", "approval_expiry_reminder_days", [14]),
        ("fixed_rate_expiry", "Fixed rate expires", "fixed_rate_reminder_days", [90, 30]),
        ("rate_review_date", "Rate review", "rate_review_reminder_days", [7]),
    ):
        count += date_reminders(db, [("loan_application", field, label, broker)], s.get(key, default), today)
    return count


PACK = register(
    Pack(
        key=K,
        name="Loan Broker (Australia)",
        version=d.VERSION,
        region="AU",
        description="Loan applications from enquiry to settlement, lender panel, fact finds, commission "
        "ledger (upfront, trail, clawback), NCCP credit guide and Best Interests Duty records, reminders, "
        "broker profiles and reports.",
        bundle=d.bundle,
        install=d.install,
        custom_permissions={d.SUBMIT: "Submit to Lender", d.COMMISSIONS: "Manage Commissions"},
        daily_job=daily_reminders,
        key_dates=(
            ("loan_application", "settlement_date", "Settlement", ("broker", "processor"), []),
            (
                "loan_application",
                "approval_expiry",
                "Approval expires",
                ("broker", "processor"),
                [{"field": "stage", "op": "not_in", "value": ["Settled", "Declined"]}],
            ),
            ("loan_application", "fixed_rate_expiry", "Fixed rate expires", ("broker",), []),
        ),
    )
)

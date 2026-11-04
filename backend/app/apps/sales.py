"""Sales app business logic (plan v3, section 8): person names, lead conversion, opportunity stages,
opportunity products and pricing."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import false, func, select

from app.core.errors import AppError, ConflictError
from app.engine.hooks import Change, Event, action, on, ref
from app.engine.records import RecordService
from app.engine.standard_v1 import STANDARD_PRICE_BOOK_ID
from app.engine.types import decimal_to_json, money, to_decimal
from app.models import Record, RecordLink
from app.services.settings import get_setting


class BusinessRuleError(AppError):
    status_code = 422
    code = "business_rule"


def rule(message: str, field: str | None = None) -> BusinessRuleError:
    return BusinessRuleError(message, fields={field: message} if field else None)


def full_name(data: dict[str, Any]) -> str:
    return " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p).strip()


# ------------------------------------------------------------------ contacts & leads


@on("contact", Event.BEFORE_CREATE, Event.BEFORE_UPDATE)
@on("lead", Event.BEFORE_CREATE, Event.BEFORE_UPDATE)
def person_name(change: Change) -> None:
    if change.record is None or change.is_changed("first_name") or change.is_changed("last_name"):
        name = full_name(change.data)
        if name:
            change.system["name"] = name


@on("lead", Event.BEFORE_UPDATE, Event.BEFORE_DELETE)
def converted_leads_are_read_only(change: Change) -> None:
    if change.old.get("is_converted") and not change.svc.system:
        raise rule("Converted leads can't be changed.")


def _find_duplicates(svc: RecordService, lead: Record) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"accounts": [], "contacts": []}
    company = (lead.data.get("company") or "").strip()
    if company and svc.policy.object("account").read:
        res = svc.query(
            "account",
            filters={"logic": "and", "conditions": [{"field": "name", "op": "equals", "value": company}]},
            limit=5,
            count=False,
        )
        out["accounts"] = [{"id": str(r.id), "name": r.name} for r in res.records]
    email = lead.data.get("email")
    if email and svc.policy.object("contact").read:
        res = svc.query(
            "contact",
            filters={"logic": "and", "conditions": [{"field": "email", "op": "equals", "value": email}]},
            limit=5,
            count=False,
        )
        out["contacts"] = [
            {"id": str(r.id), "name": r.name, "account": r.data.get("account")} for r in res.records
        ]
    return out


_LEAD_TO_CONTACT = {
    "salutation": "salutation", "first_name": "first_name", "last_name": "last_name", "title": "title",
    "email": "email", "phone": "phone", "mobile": "mobile", "address": "mailing_address",
    "lead_source": "lead_source", "email_opt_in": "email_opt_in", "do_not_call": "do_not_call",
    "description": "description",
}  # fmt: skip
_LEAD_TO_ACCOUNT = {
    "industry": "industry", "phone": "phone", "website": "website", "annual_revenue": "annual_revenue",
    "employees": "employees", "address": "billing_address",
}  # fmt: skip


def _mapped(svc: RecordService, lead: Record, target: str, base: dict[str, str]) -> dict[str, Any]:
    values = {dst: lead.data[src] for src, dst in base.items() if lead.data.get(src) is not None}
    field_map: dict[str, str] = (get_setting(svc.db, "lead_conversion") or {}).get("field_map", {})
    target_meta = svc.registry.get(target)
    for src, dst in field_map.items():
        obj, _, fld = dst.partition(".")
        if obj == target and fld in target_meta.fields and lead.data.get(src) is not None:
            values[fld] = lead.data[src]
    return values


def _repoint_activities(svc: RecordService, from_id: uuid.UUID, to_id: uuid.UUID) -> None:
    sys = svc.elevated()
    for obj in ("task", "event", "note", "file"):
        rows = sys.db.scalars(
            select(Record)
            .join(RecordLink, RecordLink.from_record_id == Record.id)
            .where(
                RecordLink.to_record_id == from_id,
                RecordLink.field_api_name == "related_to",
                RecordLink.from_object == obj,
            )
        ).all()
        for r in rows:
            sys.update(obj, r.id, {"related_to": str(to_id)}, record=r)


@action("lead", "convert", "Convert", visible=lambda r: not r.data.get("is_converted"))
def convert_lead(svc: RecordService, lead: Record, payload: dict[str, Any]) -> dict[str, Any]:
    """Create or link an Account and a Contact, optionally an Opportunity; the lead becomes read-only.

    payload: {"check_duplicates": bool, "account_id": uuid?, "contact_id": uuid?, "create_opportunity": bool,
              "opportunity_name": str?, "owner_id": uuid?}
    """
    if lead.data.get("is_converted"):
        raise rule("This lead has already been converted.")
    if payload.get("check_duplicates"):
        return {"duplicates": _find_duplicates(svc, lead)}
    for obj in ("account", "contact"):
        if not svc.policy.object(obj).create and not payload.get(f"{obj}_id"):
            raise rule(f"You need permission to create {obj}s to convert this lead.")
    owner_id = payload.get("owner_id") or lead.owner_id or svc.user_id

    account_id = payload.get("account_id")
    if account_id:
        account = svc.get("account", uuid.UUID(str(account_id)))
    else:
        values = _mapped(svc, lead, "account", _LEAD_TO_ACCOUNT)
        values["name"] = lead.data.get("company") or lead.name
        values["type"] = "Customer" if payload.get("create_opportunity") else "Prospect"
        account = svc.create("account", values, owner_id=owner_id)

    contact_id = payload.get("contact_id")
    if contact_id:
        contact = svc.get("contact", uuid.UUID(str(contact_id)))
        if not contact.data.get("account"):
            svc.update("contact", contact.id, {"account": str(account.id)})
    else:
        values = _mapped(svc, lead, "contact", _LEAD_TO_CONTACT)
        values["account"] = str(account.id)
        contact = svc.create("contact", values, owner_id=owner_id)

    opportunity = None
    if payload.get("create_opportunity"):
        values = _mapped(svc, lead, "opportunity", {"lead_source": "lead_source", "campaign": "campaign"})
        values.update(
            {
                "name": str(payload.get("opportunity_name") or f"{account.name} -").strip(),
                "account": str(account.id),
                "primary_contact": str(contact.id),
                "close_date": (date.today() + timedelta(days=30)).isoformat(),
            }
        )
        opportunity = svc.create("opportunity", values, owner_id=owner_id)

    _repoint_activities(svc, lead.id, contact.id)
    sys = svc.elevated()
    for member in sys.db.scalars(
        select(Record)
        .join(RecordLink, RecordLink.from_record_id == Record.id)
        .where(
            RecordLink.to_record_id == lead.id,
            RecordLink.field_api_name == "lead",
            RecordLink.from_object == "campaign_member",
        )
    ).all():
        if not member.data.get("contact"):
            sys.update("campaign_member", member.id, {"contact": str(contact.id)}, record=member)
    for consent in sys.db.scalars(
        select(Record)
        .join(RecordLink, RecordLink.from_record_id == Record.id)
        .where(
            RecordLink.to_record_id == lead.id,
            RecordLink.field_api_name == "lead",
            RecordLink.from_object == "consent",
        )
    ).all():
        if not consent.data.get("contact"):
            sys.update("consent", consent.id, {"contact": str(contact.id)}, record=consent)
    sys.update(
        "lead",
        lead.id,
        {
            "is_converted": True,
            "status": "Qualified",
            "converted_date": date.today().isoformat(),
            "converted_account": str(account.id),
            "converted_contact": str(contact.id),
            "converted_opportunity": str(opportunity.id) if opportunity else None,
        },
        record=lead,
    )
    return {
        "account_id": str(account.id),
        "contact_id": str(contact.id),
        "opportunity_id": str(opportunity.id) if opportunity else None,
    }


# ------------------------------------------------------------------ opportunities


def _stage_info(svc: RecordService, stage: str | None) -> dict[str, Any]:
    f = svc.registry.get("opportunity").fields["stage"]
    for v in f.picklist_values:
        if v["value"] == stage:
            return v
    return {}


@on("opportunity", Event.BEFORE_CREATE, Event.BEFORE_UPDATE)
def opportunity_stage(change: Change) -> None:
    data = change.data
    old_stage = change.old.get("stage")
    new_stage = data.get("stage")
    if change.record is not None and old_stage != new_stage:
        old_info = _stage_info(change.svc, old_stage)
        if old_info.get("closed") and not change.svc.system:
            raise rule("Closed opportunities can't change stage.", "stage")
    if change.record is None or change.is_changed("stage"):
        info = _stage_info(change.svc, new_stage)
        if not change.is_changed("probability") and "probability" in info:
            data["probability"] = info["probability"]
        if info.get("forecast"):
            data["forecast_category"] = info["forecast"]
        data["is_closed"] = bool(info.get("closed"))
        data["is_won"] = bool(info.get("won"))
        data["closed_date"] = date.today().isoformat() if info.get("closed") else None
    if new_stage == "Closed Lost" and not data.get("loss_reason"):
        raise rule("Choose a loss reason to close this opportunity as lost.", "loss_reason")
    if change.record is not None and data.get("has_products"):
        if change.is_changed("amount") and not change.svc.system:
            raise rule("The amount is the total of the opportunity's products.", "amount")
        if change.is_changed("price_book"):
            raise rule("Remove the products before changing the price book.", "price_book")


def _price_book_id(svc: RecordService, opportunity: Record | None) -> uuid.UUID:
    if opportunity is not None and opportunity.data.get("price_book"):
        return uuid.UUID(str(opportunity.data["price_book"]))
    return STANDARD_PRICE_BOOK_ID


def find_entry(svc: RecordService, price_book_id: uuid.UUID, product_id: uuid.UUID) -> Record | None:
    return svc.db.scalar(
        select(Record).where(
            Record.object_api_name == "price_book_entry",
            Record.is_deleted == false(),
            Record.data["price_book"].astext == str(price_book_id),
            Record.data["product"].astext == str(product_id),
        )
    )


@on("opportunity_product", Event.BEFORE_CREATE, Event.BEFORE_UPDATE)
def opportunity_line(change: Change) -> None:
    svc = change.svc
    data = change.data
    opp = svc.db.get(Record, ref(data.get("opportunity")))
    product = svc.db.get(Record, ref(data.get("product")))
    if product is None:
        raise rule("Choose a product.", "product")
    if change.record is None or change.is_changed("product"):
        if not product.data.get("is_active", True):
            raise rule("This product is inactive.", "product")
        book_id = _price_book_id(svc, opp)
        entry = find_entry(svc, book_id, product.id)
        if entry is None or not entry.data.get("is_active", True):
            raise rule("This product has no active price in the opportunity's price book.", "product")
        data["price_book_entry"] = str(entry.id)
        if data.get("unit_price") is None or not change.is_changed("unit_price"):
            data["unit_price"] = entry.data.get("list_price")
    qty = to_decimal(data.get("quantity")) or Decimal(0)
    price = to_decimal(data.get("unit_price")) or Decimal(0)
    discount = to_decimal(data.get("discount")) or Decimal(0)
    total = money(qty * price - discount)
    if total < 0:
        raise rule("The discount is larger than the line amount.", "discount")
    data["line_total"] = decimal_to_json(total)
    change.system["name"] = product.name


def recompute_opportunity_amount(svc: RecordService, opportunity_id: uuid.UUID) -> None:
    sys = svc.elevated()
    opp = sys.db.get(Record, opportunity_id)
    if opp is None or opp.is_deleted:
        return
    totals = sys.db.execute(
        select(
            func.count(), func.coalesce(func.sum(Record.data["line_total"].astext.cast(sys_numeric())), 0)
        ).where(
            Record.object_api_name == "opportunity_product",
            Record.is_deleted == false(),
            Record.data["opportunity"].astext == str(opportunity_id),
        )
    ).one()
    count, amount = int(totals[0]), Decimal(str(totals[1]))
    values: dict[str, Any] = {"has_products": count > 0}
    if count > 0:
        values["amount"] = decimal_to_json(money(amount))
    if any(opp.data.get(k) != v for k, v in values.items()):
        sys.update("opportunity", opp.id, values, record=opp)


def sys_numeric() -> Any:
    from sqlalchemy import Numeric

    return Numeric


@on("opportunity_product", Event.AFTER_CREATE, Event.AFTER_UPDATE, Event.AFTER_DELETE)
def opportunity_line_rollup(change: Change) -> None:
    opp_id = ref(change.data.get("opportunity") or change.old.get("opportunity"))
    if opp_id is not None:
        recompute_opportunity_amount(change.svc, opp_id)


@on("opportunity", Event.BEFORE_DELETE)
def opportunity_delete(change: Change) -> None:
    if change.old.get("is_won") and not change.svc.policy.is_system_admin and not change.svc.system:
        raise rule("Won opportunities can only be deleted by an administrator.")


@action("opportunity", "mark_stage", "Mark Stage", visible=lambda r: not r.data.get("is_closed"))
def mark_stage(svc: RecordService, opp: Record, payload: dict[str, Any]) -> dict[str, Any]:
    """Path "Mark as current stage": payload {"stage": value, "loss_reason"?}."""
    stage = payload.get("stage")
    values: dict[str, Any] = {"stage": stage}
    if payload.get("loss_reason"):
        values["loss_reason"] = payload["loss_reason"]
    svc.update("opportunity", opp.id, values, record=opp)
    return svc.serialize(opp)


def stamp_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def ensure_unique(
    svc: RecordService, obj: str, conditions: dict[str, str], exclude: uuid.UUID | None, message: str
) -> None:
    stmt = select(Record.id).where(Record.object_api_name == obj, Record.is_deleted == false())
    for k, v in conditions.items():
        stmt = stmt.where(Record.data[k].astext == v)
    if exclude is not None:
        stmt = stmt.where(Record.id != exclude)
    if svc.db.scalar(stmt.limit(1)) is not None:
        raise ConflictError(message)

"""Billing app business logic (plan v3, section 8): price books, quotes, invoices, payments, tax.

Money: line = quantity x unit price - discount; tax per line from its tax rate; every amount is rounded
half-up to the cent. Issued invoices are locked; payments move them to Partially Paid / Paid; voiding
needs a reason; over-payment is refused.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import false, select

from app.apps.sales import BusinessRuleError, ensure_unique, find_entry, rule
from app.core.clock import local_today
from app.engine.hooks import Change, Event, action, on, ref
from app.engine.records import RecordService, format_number
from app.engine.standard_v1 import GST_TAX_RATE_ID, STANDARD_PRICE_BOOK_ID
from app.engine.types import decimal_to_json, money, to_decimal
from app.models import Record
from app.services.settings import get_setting

OPEN_INVOICE = ("Issued", "Partially Paid")


def _num(value: Any) -> Decimal:
    return to_decimal(value) or Decimal(0)


def _children(svc: RecordService, obj: str, field: str, parent_id: uuid.UUID) -> list[Record]:
    return list(
        svc.db.scalars(
            select(Record).where(
                Record.object_api_name == obj,
                Record.is_deleted == false(),
                Record.data[field].astext == str(parent_id),
            )
        )
    )


def default_tax_rate(svc: RecordService) -> Record | None:
    rec = svc.db.scalar(
        select(Record)
        .where(
            Record.object_api_name == "tax_rate",
            Record.is_deleted == false(),
            Record.data["is_default"].astext == "true",
        )
        .limit(1)
    )
    return rec or svc.db.get(Record, GST_TAX_RATE_ID)


# ------------------------------------------------------------------ products & price books


@on("product", Event.BEFORE_CREATE)
def product_defaults(change: Change) -> None:
    if change.data.get("standard_price") is None:
        change.data["standard_price"] = 0


@on("product", Event.AFTER_CREATE)
def product_standard_entry(change: Change) -> None:
    """Every product has a standard price-book entry."""
    assert change.record is not None
    sys = change.svc.elevated()
    sys.create(
        "price_book_entry",
        {
            "price_book": str(STANDARD_PRICE_BOOK_ID),
            "product": str(change.record.id),
            "list_price": change.data.get("standard_price") or 0,
            "is_active": True,
        },
    )


@on("product", Event.AFTER_UPDATE)
def product_price_sync(change: Change) -> None:
    assert change.record is not None
    if not change.is_changed("standard_price"):
        return
    entry = find_entry(change.svc, STANDARD_PRICE_BOOK_ID, change.record.id)
    if entry is not None and entry.data.get("list_price") != change.data.get("standard_price"):
        change.svc.elevated().update(
            "price_book_entry", entry.id, {"list_price": change.data.get("standard_price")}, record=entry
        )


@on("price_book_entry", Event.BEFORE_CREATE, Event.BEFORE_UPDATE)
def entry_rules(change: Change) -> None:
    svc = change.svc
    book_id, product_id = ref(change.data.get("price_book")), ref(change.data.get("product"))
    if book_id is None or product_id is None:
        return
    ensure_unique(
        svc,
        "price_book_entry",
        {"price_book": str(book_id), "product": str(product_id)},
        change.record.id if change.record else None,
        "This product already has a price in this price book.",
    )
    if book_id != STANDARD_PRICE_BOOK_ID and find_entry(svc, STANDARD_PRICE_BOOK_ID, product_id) is None:
        raise rule("Add the product to the standard price book first.", "product")
    product = svc.db.get(Record, product_id)
    book = svc.db.get(Record, book_id)
    if product is not None and book is not None:
        change.system["name"] = f"{product.name} - {book.name}"


@on("price_book_entry", Event.AFTER_UPDATE)
def entry_price_sync(change: Change) -> None:
    if ref(change.data.get("price_book")) != STANDARD_PRICE_BOOK_ID or not change.is_changed("list_price"):
        return
    product = change.svc.db.get(Record, ref(change.data.get("product")))
    if product is not None and product.data.get("standard_price") != change.data.get("list_price"):
        change.svc.elevated().update(
            "product", product.id, {"standard_price": change.data.get("list_price")}, record=product
        )


@on("price_book", Event.BEFORE_DELETE)
@on("price_book_entry", Event.BEFORE_DELETE)
def protect_standard_book(change: Change) -> None:
    rec = change.record
    assert rec is not None
    if rec.id == STANDARD_PRICE_BOOK_ID or (
        rec.object_api_name == "price_book_entry"
        and ref(rec.data.get("price_book")) == STANDARD_PRICE_BOOK_ID
        and not change.svc.system
    ):
        raise rule("The standard price book and its entries can't be deleted; deactivate them instead.")


@on("tax_rate", Event.AFTER_CREATE, Event.AFTER_UPDATE)
def single_default_tax(change: Change) -> None:
    if not change.data.get("is_default") or not change.is_changed("is_default"):
        return
    assert change.record is not None
    sys = change.svc.elevated()
    for other in sys.db.scalars(
        select(Record).where(
            Record.object_api_name == "tax_rate",
            Record.id != change.record.id,
            Record.data["is_default"].astext == "true",
        )
    ):
        sys.update("tax_rate", other.id, {"is_default": False}, record=other)


# ------------------------------------------------------------------ lines (quotes and invoices)


def _line_parent(svc: RecordService, change: Change, parent_field: str) -> Record:
    parent = svc.db.get(Record, ref(change.data.get(parent_field) or change.old.get(parent_field)))
    if parent is None:
        raise rule("Choose the parent record.", parent_field)
    return parent


def price_line(
    svc: RecordService, data: dict[str, Any], *, price_book_id: uuid.UUID | None, changed: set[str]
) -> str:
    """Fill in unit price / tax rate from the product, compute line totals. Returns the line's name."""
    product = svc.db.get(Record, ref(data.get("product"))) if data.get("product") else None
    if product is not None:
        if "product" in changed and not product.data.get("is_active", True):
            raise rule("This product is inactive.", "product")
        if data.get("unit_price") is None:
            entry = find_entry(svc, price_book_id or STANDARD_PRICE_BOOK_ID, product.id)
            if entry is None and price_book_id not in (None, STANDARD_PRICE_BOOK_ID):
                entry = find_entry(svc, STANDARD_PRICE_BOOK_ID, product.id)
            if entry is None:
                raise rule("This product has no price; enter a unit price.", "unit_price")
            data["unit_price"] = entry.data.get("list_price")
        if not data.get("tax_rate") and product.data.get("tax_rate"):
            data["tax_rate"] = product.data["tax_rate"]
        if not data.get("description"):
            data["description"] = product.name
    if data.get("unit_price") is None:
        raise rule("Enter a unit price.", "unit_price")
    if not data.get("tax_rate"):
        default = default_tax_rate(svc)
        if default is not None:
            data["tax_rate"] = str(default.id)
    qty, price, discount = (
        _num(data.get("quantity")),
        _num(data.get("unit_price")),
        _num(data.get("discount")),
    )
    if qty < 0:
        raise rule("Quantity can't be negative.", "quantity")
    gross = money(qty * price)
    net = money(gross - discount)
    if net < 0:
        raise rule("The discount is larger than the line amount.", "discount")
    rate = Decimal(0)
    if data.get("tax_rate"):
        tax = svc.db.get(Record, ref(data["tax_rate"]))
        rate = _num(tax.data.get("rate")) if tax is not None else Decimal(0)
    data["line_total"] = decimal_to_json(net)
    data["tax_amount"] = decimal_to_json(money(net * rate / 100))
    return str(data.get("description") or (product.name if product else "Line"))[:255]


def recompute_totals(svc: RecordService, parent: Record, line_object: str, parent_field: str) -> None:
    lines = _children(svc, line_object, parent_field, parent.id)
    subtotal = sum(
        (money(_num(line.data.get("quantity")) * _num(line.data.get("unit_price"))) for line in lines),
        Decimal(0),
    )
    discount = sum((_num(line.data.get("discount")) for line in lines), Decimal(0))
    tax = sum((_num(line.data.get("tax_amount")) for line in lines), Decimal(0))
    total = money(subtotal - discount + tax)
    values: dict[str, Any] = {
        "subtotal": decimal_to_json(money(subtotal)),
        "discount_total": decimal_to_json(money(discount)),
        "tax_total": decimal_to_json(money(tax)),
        "total": decimal_to_json(total),
    }
    if parent.object_api_name == "invoice":
        paid = _paid(svc, parent.id)
        values["amount_paid"] = decimal_to_json(paid)
        values["balance"] = decimal_to_json(money(total - paid))
    if any(parent.data.get(k) != v for k, v in values.items()):
        svc.elevated().update(parent.object_api_name, parent.id, values, record=parent)


def _paid(svc: RecordService, invoice_id: uuid.UUID) -> Decimal:
    return money(
        sum(
            (
                _num(p.data.get("amount"))
                for p in _children(svc, "payment", "invoice", invoice_id)
                if p.data.get("status", "Received") == "Received"
            ),
            Decimal(0),
        )
    )


@on("quote_line", Event.BEFORE_CREATE, Event.BEFORE_UPDATE, Event.BEFORE_DELETE)
def quote_line_rules(change: Change) -> None:
    quote = _line_parent(change.svc, change, "quote")
    if quote.data.get("status") in ("Accepted", "Rejected") and not change.svc.system:
        raise rule("Lines of accepted or rejected quotes can't be changed.")
    if change.record is not None and change.data == change.old:
        return
    if change.old and not change.data.get("quote"):
        return
    book = ref(quote.data.get("price_book"))
    change.system["name"] = price_line(
        change.svc,
        change.data,
        price_book_id=book,
        changed=change.changed if change.record else set(change.data),
    )


@on("invoice_line", Event.BEFORE_CREATE, Event.BEFORE_UPDATE, Event.BEFORE_DELETE)
def invoice_line_rules(change: Change) -> None:
    invoice = _line_parent(change.svc, change, "invoice")
    if invoice.data.get("status", "Draft") != "Draft" and not change.svc.system:
        raise rule("Lines of issued invoices are locked.")
    if change.record is not None and change.data == change.old:
        return
    change.system["name"] = price_line(
        change.svc,
        change.data,
        price_book_id=None,
        changed=change.changed if change.record else set(change.data),
    )


@on("quote_line", Event.AFTER_CREATE, Event.AFTER_UPDATE, Event.AFTER_DELETE)
def quote_line_rollup(change: Change) -> None:
    quote = change.svc.db.get(Record, ref(change.data.get("quote") or change.old.get("quote")))
    if quote is not None and not quote.is_deleted:
        recompute_totals(change.svc, quote, "quote_line", "quote")


@on("invoice_line", Event.AFTER_CREATE, Event.AFTER_UPDATE, Event.AFTER_DELETE)
def invoice_line_rollup(change: Change) -> None:
    invoice = change.svc.db.get(Record, ref(change.data.get("invoice") or change.old.get("invoice")))
    if invoice is not None and not invoice.is_deleted:
        recompute_totals(change.svc, invoice, "invoice_line", "invoice")


# ------------------------------------------------------------------ quotes


@on("quote", Event.BEFORE_CREATE)
def quote_defaults(change: Change) -> None:
    data = change.data
    if not data.get("account") and data.get("opportunity"):
        opp = change.svc.db.get(Record, ref(data["opportunity"]))
        if opp is not None:
            data["account"] = opp.data.get("account")
            data.setdefault("contact", opp.data.get("primary_contact"))
            data.setdefault("price_book", opp.data.get("price_book"))
    if not data.get("expiry_date"):
        data["expiry_date"] = (local_today() + timedelta(days=30)).isoformat()
    for k in ("subtotal", "discount_total", "tax_total", "total"):
        data.setdefault(k, 0)


@on("quote", Event.BEFORE_UPDATE)
def quote_rules(change: Change) -> None:
    old = change.old.get("status")
    new = change.data.get("status")
    if old in ("Accepted", "Rejected") and new != old and not change.svc.system:
        raise rule("Accepted and rejected quotes are final.", "status")
    if change.is_changed("price_book") and _children(
        change.svc, "quote_line", "quote", change.record.id if change.record else uuid.uuid4()
    ):
        raise rule("Remove the lines before changing the price book.", "price_book")


@action(
    "quote",
    "create_invoice",
    "Create Invoice",
    visible=lambda r: r.data.get("status") == "Accepted" and not r.data.get("invoice"),
)
def create_invoice_from_quote(svc: RecordService, quote: Record, payload: dict[str, Any]) -> dict[str, Any]:
    if quote.data.get("status") != "Accepted":
        raise rule("Only accepted quotes can be invoiced.")
    if quote.data.get("invoice"):
        raise rule("This quote has already been invoiced.")
    invoice = svc.create(
        "invoice",
        {
            "account": quote.data.get("account"),
            "contact": quote.data.get("contact"),
            "opportunity": quote.data.get("opportunity"),
            "notes": quote.data.get("terms"),
        },
    )
    sys = svc.elevated()
    sys.update("invoice", invoice.id, {"quote": str(quote.id)}, record=invoice)
    lines = sorted(
        _children(svc, "quote_line", "quote", quote.id),
        key=lambda r: (_num(r.data.get("sort_order")), r.created_at),
    )
    for i, line in enumerate(lines, start=1):
        svc.create(
            "invoice_line",
            {
                "invoice": str(invoice.id),
                **{
                    k: line.data.get(k)
                    for k in ("product", "description", "quantity", "unit_price", "discount", "tax_rate")
                    if line.data.get(k) is not None
                },
                "sort_order": i,
            },
        )
    sys.update("quote", quote.id, {"invoice": str(invoice.id)}, record=quote)
    return {"invoice_id": str(invoice.id)}


# ------------------------------------------------------------------ invoices


def billing_account_for(svc: RecordService, contact: Record) -> Record:
    """The organisation an individual client is billed through: theirs, or one created in their name
    and linked to them (so every later invoice uses the same one, not a duplicate)."""
    account = svc.db.get(Record, ref(contact.data.get("account"))) if contact.data.get("account") else None
    if account is not None and not account.is_deleted:
        return account
    sys = svc.elevated()
    account = sys.create("account", {"name": contact.name, "type": "Customer"})
    sys.update("contact", contact.id, {"account": str(account.id)}, record=contact)
    return account


# Profession records an invoice can be raised from, and the field holding their client.
_BILLED_FROM = (("legal_matter", "client"), ("matter", "client"), ("engagement", "contact"))


@on("invoice", Event.BEFORE_CREATE)
def invoice_defaults(change: Change) -> None:
    data = change.data
    if not data.get("account"):
        # An individual (no organisation): bill the client named on the invoice or its matter.
        contact = change.svc.db.get(Record, ref(data.get("contact"))) if data.get("contact") else None
        for field, client_field in _BILLED_FROM:
            if contact is None and data.get(field):
                parent = change.svc.db.get(Record, ref(data[field]))
                client = parent.data.get(client_field) if parent is not None else None
                contact = change.svc.db.get(Record, ref(client)) if client else None
        if contact is not None and contact.object_api_name == "contact" and not contact.is_deleted:
            data["account"] = str(billing_account_for(change.svc, contact).id)
            data.setdefault("contact", str(contact.id))
        else:
            raise rule("Choose who the invoice is for: a client or an organisation.", "account")
    billing = get_setting(change.svc.db, "billing")
    data["status"] = "Draft"
    data.setdefault("payment_terms_days", billing.get("payment_terms_days", 14))
    for k in ("subtotal", "discount_total", "tax_total", "total", "amount_paid", "balance"):
        data[k] = 0
    account = change.svc.db.get(Record, ref(data.get("account")))
    change.system["name"] = f"Draft - {account.name if account else 'invoice'}"[:255]


INVOICE_ALWAYS_EDITABLE = {"notes", "contact"}


@on("invoice", Event.BEFORE_UPDATE)
def invoice_lock(change: Change) -> None:
    if change.svc.system:
        return
    if change.old.get("status", "Draft") != "Draft":
        locked = {f for f in change.changed if f not in INVOICE_ALWAYS_EDITABLE}
        if locked:
            raise rule("Issued invoices can't be changed; void and re-issue instead.")
    if change.is_changed("account") and change.record is not None:
        account = change.svc.db.get(Record, ref(change.data.get("account")))
        if account is not None:
            change.system["name"] = f"Draft - {account.name}"[:255]


@on("invoice", Event.BEFORE_DELETE)
def invoice_delete(change: Change) -> None:
    if change.old.get("status", "Draft") != "Draft":
        raise rule("Issued invoices can't be deleted; void them instead.")


@action("invoice", "issue", "Issue Invoice", visible=lambda r: r.data.get("status", "Draft") == "Draft")
def issue_invoice(svc: RecordService, invoice: Record, payload: dict[str, Any]) -> dict[str, Any]:
    if invoice.data.get("status", "Draft") != "Draft":
        raise rule("Only draft invoices can be issued.")
    if not _children(svc, "invoice_line", "invoice", invoice.id):
        raise rule("Add at least one line before issuing.")
    billing = get_setting(svc.db, "billing")
    company = get_setting(svc.db, "company") or {}
    if billing.get("gst_registered", True) and not str(company.get("abn") or "").strip():
        # A tax invoice must show the supplier's ABN (GST law); without it the client can't claim the GST
        # credit and may have to withhold tax from the payment.
        raise rule("Add the practice's ABN in Setup → Company before issuing tax invoices.")
    prefix = str(billing.get("invoice_prefix") or "INV-")
    digits = int(billing.get("invoice_number_digits") or 6)
    number = format_number(svc.db, "invoice_number", prefix + "{" + "0" * digits + "}")
    issue_date = (
        date.fromisoformat(invoice.data["issue_date"]) if invoice.data.get("issue_date") else local_today()
    )
    terms = int(_num(invoice.data.get("payment_terms_days")) or billing.get("payment_terms_days", 14))
    due = invoice.data.get("due_date") or (issue_date + timedelta(days=terms)).isoformat()
    sys = svc.elevated()
    sys.update(
        "invoice",
        invoice.id,
        {
            "status": "Issued",
            "invoice_number": number,
            "issue_date": issue_date.isoformat(),
            "due_date": due,
        },
        record=invoice,
    )
    invoice.name = number
    recompute_totals(svc, invoice, "invoice_line", "invoice")
    return svc.serialize(invoice)


@action("invoice", "void", "Void Invoice", visible=lambda r: r.data.get("status") in OPEN_INVOICE)
def void_invoice(svc: RecordService, invoice: Record, payload: dict[str, Any]) -> dict[str, Any]:
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise BusinessRuleError("Enter the reason for voiding.", fields={"reason": "Required"})
    if invoice.data.get("status") not in OPEN_INVOICE:
        raise rule("Only issued, unpaid invoices can be voided.")
    if _paid(svc, invoice.id) > 0:
        raise rule("Reverse the invoice's payments before voiding it.")
    svc.elevated().update(
        "invoice", invoice.id, {"status": "Void", "void_reason": reason[:4000], "balance": 0}, record=invoice
    )
    return svc.serialize(invoice)


# ------------------------------------------------------------------ payments


def refresh_invoice_payments(svc: RecordService, invoice: Record) -> None:
    total = _num(invoice.data.get("total"))
    paid = _paid(svc, invoice.id)
    status = invoice.data.get("status")
    if status in ("Issued", "Partially Paid", "Paid"):
        status = "Paid" if paid >= total and total > 0 else ("Partially Paid" if paid > 0 else "Issued")
    svc.elevated().update(
        "invoice",
        invoice.id,
        {
            "amount_paid": decimal_to_json(paid),
            "balance": decimal_to_json(money(total - paid)),
            "status": status,
        },
        record=invoice,
    )


@on("payment", Event.BEFORE_CREATE)
def payment_rules(change: Change) -> None:
    svc = change.svc
    invoice = svc.db.get(Record, ref(change.data.get("invoice")))
    if invoice is None:
        raise rule("Choose an invoice.", "invoice")
    # Lock the invoice row so concurrent payments can't over-pay it.
    svc.db.refresh(invoice, with_for_update=True)
    if invoice.data.get("status") not in OPEN_INVOICE:
        raise rule("Payments can only be recorded against issued, unpaid invoices.", "invoice")
    amount = _num(change.data.get("amount"))
    balance = money(_num(invoice.data.get("total")) - _paid(svc, invoice.id))
    if amount <= 0:
        raise rule("Enter a positive amount.", "amount")
    if amount > balance:
        raise rule(f"The payment is more than the balance due ({balance}).", "amount")
    change.data["status"] = "Received"


@on("payment", Event.AFTER_CREATE)
def payment_applied(change: Change) -> None:
    invoice = change.svc.db.get(Record, ref(change.data.get("invoice")))
    if invoice is not None:
        refresh_invoice_payments(change.svc, invoice)


@on("payment", Event.BEFORE_UPDATE, Event.BEFORE_DELETE)
def payments_are_immutable(change: Change) -> None:
    if change.svc.system:
        return
    if change.record is not None and change.changed - {"reference"}:
        raise rule("Payments can't be changed; reverse the payment instead.")


@action(
    "payment", "reverse", "Reverse Payment", visible=lambda r: r.data.get("status", "Received") == "Received"
)
def reverse_payment(svc: RecordService, payment: Record, payload: dict[str, Any]) -> dict[str, Any]:
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise BusinessRuleError("Enter the reason for the reversal.", fields={"reason": "Required"})
    if payment.data.get("status") == "Reversed":
        raise rule("This payment has already been reversed.")
    sys = svc.elevated()
    sys.update(
        "payment", payment.id, {"status": "Reversed", "reversal_reason": reason[:4000]}, record=payment
    )
    invoice = svc.db.get(Record, ref(payment.data.get("invoice")))
    if invoice is not None:
        refresh_invoice_payments(svc, invoice)
    return svc.serialize(payment)

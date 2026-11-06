"""Standard objects, apps and list views, version 1 (plan v3, sections 5, 6 and 10).

FROZEN once released: applied by a migration through the installer (idempotent; admin changes are kept).
Ship changes as standard_v2 plus a new migration.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import Connection, text

from app.engine.installer import (
    install_bundle,
    install_field_security,
    install_link,
    install_record,
    set_setting,
    stable_id,
)
from app.security.seed_v1 import stable_id as security_id

ACTIVITY_TARGETS: Final = ["*"]  # resolved to every object with activities enabled


def F(api: str, label: str, type_: str, **kw: Any) -> dict[str, Any]:
    field: dict[str, Any] = {"api_name": api, "label": label, "type": type_}
    options = kw.pop("options", {})
    for key in ("max_length", "scale", "min", "max", "target", "targets", "delete_rule", "is_path", "filter"):
        if key in kw:
            options[key] = kw.pop(key)
    if "values" in kw:
        options["values"] = _values(kw.pop("values"), kw.pop("default", None))
    field["options"] = options
    field.update(kw)
    return field


def _values(values: list[Any], default: str | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for v in values:
        item = dict(v) if isinstance(v, dict) else {"value": v, "label": v}
        item.setdefault("active", True)
        if default is not None and item["value"] == default:
            item["default"] = True
        out.append(item)
    return out


def P(value: str, color: str, **extra: Any) -> dict[str, Any]:
    return {"value": value, "label": value, "color": color, **extra}


def section(label: str, fields: list[str], columns: int = 2) -> dict[str, Any]:
    return {"label": label, "columns": columns, "fields": fields}


def related(obj: str, field: str, label: str, columns: list[str]) -> dict[str, Any]:
    return {"object": obj, "field": field, "label": label, "columns": columns}


SYSTEM_SECTION = section("System Information", ["created_by_id", "created_at", "updated_by_id", "updated_at"])

SALUTATIONS = ["Mr.", "Ms.", "Mrs.", "Mx.", "Dr.", "Prof."]
LEAD_SOURCES = [
    "Web",
    "Phone Inquiry",
    "Partner Referral",
    "Purchased List",
    "Event",
    "Advertisement",
    "Social Media",
    "Other",
]
INDUSTRIES = [
    "Agriculture", "Construction", "Education", "Finance", "Government", "Healthcare", "Hospitality",
    "Manufacturing", "Media", "Not For Profit", "Professional Services", "Retail", "Technology", "Transport", "Other",
]  # fmt: skip
STAGES = [
    P("Prospecting", "#94a3b8", probability=10, forecast="Pipeline"),
    P("Qualification", "#60a5fa", probability=20, forecast="Pipeline"),
    P("Needs Analysis", "#38bdf8", probability=40, forecast="Pipeline"),
    P("Proposal", "#a78bfa", probability=60, forecast="Best Case"),
    P("Negotiation", "#f59e0b", probability=80, forecast="Commit"),
    P("Closed Won", "#16a34a", probability=100, forecast="Closed", closed=True, won=True),
    P("Closed Lost", "#dc2626", probability=0, forecast="Omitted", closed=True, won=False),
]
LINE_COLUMNS = ["product", "quantity", "unit_price", "discount", "line_total"]

ACCOUNT: Final[dict[str, Any]] = {
    "api_name": "account", "label": "Account", "plural_label": "Accounts", "icon": "account", "color": "#5867e8",
    "sharing": "read",
    "fields": [
        F("type", "Type", "picklist", values=["Prospect", "Customer", "Partner", "Vendor", "Other"]),
        F("industry", "Industry", "picklist", values=INDUSTRIES),
        F("phone", "Phone", "phone", searchable=True),
        F("website", "Website", "url"),
        F("email", "E-mail", "email", searchable=True),
        F("abn", "ABN / Tax ID", "text", max_length=20, searchable=True, indexed=True),
        F("annual_revenue", "Annual Revenue", "currency"),
        F("employees", "Employees", "number"),
        F("parent_account", "Parent Account", "lookup", target="account", delete_rule="clear"),
        F("billing_address", "Billing Address", "address"),
        F("shipping_address", "Shipping Address", "address"),
        F("description", "Description", "long_text"),
    ],
    "page_layout": [
        section("Account Information", ["name", "type", "industry", "phone", "email", "website", "abn", "parent_account", "owner_id"]),
        section("Financials", ["annual_revenue", "employees"]),
        section("Address Information", ["billing_address", "shipping_address"]),
        section("Description", ["description"], 1),
        SYSTEM_SECTION,
    ],
    "compact_layout": ["type", "industry", "phone", "website", "owner_id"],
    "list_columns": ["name", "type", "industry", "phone", "owner_id"],
    "related_lists": [
        related("contact", "account", "Contacts", ["name", "title", "email", "phone"]),
        related("opportunity", "account", "Opportunities", ["name", "stage", "amount", "close_date"]),
        related("case", "account", "Cases", ["name", "subject", "status", "priority"]),
        related("quote", "account", "Quotes", ["name", "status", "total", "expiry_date"]),
        related("invoice", "account", "Invoices", ["name", "status", "total", "balance", "due_date"]),
        related("account", "parent_account", "Child Accounts", ["name", "type", "phone"]),
    ],
}  # fmt: skip

CONTACT: Final[dict[str, Any]] = {
    "api_name": "contact", "label": "Contact", "plural_label": "Contacts", "icon": "contact", "color": "#8b5cf6",
    "sharing": "read", "show_in_portal": True,
    "fields": [
        F("salutation", "Salutation", "picklist", values=SALUTATIONS),
        F("first_name", "First Name", "text", max_length=80, searchable=True),
        F("last_name", "Last Name", "text", max_length=80, required=True, searchable=True),
        F("account", "Account", "lookup", target="account", delete_rule="clear", track_history=True),
        F("title", "Title", "text", max_length=128),
        F("department", "Department", "text", max_length=80),
        F("email", "E-mail", "email", searchable=True, indexed=True, track_history=True),
        F("phone", "Landline / Office Phone", "phone", searchable=True),
        F("mobile", "Mobile Number", "phone", searchable=True),
        F("mailing_address", "Mailing Address", "address"),
        F("birthdate", "Birthdate", "date"),
        F("lead_source", "Lead Source", "picklist", values=LEAD_SOURCES),
        F("reports_to", "Reports To", "lookup", target="contact", delete_rule="clear"),
        F("email_opt_in", "E-mail Opt-in", "checkbox", default_value=False, track_history=True),
        F("do_not_call", "Do Not Call", "checkbox", default_value=False),
        F("email_bounced", "E-mail Bounced", "checkbox", default_value=False, is_readonly=True),
        F("description", "Description", "long_text"),
    ],
    "page_layout": [
        section("Contact Information", ["salutation", "first_name", "last_name", "account", "title", "department", "reports_to", "owner_id"]),
        section("Contact Details", ["email", "phone", "mobile", "birthdate", "lead_source"]),
        section("Preferences", ["email_opt_in", "do_not_call", "email_bounced"]),
        section("Address Information", ["mailing_address"]),
        section("Description", ["description"], 1),
        SYSTEM_SECTION,
    ],
    "compact_layout": ["title", "account", "email", "phone", "owner_id"],
    "list_columns": ["name", "account", "title", "email", "phone", "owner_id"],
    "related_lists": [
        related("opportunity", "primary_contact", "Opportunities", ["name", "stage", "amount", "close_date"]),
        related("case", "contact", "Cases", ["name", "subject", "status", "priority"]),
        related("campaign_member", "contact", "Campaign History", ["campaign", "status"]),
        related("consent", "contact", "Consent", ["channel", "status", "source", "captured_at"]),
        related("invoice", "contact", "Invoices", ["name", "status", "total", "due_date"]),
    ],
}  # fmt: skip

LEAD: Final[dict[str, Any]] = {
    "api_name": "lead", "label": "Lead", "plural_label": "Leads", "icon": "lead", "color": "#f97316",
    "sharing": "private", "allow_queues": True,
    "fields": [
        F("salutation", "Salutation", "picklist", values=SALUTATIONS),
        F("first_name", "First Name", "text", max_length=80, searchable=True),
        F("last_name", "Last Name", "text", max_length=80, required=True, searchable=True),
        F("company", "Company", "text", max_length=255, required=True, searchable=True),
        F("title", "Title", "text", max_length=128),
        F("email", "E-mail", "email", searchable=True, indexed=True),
        F("phone", "Landline / Office Phone", "phone", searchable=True),
        F("mobile", "Mobile Number", "phone"),
        F("website", "Website", "url"),
        F("address", "Address", "address"),
        F("lead_source", "Lead Source", "picklist", values=LEAD_SOURCES, indexed=True),
        F("status", "Status", "picklist", is_path=True, track_history=True, indexed=True, values=[
            P("New", "#94a3b8"), P("Contacted", "#60a5fa"), P("Nurturing", "#a78bfa"),
            P("Qualified", "#16a34a", closed=True), P("Unqualified", "#dc2626", closed=True),
        ], default="New"),
        F("rating", "Rating", "picklist", values=[P("Hot", "#dc2626"), P("Warm", "#f59e0b"), P("Cold", "#60a5fa")]),
        F("industry", "Industry", "picklist", values=INDUSTRIES),
        F("annual_revenue", "Annual Revenue", "currency"),
        F("employees", "Employees", "number"),
        F("campaign", "Campaign", "lookup", target="campaign", delete_rule="clear"),
        F("email_opt_in", "E-mail Opt-in", "checkbox", default_value=False),
        F("do_not_call", "Do Not Call", "checkbox", default_value=False),
        F("email_bounced", "E-mail Bounced", "checkbox", default_value=False, is_readonly=True),
        F("description", "Description", "long_text"),
        F("is_converted", "Converted", "checkbox", default_value=False, is_readonly=True, default_access="read"),
        F("converted_date", "Converted Date", "date", is_readonly=True, default_access="read"),
        F("converted_account", "Converted Account", "lookup", target="account", is_readonly=True, default_access="read"),
        F("converted_contact", "Converted Contact", "lookup", target="contact", is_readonly=True, default_access="read"),
        F("converted_opportunity", "Converted Opportunity", "lookup", target="opportunity", is_readonly=True, default_access="read"),
    ],
    "page_layout": [
        section("Lead Information", ["salutation", "first_name", "last_name", "company", "title", "status", "rating", "lead_source", "campaign", "owner_id"]),
        section("Contact Details", ["email", "phone", "mobile", "website"]),
        section("Company", ["industry", "annual_revenue", "employees"]),
        section("Preferences", ["email_opt_in", "do_not_call", "email_bounced"]),
        section("Address Information", ["address"]),
        section("Description", ["description"], 1),
        section("Conversion", ["is_converted", "converted_date", "converted_account", "converted_contact", "converted_opportunity"]),
        SYSTEM_SECTION,
    ],
    "compact_layout": ["company", "title", "status", "email", "phone", "owner_id"],
    "list_columns": ["name", "company", "status", "lead_source", "email", "owner_id"],
    "related_lists": [
        related("campaign_member", "lead", "Campaign History", ["campaign", "status"]),
        related("consent", "lead", "Consent", ["channel", "status", "source", "captured_at"]),
    ],
}  # fmt: skip

OPPORTUNITY: Final[dict[str, Any]] = {
    "api_name": "opportunity", "label": "Opportunity", "plural_label": "Opportunities", "icon": "opportunity",
    "color": "#f59e0b", "sharing": "private",
    "fields": [
        F("account", "Account", "lookup", target="account", delete_rule="restrict", required=True, indexed=True),
        F("primary_contact", "Primary Contact", "lookup", target="contact", delete_rule="clear"),
        F("stage", "Stage", "picklist", is_path=True, track_history=True, indexed=True, values=STAGES, default="Prospecting"),
        F("probability", "Probability (%)", "percent", scale=0, min=0, max=100),
        F("amount", "Amount", "currency", track_history=True),
        F("close_date", "Close Date", "date", required=True, track_history=True, indexed=True),
        F("type", "Type", "picklist", values=["New Business", "Existing Business", "Renewal"]),
        F("lead_source", "Lead Source", "picklist", values=LEAD_SOURCES),
        F("next_step", "Next Step", "text", max_length=255),
        F("forecast_category", "Forecast Category", "picklist", values=["Pipeline", "Best Case", "Commit", "Closed", "Omitted"]),
        F("loss_reason", "Loss Reason", "picklist", values=["Price", "Competitor", "No Budget", "No Decision", "Timing", "Other"]),
        F("campaign", "Primary Campaign Source", "lookup", target="campaign", delete_rule="clear"),
        F("price_book", "Price Book", "lookup", target="price_book", delete_rule="restrict"),
        F("has_products", "Has Products", "checkbox", default_value=False, is_readonly=True),
        F("is_closed", "Closed", "checkbox", default_value=False, is_readonly=True),
        F("is_won", "Won", "checkbox", default_value=False, is_readonly=True),
        F("closed_date", "Closed On", "date", is_readonly=True),
        F("description", "Description", "long_text"),
    ],
    "page_layout": [
        section("Opportunity Information", ["name", "account", "primary_contact", "type", "lead_source", "campaign", "owner_id"]),
        section("Pipeline", ["stage", "probability", "forecast_category", "amount", "close_date", "next_step", "loss_reason", "price_book"]),
        section("Description", ["description"], 1),
        SYSTEM_SECTION,
    ],
    "compact_layout": ["account", "close_date", "amount", "stage", "owner_id"],
    "list_columns": ["name", "account", "stage", "amount", "close_date", "owner_id"],
    "related_lists": [
        related("opportunity_product", "opportunity", "Products", LINE_COLUMNS),
        related("quote", "opportunity", "Quotes", ["name", "status", "total", "expiry_date"]),
        related("invoice", "opportunity", "Invoices", ["name", "status", "total", "balance"]),
    ],
}  # fmt: skip

OPPORTUNITY_PRODUCT: Final[dict[str, Any]] = {
    "api_name": "opportunity_product", "label": "Opportunity Product", "plural_label": "Opportunity Products",
    "icon": "product", "color": "#f59e0b", "is_detail_only": True, "allow_activities": False, "allow_files": False,
    "allow_notes": False, "searchable": False, "sharing": "controlled_by_parent",
    "fields": [
        F("opportunity", "Opportunity", "master_detail", target="opportunity", required=True),
        F("product", "Product", "lookup", target="product", required=True, delete_rule="restrict"),
        F("price_book_entry", "Price Book Entry", "lookup", target="price_book_entry", delete_rule="restrict", is_readonly=True),
        F("quantity", "Quantity", "number", scale=2, required=True, default_value=1, min=0),
        F("unit_price", "Unit Price", "currency"),
        F("discount", "Discount", "currency", min=0),
        F("line_total", "Line Total", "currency", is_readonly=True),
        F("description", "Line Description", "text", max_length=255),
    ],
    "page_layout": [section("Line", ["opportunity", "product", "quantity", "unit_price", "discount", "line_total", "description"])],
    "list_columns": LINE_COLUMNS,
}  # fmt: skip

PRODUCT: Final[dict[str, Any]] = {
    "api_name": "product", "label": "Product", "plural_label": "Products", "icon": "product", "color": "#0ea5e9",
    "sharing": "read",
    "fields": [
        F("product_code", "Product Code", "text", max_length=40, is_unique=True, external_id=True, searchable=True, indexed=True),
        F("family", "Product Family", "picklist", values=["Hardware", "Software", "Services", "Subscription", "Other"]),
        F("is_active", "Active", "checkbox", default_value=True),
        F("tax_rate", "Tax Rate", "lookup", target="tax_rate", delete_rule="restrict"),
        F("unit_of_measure", "Unit of Measure", "text", max_length=20),
        F("standard_price", "Standard Price", "currency", min=0, help_text="List price in the standard price book."),
        F("description", "Description", "long_text"),
    ],
    "page_layout": [
        section("Product Information", ["name", "product_code", "family", "is_active", "tax_rate", "unit_of_measure", "standard_price"]),
        section("Description", ["description"], 1),
        SYSTEM_SECTION,
    ],
    "compact_layout": ["product_code", "family", "is_active", "standard_price"],
    "list_columns": ["name", "product_code", "family", "standard_price", "is_active"],
    "related_lists": [related("price_book_entry", "product", "Price Book Entries", ["price_book", "list_price", "is_active"])],
}  # fmt: skip

PRICE_BOOK: Final[dict[str, Any]] = {
    "api_name": "price_book", "label": "Price Book", "plural_label": "Price Books", "icon": "pricebook",
    "color": "#0ea5e9", "sharing": "read",
    "fields": [
        F("is_active", "Active", "checkbox", default_value=True),
        F("is_standard", "Standard Price Book", "checkbox", default_value=False, is_readonly=True),
        F("description", "Description", "long_text"),
    ],
    "page_layout": [section("Price Book", ["name", "is_active", "is_standard"]), section("Description", ["description"], 1), SYSTEM_SECTION],
    "compact_layout": ["is_active", "is_standard"],
    "list_columns": ["name", "is_active", "is_standard"],
    "related_lists": [related("price_book_entry", "price_book", "Entries", ["product", "list_price", "is_active"])],
}  # fmt: skip

PRICE_BOOK_ENTRY: Final[dict[str, Any]] = {
    "api_name": "price_book_entry", "label": "Price Book Entry", "plural_label": "Price Book Entries",
    "icon": "pricebook", "color": "#0ea5e9", "is_detail_only": True, "allow_activities": False, "allow_files": False,
    "allow_notes": False, "searchable": False, "sharing": "controlled_by_parent",
    "fields": [
        F("price_book", "Price Book", "master_detail", target="price_book", required=True),
        F("product", "Product", "lookup", target="product", required=True, delete_rule="restrict"),
        F("list_price", "List Price", "currency", required=True, min=0, track_history=True),
        F("is_active", "Active", "checkbox", default_value=True),
    ],
    "page_layout": [section("Entry", ["price_book", "product", "list_price", "is_active"])],
    "list_columns": ["product", "price_book", "list_price", "is_active"],
}  # fmt: skip

_TOTALS = [
    F("subtotal", "Subtotal", "currency", is_readonly=True),
    F("discount_total", "Discount", "currency", is_readonly=True),
    F("tax_total", "Tax", "currency", is_readonly=True),
    F("total", "Total", "currency", is_readonly=True),
]


def _line_object(api: str, label: str, plural: str, parent: str, parent_label: str) -> dict[str, Any]:
    return {
        "api_name": api, "label": label, "plural_label": plural, "icon": "line", "color": "#14b8a6",
        "is_detail_only": True, "allow_activities": False, "allow_files": False, "allow_notes": False,
        "searchable": False, "sharing": "controlled_by_parent",
        "fields": [
            F(parent, parent_label, "master_detail", target=parent, required=True),
            F("product", "Product", "lookup", target="product", delete_rule="restrict"),
            F("description", "Description", "text", max_length=255),
            F("quantity", "Quantity", "number", scale=2, required=True, default_value=1, min=0),
            F("unit_price", "Unit Price", "currency", required=True),
            F("discount", "Discount", "currency", min=0),
            F("tax_rate", "Tax Rate", "lookup", target="tax_rate", delete_rule="restrict"),
            F("tax_amount", "Tax", "currency", is_readonly=True),
            F("line_total", "Line Total (ex tax)", "currency", is_readonly=True),
            F("sort_order", "Line No.", "number"),
        ],
        "page_layout": [section("Line", [parent, "product", "description", "quantity", "unit_price", "discount", "tax_rate", "tax_amount", "line_total"])],
        "list_columns": ["product", "description", "quantity", "unit_price", "discount", "tax_amount", "line_total"],
    }  # fmt: skip


QUOTE: Final[dict[str, Any]] = {
    "api_name": "quote", "label": "Quote", "plural_label": "Quotes", "icon": "quote", "color": "#14b8a6",
    "sharing": "private", "name_field_type": "auto_number", "name_label": "Quote Number", "name_format": "Q-{00000}",
    "fields": [
        F("title", "Title", "text", max_length=255, required=True, searchable=True),
        F("opportunity", "Opportunity", "lookup", target="opportunity", delete_rule="clear"),
        F("account", "Account", "lookup", target="account", required=True, delete_rule="restrict"),
        F("contact", "Contact", "lookup", target="contact", delete_rule="clear"),
        F("status", "Status", "picklist", is_path=True, track_history=True, values=[
            P("Draft", "#94a3b8"), P("Sent", "#60a5fa"), P("Accepted", "#16a34a", closed=True), P("Rejected", "#dc2626", closed=True),
        ], default="Draft"),
        F("expiry_date", "Expiry Date", "date"),
        F("price_book", "Price Book", "lookup", target="price_book", delete_rule="restrict"),
        *_TOTALS,
        F("invoice", "Invoice", "lookup", target="invoice", is_readonly=True, delete_rule="clear"),
        F("terms", "Terms", "long_text"),
    ],
    "page_layout": [
        section("Quote Information", ["name", "title", "status", "opportunity", "account", "contact", "expiry_date", "price_book", "owner_id"]),
        section("Totals", ["subtotal", "discount_total", "tax_total", "total", "invoice"]),
        section("Terms", ["terms"], 1),
        SYSTEM_SECTION,
    ],
    "compact_layout": ["title", "account", "status", "total", "expiry_date"],
    "list_columns": ["name", "title", "account", "status", "total", "expiry_date"],
    "related_lists": [related("quote_line", "quote", "Quote Lines", ["product", "quantity", "unit_price", "discount", "tax_amount", "line_total"])],
}  # fmt: skip

INVOICE: Final[dict[str, Any]] = {
    "api_name": "invoice", "label": "Invoice", "plural_label": "Invoices", "icon": "invoice", "color": "#10b981",
    "sharing": "private", "name_label": "Invoice", "show_in_portal": True, "portal_fields": ["account", "contact"],
    "fields": [
        F("invoice_number", "Invoice Number", "text", max_length=40, is_readonly=True, is_unique=True, searchable=True),
        F("account", "Account", "lookup", target="account", required=True, delete_rule="restrict", indexed=True),
        F("contact", "Billing Contact", "lookup", target="contact", delete_rule="clear"),
        F("opportunity", "Opportunity", "lookup", target="opportunity", delete_rule="clear"),
        F("quote", "Quote", "lookup", target="quote", delete_rule="clear", is_readonly=True),
        F("status", "Status", "picklist", is_path=True, track_history=True, is_readonly=True, indexed=True, values=[
            P("Draft", "#94a3b8"), P("Issued", "#60a5fa"), P("Partially Paid", "#f59e0b"),
            P("Paid", "#16a34a", closed=True), P("Void", "#64748b", closed=True),
        ], default="Draft"),
        F("issue_date", "Issue Date", "date", indexed=True),
        F("due_date", "Due Date", "date", indexed=True),
        F("payment_terms_days", "Payment Terms (days)", "number", min=0, max=365),
        *_TOTALS,
        F("amount_paid", "Amount Paid", "currency", is_readonly=True),
        F("balance", "Balance Due", "currency", is_readonly=True),
        F("void_reason", "Void Reason", "textarea", is_readonly=True),
        F("notes", "Notes", "long_text"),
    ],
    "page_layout": [
        section("Invoice Information", ["invoice_number", "status", "account", "contact", "opportunity", "quote", "owner_id"]),
        section("Dates", ["issue_date", "due_date", "payment_terms_days"]),
        section("Totals", ["subtotal", "discount_total", "tax_total", "total", "amount_paid", "balance"]),
        section("Notes", ["notes", "void_reason"], 1),
        SYSTEM_SECTION,
    ],
    "compact_layout": ["account", "status", "total", "balance", "due_date"],
    "list_columns": ["name", "account", "status", "issue_date", "due_date", "total", "balance"],
    "related_lists": [
        related("invoice_line", "invoice", "Invoice Lines", ["product", "description", "quantity", "unit_price", "discount", "tax_amount", "line_total"]),
        related("payment", "invoice", "Payments", ["name", "payment_date", "amount", "method", "status"]),
    ],
}  # fmt: skip

PAYMENT: Final[dict[str, Any]] = {
    "api_name": "payment", "label": "Payment", "plural_label": "Payments", "icon": "payment", "color": "#10b981",
    "sharing": "controlled_by_parent", "name_field_type": "auto_number", "name_label": "Payment Number",
    "name_format": "PAY-{000000}", "allow_activities": False, "show_in_portal": True,
    "fields": [
        F("invoice", "Invoice", "master_detail", target="invoice", required=True),
        F("amount", "Amount", "currency", required=True, min=0.01),
        F("payment_date", "Payment Date", "date", required=True, default_value="today"),
        F("method", "Method", "picklist", values=["Bank Transfer", "Credit Card", "BPAY", "Cash", "Cheque", "Other"], default="Bank Transfer"),
        F("reference", "Reference", "text", max_length=80),
        F("status", "Status", "picklist", is_readonly=True, values=[P("Received", "#16a34a"), P("Reversed", "#dc2626")], default="Received"),
        F("reversal_reason", "Reversal Reason", "textarea", is_readonly=True),
    ],
    "page_layout": [section("Payment", ["name", "invoice", "amount", "payment_date", "method", "reference", "status", "reversal_reason"]), SYSTEM_SECTION],
    "compact_layout": ["invoice", "amount", "payment_date", "method", "status"],
    "list_columns": ["name", "invoice", "payment_date", "amount", "method", "status"],
}  # fmt: skip

TAX_RATE: Final[dict[str, Any]] = {
    "api_name": "tax_rate", "label": "Tax Rate", "plural_label": "Tax Rates", "icon": "tax", "color": "#64748b",
    "sharing": "read", "allow_activities": False, "allow_files": False, "allow_notes": False,
    "fields": [
        F("rate", "Rate (%)", "percent", required=True, scale=3, min=0, max=100),
        F("is_default", "Default", "checkbox", default_value=False),
        F("is_active", "Active", "checkbox", default_value=True),
        F("description", "Description", "textarea"),
    ],
    "page_layout": [section("Tax Rate", ["name", "rate", "is_default", "is_active", "description"]), SYSTEM_SECTION],
    "compact_layout": ["rate", "is_default", "is_active"],
    "list_columns": ["name", "rate", "is_default", "is_active"],
}  # fmt: skip

CASE: Final[dict[str, Any]] = {
    "api_name": "case", "label": "Case", "plural_label": "Cases", "icon": "case", "color": "#ec4899",
    "sharing": "private", "name_field_type": "auto_number", "name_label": "Case Number", "name_format": "CASE-{00000}",
    "allow_queues": True, "show_in_portal": True, "portal_fields": ["contact"],
    "fields": [
        F("subject", "Subject", "text", max_length=255, required=True, searchable=True),
        F("description", "Description", "long_text", searchable=True),
        F("account", "Account", "lookup", target="account", delete_rule="clear", indexed=True),
        F("contact", "Contact", "lookup", target="contact", delete_rule="clear", indexed=True),
        F("status", "Status", "picklist", is_path=True, track_history=True, indexed=True, values=[
            P("New", "#94a3b8"), P("Working", "#60a5fa"), P("Waiting on Customer", "#a78bfa"),
            P("Escalated", "#dc2626"), P("Closed", "#16a34a", closed=True),
        ], default="New"),
        F("priority", "Priority", "picklist", track_history=True, values=[
            P("Low", "#94a3b8"), P("Medium", "#60a5fa"), P("High", "#f59e0b"), P("Critical", "#dc2626"),
        ], default="Medium"),
        F("origin", "Origin", "picklist", values=["Email", "Phone", "Web", "Portal"], default="Phone"),
        F("type", "Type", "picklist", values=["Question", "Problem", "Feature Request", "Billing", "Other"]),
        F("first_response_due", "First Response Due", "datetime", is_readonly=True),
        F("resolution_due", "Resolution Due", "datetime", is_readonly=True, indexed=True),
        F("first_responded_at", "First Responded", "datetime", is_readonly=True),
        F("is_escalated", "Escalated (SLA)", "checkbox", default_value=False, is_readonly=True),
        F("closed_at", "Closed", "datetime", is_readonly=True),
        F("resolution", "Resolution", "long_text"),
        F("supplied_name", "Web Name", "text", max_length=120, is_readonly=True),
        F("supplied_email", "Web E-mail", "email", is_readonly=True),
    ],
    "page_layout": [
        section("Case Information", ["name", "subject", "status", "priority", "origin", "type", "account", "contact", "owner_id"]),
        section("Service Level", ["first_response_due", "first_responded_at", "resolution_due", "is_escalated", "closed_at"]),
        section("Description", ["description", "resolution"], 1),
        section("Web Information", ["supplied_name", "supplied_email"]),
        SYSTEM_SECTION,
    ],
    "compact_layout": ["subject", "status", "priority", "contact", "owner_id"],
    "list_columns": ["name", "subject", "status", "priority", "contact", "owner_id"],
}  # fmt: skip

CAMPAIGN: Final[dict[str, Any]] = {
    "api_name": "campaign", "label": "Campaign", "plural_label": "Campaigns", "icon": "campaign", "color": "#f43f5e",
    "sharing": "read",
    "fields": [
        F("type", "Type", "picklist", values=["Email", "Webinar", "Event", "Advertisement", "Social", "Direct Mail", "Other"]),
        F("status", "Status", "picklist", values=[P("Planned", "#94a3b8"), P("In Progress", "#60a5fa"), P("Completed", "#16a34a"), P("Aborted", "#dc2626")], default="Planned"),
        F("start_date", "Start Date", "date"),
        F("end_date", "End Date", "date"),
        F("budgeted_cost", "Budgeted Cost", "currency"),
        F("actual_cost", "Actual Cost", "currency"),
        F("expected_revenue", "Expected Revenue", "currency"),
        F("parent_campaign", "Parent Campaign", "lookup", target="campaign", delete_rule="clear"),
        F("is_active", "Active", "checkbox", default_value=True),
        F("description", "Description", "long_text"),
    ],
    "page_layout": [
        section("Campaign Information", ["name", "type", "status", "is_active", "start_date", "end_date", "parent_campaign", "owner_id"]),
        section("Budget", ["budgeted_cost", "actual_cost", "expected_revenue"]),
        section("Description", ["description"], 1),
        SYSTEM_SECTION,
    ],
    "compact_layout": ["type", "status", "start_date", "end_date", "owner_id"],
    "list_columns": ["name", "type", "status", "start_date", "end_date", "owner_id"],
    "related_lists": [
        related("campaign_member", "campaign", "Campaign Members", ["name", "lead", "contact", "status"]),
        related("opportunity", "campaign", "Influenced Opportunities", ["name", "stage", "amount", "close_date"]),
        related("lead", "campaign", "Leads", ["name", "company", "status"]),
        related("email_send", "campaign", "E-mail Sends", ["name", "status", "sent_at", "recipients_count"]),
    ],
}  # fmt: skip

CAMPAIGN_MEMBER: Final[dict[str, Any]] = {
    "api_name": "campaign_member", "label": "Campaign Member", "plural_label": "Campaign Members", "icon": "member",
    "color": "#f43f5e", "is_detail_only": True, "allow_activities": False, "allow_files": False, "allow_notes": False,
    "searchable": False, "sharing": "controlled_by_parent",
    "fields": [
        F("campaign", "Campaign", "master_detail", target="campaign", required=True),
        F("lead", "Lead", "lookup", target="lead", delete_rule="clear"),
        F("contact", "Contact", "lookup", target="contact", delete_rule="clear"),
        F("status", "Member Status", "picklist", values=["Planned", "Sent", "Responded", "Registered", "Attended", "Unsubscribed"], default="Planned", track_history=True),
        F("has_responded", "Responded", "checkbox", default_value=False, is_readonly=True),
        F("first_responded_date", "First Responded", "date", is_readonly=True),
    ],
    "page_layout": [section("Member", ["campaign", "lead", "contact", "status", "has_responded", "first_responded_date"])],
    "list_columns": ["name", "campaign", "status", "has_responded"],
}  # fmt: skip

SEGMENT: Final[dict[str, Any]] = {
    "api_name": "segment", "label": "Segment", "plural_label": "Segments", "icon": "segment", "color": "#f43f5e",
    "sharing": "read", "allow_activities": False,
    "fields": [
        F("target_object", "Members Are", "picklist", values=[{"value": "contact", "label": "Contacts"}, {"value": "lead", "label": "Leads"}], required=True, default="contact"),
        F("criteria", "Criteria (filter JSON)", "long_text", help_text="A filter over the members' fields; edited with the segment builder."),
        F("member_count", "Members", "number", is_readonly=True),
        F("counted_at", "Counted", "datetime", is_readonly=True),
        F("description", "Description", "long_text"),
    ],
    "page_layout": [section("Segment", ["name", "target_object", "member_count", "counted_at", "owner_id"]), section("Definition", ["criteria", "description"], 1), SYSTEM_SECTION],
    "compact_layout": ["target_object", "member_count", "counted_at"],
    "list_columns": ["name", "target_object", "member_count", "owner_id"],
}  # fmt: skip

EMAIL_TEMPLATE: Final[dict[str, Any]] = {
    "api_name": "email_template", "label": "Email Template", "plural_label": "Email Templates", "icon": "template",
    "color": "#f43f5e", "sharing": "read", "allow_activities": False,
    "fields": [
        F("subject", "Subject", "text", max_length=200, required=True),
        F("html_body", "HTML Body", "long_text", help_text="Merge fields: {{first_name}}, {{last_name}}, {{name}}, {{email}}, {{company}}, {{unsubscribe_url}}."),
        F("text_body", "Plain-text Body", "long_text"),
        F("category", "Category", "picklist", values=["Newsletter", "Promotion", "Announcement", "Event", "Transactional", "Other"]),
        F("is_active", "Active", "checkbox", default_value=True),
    ],
    "page_layout": [section("Template", ["name", "subject", "category", "is_active", "owner_id"]), section("Content", ["html_body", "text_body"], 1), SYSTEM_SECTION],
    "compact_layout": ["subject", "category", "is_active"],
    "list_columns": ["name", "subject", "category", "is_active"],
}  # fmt: skip

EMAIL_SEND: Final[dict[str, Any]] = {
    "api_name": "email_send", "label": "Email Send", "plural_label": "Email Sends", "icon": "send", "color": "#f43f5e",
    "sharing": "private", "allow_activities": False,
    "fields": [
        F("subject", "Subject", "text", max_length=200, required=True),
        F("template", "Template", "lookup", target="email_template", delete_rule="clear"),
        F("segment", "Segment", "lookup", target="segment", delete_rule="restrict"),
        F("campaign", "Campaign", "lookup", target="campaign", delete_rule="restrict"),
        F("from_name", "From Name", "text", max_length=80),
        F("from_email", "From E-mail", "email"),
        F("html_body", "HTML Body", "long_text"),
        F("text_body", "Plain-text Body", "long_text"),
        F("status", "Status", "picklist", is_readonly=True, is_path=True, values=[
            P("Draft", "#94a3b8"), P("Scheduled", "#60a5fa"), P("Sending", "#f59e0b"), P("Sent", "#16a34a", closed=True), P("Cancelled", "#64748b", closed=True),
        ], default="Draft"),
        F("scheduled_at", "Scheduled For", "datetime"),
        F("sent_at", "Sent", "datetime", is_readonly=True),
        F("recipients_count", "Recipients", "number", is_readonly=True),
        F("delivered_count", "Delivered", "number", is_readonly=True),
        F("opened_count", "Opened", "number", is_readonly=True),
        F("clicked_count", "Clicked", "number", is_readonly=True),
        F("bounced_count", "Bounced", "number", is_readonly=True),
        F("unsubscribed_count", "Unsubscribed", "number", is_readonly=True),
        F("skipped_count", "Skipped (no consent / duplicate)", "number", is_readonly=True),
    ],
    "page_layout": [
        section("E-mail Send", ["name", "subject", "status", "template", "segment", "campaign", "from_name", "from_email", "scheduled_at", "sent_at", "owner_id"]),
        section("Results", ["recipients_count", "delivered_count", "opened_count", "clicked_count", "bounced_count", "unsubscribed_count", "skipped_count"]),
        section("Content", ["html_body", "text_body"], 1),
        SYSTEM_SECTION,
    ],
    "compact_layout": ["subject", "status", "sent_at", "recipients_count", "opened_count"],
    "list_columns": ["name", "subject", "status", "scheduled_at", "sent_at", "recipients_count"],
}  # fmt: skip

CONSENT: Final[dict[str, Any]] = {
    "api_name": "consent", "label": "Consent", "plural_label": "Consents", "icon": "consent", "color": "#f43f5e",
    "sharing": "controlled_by_parent", "allow_activities": False, "allow_files": False, "searchable": False,
    "name_field_type": "auto_number", "name_label": "Consent Number", "name_format": "CON-{000000}",
    "fields": [
        F("contact", "Contact", "lookup", target="contact", delete_rule="clear", indexed=True),
        F("lead", "Lead", "lookup", target="lead", delete_rule="clear", indexed=True),
        F("channel", "Channel", "picklist", required=True, values=["Email", "SMS", "Phone", "Post"], default="Email"),
        F("status", "Status", "picklist", required=True, values=[P("Opted In", "#16a34a"), P("Opted Out", "#dc2626")]),
        F("source", "Source", "picklist", values=["Web Form", "Import", "Manual", "Unsubscribe Link", "Portal", "Lead Conversion"], default="Manual"),
        F("captured_at", "Captured", "datetime", default_value="now"),
        F("ip_address", "IP Address", "text", max_length=45),
        F("notes", "Notes", "textarea"),
    ],
    "page_layout": [section("Consent", ["name", "contact", "lead", "channel", "status", "source", "captured_at", "ip_address", "notes"]), SYSTEM_SECTION],
    "list_columns": ["name", "contact", "lead", "channel", "status", "source", "captured_at"],
}  # fmt: skip

TASK: Final[dict[str, Any]] = {
    "api_name": "task", "label": "Task", "plural_label": "Tasks", "icon": "task", "color": "#22c55e",
    "name_label": "Subject", "sharing": "controlled_by_parent", "allow_activities": False, "allow_files": False,
    "allow_notes": False,
    "fields": [
        F("type", "Type", "picklist", values=["Call", "E-mail", "Meeting", "To-Do", "Other"], default="To-Do"),
        F("status", "Status", "picklist", values=[P("Not Started", "#94a3b8"), P("In Progress", "#60a5fa"), P("Completed", "#16a34a", closed=True), P("Deferred", "#64748b")], default="Not Started", indexed=True),
        F("priority", "Priority", "picklist", values=["Low", "Normal", "High"], default="Normal"),
        F("due_date", "Due Date", "date", indexed=True),
        F("reminder_at", "Reminder", "datetime"),
        F("related_to", "Related To", "lookup", targets=ACTIVITY_TARGETS, delete_rule="clear", indexed=True),
        F("who", "Name", "lookup", targets=["contact", "lead"], delete_rule="clear"),
        F("description", "Comments", "long_text"),
        F("completed_at", "Completed", "datetime", is_readonly=True),
        F("reminder_sent", "Reminder Sent", "checkbox", default_value=False, is_readonly=True),
    ],
    "page_layout": [section("Task", ["name", "type", "status", "priority", "due_date", "reminder_at", "related_to", "who", "owner_id"]), section("Comments", ["description"], 1), SYSTEM_SECTION],
    "compact_layout": ["status", "due_date", "priority", "related_to", "owner_id"],
    "list_columns": ["name", "status", "priority", "due_date", "related_to", "owner_id"],
}  # fmt: skip

EVENT: Final[dict[str, Any]] = {
    "api_name": "event", "label": "Event", "plural_label": "Events", "icon": "event", "color": "#06b6d4",
    "name_label": "Subject", "sharing": "controlled_by_parent", "allow_activities": False, "allow_files": False,
    "allow_notes": False,
    "fields": [
        F("type", "Type", "picklist", values=["Meeting", "Call", "Consultation", "Other"], default="Meeting"),
        F("start_at", "Start", "datetime", required=True, indexed=True),
        F("end_at", "End", "datetime", required=True),
        F("all_day", "All-day", "checkbox", default_value=False),
        F("location", "Location", "text", max_length=255),
        F("related_to", "Related To", "lookup", targets=ACTIVITY_TARGETS, delete_rule="clear", indexed=True),
        F("who", "Name", "lookup", targets=["contact", "lead"], delete_rule="clear"),
        F("reminder_at", "Reminder", "datetime"),
        F("reminder_sent", "Reminder Sent", "checkbox", default_value=False, is_readonly=True),
        F("description", "Description", "long_text"),
    ],
    "page_layout": [section("Event", ["name", "type", "start_at", "end_at", "all_day", "location", "related_to", "who", "reminder_at", "owner_id"]), section("Description", ["description"], 1), SYSTEM_SECTION],
    "compact_layout": ["start_at", "end_at", "location", "related_to"],
    "list_columns": ["name", "start_at", "end_at", "location", "related_to", "owner_id"],
}  # fmt: skip

NOTE: Final[dict[str, Any]] = {
    "api_name": "note", "label": "Note", "plural_label": "Notes", "icon": "note", "color": "#eab308",
    "name_label": "Title", "sharing": "controlled_by_parent", "allow_activities": False, "allow_files": False,
    "allow_notes": False, "show_in_portal": True,
    "fields": [
        F("body", "Body", "long_text", searchable=True),
        F("related_to", "Related To", "lookup", targets=ACTIVITY_TARGETS, delete_rule="clear", indexed=True),
        F("is_public", "Visible in Portal", "checkbox", default_value=False),
    ],
    "page_layout": [section("Note", ["name", "related_to", "is_public", "owner_id"]), section("Body", ["body"], 1), SYSTEM_SECTION],
    "list_columns": ["name", "related_to", "created_at", "owner_id"],
}  # fmt: skip

FILE: Final[dict[str, Any]] = {
    "api_name": "file", "label": "File", "plural_label": "Files", "icon": "file", "color": "#64748b",
    "name_label": "File Name", "sharing": "controlled_by_parent", "allow_activities": False, "allow_files": False,
    "allow_notes": False, "show_in_portal": True,
    "fields": [
        F("related_to", "Related To", "lookup", targets=ACTIVITY_TARGETS, delete_rule="clear", indexed=True),
        F("stored_file_id", "Content", "text", max_length=40, is_readonly=True, filterable=False),
        F("content_type", "Type", "text", max_length=120, is_readonly=True),
        F("size", "Size (bytes)", "number", is_readonly=True),
        F("description", "Description", "textarea"),
        F("is_public", "Visible in Portal", "checkbox", default_value=False),
    ],
    "page_layout": [section("File", ["name", "related_to", "content_type", "size", "is_public", "description", "owner_id"]), SYSTEM_SECTION],
    "list_columns": ["name", "related_to", "content_type", "size", "created_at"],
}  # fmt: skip

OBJECTS: Final[list[dict[str, Any]]] = [
    ACCOUNT, CONTACT, LEAD, OPPORTUNITY, OPPORTUNITY_PRODUCT, PRODUCT, PRICE_BOOK, PRICE_BOOK_ENTRY, QUOTE,
    _line_object("quote_line", "Quote Line", "Quote Lines", "quote", "Quote"),
    INVOICE,
    _line_object("invoice_line", "Invoice Line", "Invoice Lines", "invoice", "Invoice"),
    PAYMENT, TAX_RATE, CASE, CAMPAIGN, CAMPAIGN_MEMBER, SEGMENT, EMAIL_TEMPLATE, EMAIL_SEND, CONSENT,
    TASK, EVENT, NOTE, FILE,
]  # fmt: skip


def _tab(kind: str, obj: str | None = None) -> dict[str, Any]:
    return {"kind": kind, "object": obj} if obj else {"kind": kind}


APPS: Final[list[dict[str, Any]]] = [
    {"key": "sales", "label": "Sales", "icon": "sales", "color": "#0176d3", "sort_order": 10, "description": "Leads, accounts, contacts, opportunities and quotes.",
     "tabs": [_tab("home"), _tab("object", "lead"), _tab("object", "contact"), _tab("object", "account"), _tab("object", "opportunity"),
              _tab("object", "product"), _tab("object", "price_book"), _tab("object", "quote"), _tab("object", "invoice"),
              _tab("calendar"), _tab("reports")]},
    {"key": "service", "label": "Service", "icon": "service", "color": "#ec4899", "sort_order": 20, "description": "Cases, queues and service levels.",
     "tabs": [_tab("home"), _tab("object", "case"), _tab("object", "contact"), _tab("object", "account"), _tab("queues"), _tab("reports")]},
    {"key": "marketing", "label": "Marketing", "icon": "marketing", "color": "#f43f5e", "sort_order": 30, "description": "Campaigns, segments, templates and e-mail sends.",
     "tabs": [_tab("home"), _tab("object", "campaign"), _tab("object", "contact"), _tab("object", "lead"), _tab("object", "segment"),
              _tab("object", "email_template"), _tab("object", "email_send"), _tab("object", "consent"), _tab("reports")]},
    {"key": "billing", "label": "Billing", "icon": "billing", "color": "#10b981", "sort_order": 40, "description": "Products, price books, quotes, invoices and payments.",
     "tabs": [_tab("home"), _tab("object", "product"), _tab("object", "price_book"), _tab("object", "quote"), _tab("object", "invoice"),
              _tab("object", "payment"), _tab("object", "tax_rate"), _tab("reports")]},
    {"key": "analytics", "label": "Analytics", "icon": "analytics", "color": "#6366f1", "sort_order": 50, "description": "Reports and dashboards.",
     "tabs": [_tab("reports"), _tab("dashboards")]},
]  # fmt: skip

_OPEN_LEAD = {"logic": "and", "conditions": [
    {"field": "status", "op": "not_in", "value": ["Qualified", "Unqualified"]},
    {"field": "is_converted", "op": "equals", "value": False},
]}  # fmt: skip
_OPEN_OPP = {"logic": "and", "conditions": [{"field": "is_closed", "op": "equals", "value": False}]}
_OPEN_CASE = {"logic": "and", "conditions": [{"field": "status", "op": "not_equals", "value": "Closed"}]}


def _views() -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = []
    for obj in OBJECTS:
        if obj.get("is_detail_only"):
            continue
        api = obj["api_name"]
        views.append(
            {
                "key": f"{api}_all",
                "object": api,
                "name": f"All {obj['plural_label']}",
                "columns": obj["list_columns"],
            }
        )
        views.append(
            {
                "key": f"{api}_mine",
                "object": api,
                "name": f"My {obj['plural_label']}",
                "scope": "mine",
                "columns": obj["list_columns"],
            }
        )
    views += [
        {"key": "lead_open", "object": "lead", "name": "All Open Leads", "filters": _OPEN_LEAD, "columns": LEAD["list_columns"]},
        {"key": "lead_my_open", "object": "lead", "name": "My Open Leads", "scope": "mine", "filters": _OPEN_LEAD, "columns": LEAD["list_columns"]},
        {"key": "opportunity_open", "object": "opportunity", "name": "Open Opportunities", "filters": _OPEN_OPP,
         "columns": OPPORTUNITY["list_columns"], "sort": [{"field": "close_date", "direction": "asc"}], "kanban_field": "stage"},
        {"key": "opportunity_closing", "object": "opportunity", "name": "Closing This Quarter", "filters": {"logic": "and", "conditions": [
            {"field": "close_date", "op": "equals", "value": "THIS_QUARTER"}, {"field": "is_closed", "op": "equals", "value": False}]},
         "columns": OPPORTUNITY["list_columns"], "sort": [{"field": "close_date", "direction": "asc"}]},
        {"key": "case_open", "object": "case", "name": "Open Cases", "filters": _OPEN_CASE, "columns": CASE["list_columns"],
         "sort": [{"field": "created_at", "direction": "desc"}], "kanban_field": "status"},
        {"key": "case_my_open", "object": "case", "name": "My Open Cases", "scope": "mine", "filters": _OPEN_CASE, "columns": CASE["list_columns"]},
        {"key": "case_queue", "object": "case", "name": "My Queues", "scope": "queue", "filters": _OPEN_CASE, "columns": CASE["list_columns"]},
        {"key": "invoice_overdue", "object": "invoice", "name": "Overdue Invoices", "filters": {"logic": "and", "conditions": [
            {"field": "status", "op": "in", "value": ["Issued", "Partially Paid"]}, {"field": "due_date", "op": "lt", "value": "TODAY"}]},
         "columns": INVOICE["list_columns"], "sort": [{"field": "due_date", "direction": "asc"}]},
        {"key": "invoice_unpaid", "object": "invoice", "name": "Unpaid Invoices", "filters": {"logic": "and", "conditions": [
            {"field": "status", "op": "in", "value": ["Issued", "Partially Paid"]}]}, "columns": INVOICE["list_columns"]},
        {"key": "task_open", "object": "task", "name": "My Open Tasks", "scope": "mine", "filters": {"logic": "and", "conditions": [
            {"field": "status", "op": "not_equals", "value": "Completed"}]}, "columns": TASK["list_columns"],
         "sort": [{"field": "due_date", "direction": "asc"}]},
        {"key": "product_active", "object": "product", "name": "Active Products", "filters": {"logic": "and", "conditions": [
            {"field": "is_active", "op": "equals", "value": True}]}, "columns": PRODUCT["list_columns"]},
    ]  # fmt: skip
    return views


# Plan v3 section 10 "Default field-level security": (profile, object, field, access).
FIELD_SECURITY: Final = [
    ("service_agent", "opportunity", "amount", "read"),
    ("service_agent", "opportunity", "probability", "read"),
    ("marketing_user", "opportunity", "amount", "read"),
    ("marketing_user", "opportunity", "probability", "read"),
    ("service_agent", "account", "annual_revenue", "hidden"),
    ("customer_portal", "account", "annual_revenue", "hidden"),
    ("marketing_user", "contact", "birthdate", "hidden"),
    ("customer_portal", "contact", "birthdate", "hidden"),
    ("sales_representative", "payment", "reference", "hidden"),
    ("service_agent", "payment", "reference", "hidden"),
    ("marketing_user", "payment", "reference", "hidden"),
    ("customer_portal", "payment", "reference", "hidden"),
    # Portal users see their invoices' figures but not internal fields.
    ("customer_portal", "invoice", "notes", "hidden"),
    ("customer_portal", "contact", "description", "hidden"),
    ("customer_portal", "contact", "lead_source", "hidden"),
    ("customer_portal", "case", "supplied_name", "hidden"),
    ("customer_portal", "case", "supplied_email", "hidden"),
]

DEFAULT_SETTINGS: Final[dict[str, Any]] = {
    "branding": {"name": "Segue CRM", "primary_color": "#0176d3", "logo_url": None},
    "company": {"legal_name": "", "abn": "", "address": "", "email": "", "phone": "", "website": ""},
    "billing": {
        "invoice_prefix": "INV-", "invoice_number_digits": 6, "payment_terms_days": 14,
        "invoice_footer": "Payment by bank transfer. Please quote the invoice number.",
        "bank_details": "", "gst_registered": True,
    },
    "case_sla": {
        "Critical": {"first_response_hours": 1, "resolution_hours": 8},
        "High": {"first_response_hours": 4, "resolution_hours": 24},
        "Medium": {"first_response_hours": 8, "resolution_hours": 72},
        "Low": {"first_response_hours": 24, "resolution_hours": 120},
    },
    "service": {"web_queue_id": None, "web_to_case_enabled": True, "web_to_lead_enabled": True},
    "locale": {"default_locale": "en-AU", "default_time_zone": "Australia/Sydney", "currency": "AUD"},
    "retention": {"recycle_bin_days": 30, "deleted_field_days": 15, "audit_years": 7, "object_years": {}},
    "marketing": {"from_name": "Segue CRM", "from_email": "", "postal_address": "", "batch_size": 200},
    "lead_conversion": {"field_map": {}},
}  # fmt: skip


def apply(conn: Connection) -> None:
    install_bundle(conn, {"objects": OBJECTS, "apps": APPS, "list_views": _views()})
    for profile, obj, field, access in FIELD_SECURITY:
        install_field_security(conn, security_id("profile", profile), obj, field, access)
    gst = install_record(
        conn,
        "tax_rate.gst",
        "tax_rate",
        "GST 10%",
        {
            "rate": 10,
            "is_default": True,
            "is_active": True,
            "description": "Australian Goods and Services Tax",
        },
    )
    install_record(
        conn,
        "tax_rate.gst_free",
        "tax_rate",
        "GST-free",
        {"rate": 0, "is_default": False, "is_active": True, "description": "GST-free supply"},
    )
    install_record(
        conn,
        "price_book.standard",
        "price_book",
        "Standard Price Book",
        {"is_active": True, "is_standard": True},
    )
    _ = gst
    conn.execute(
        text(
            "INSERT INTO queues (id, name, email, object_api_names, created_at, updated_at) VALUES (:id, 'Customer Support', "
            "NULL, CAST(:objs AS jsonb), now(), now()) ON CONFLICT DO NOTHING"
        ),
        {"id": SUPPORT_QUEUE_ID, "objs": '["case", "lead"]'},
    )
    for key, value in DEFAULT_SETTINGS.items():
        set_setting(conn, key, value)


STANDARD_PRICE_BOOK_ID: Final = stable_id("record", "price_book.standard")
SUPPORT_QUEUE_ID: Final = stable_id("queue", "customer_support")
GST_TAX_RATE_ID: Final = stable_id("record", "tax_rate.gst")
__all__ = ["APPS", "GST_TAX_RATE_ID", "OBJECTS", "STANDARD_PRICE_BOOK_ID", "apply", "install_link"]

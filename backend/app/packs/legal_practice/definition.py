"""Legal Practice (Australia) pack, version 1.0.0 (plan v4, section 6).

Matters, parties, conflict checks, time recording in 6-minute units, court dates, trust accounting and
costs disclosure under the Legal Profession Uniform Law. The pack supports compliance; the principal
confirms against current law society guidance.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import Connection

from app.engine.installer import (
    install_dashboard,
    install_field_security,
    install_folder,
    install_object_permission,
    install_report,
    set_setting,
)
from app.engine.standard_v1 import SYSTEM_SECTION, F, P, related, section
from app.packs.common import ProfileSpec, install_profiles
from app.security.seed_v1 import stable_id as security_id

KEY: Final = "legal_practice"
VERSION: Final = "1.0.0"
APP_KEY: Final = "legal_practice"
CLEAR_CONFLICTS: Final = "clear_conflicts"
MANAGE_TRUST: Final = "manage_trust"
# Uniform Law s 174: disclosure is required unless total legal costs are not likely to exceed $750.
DISCLOSURE_THRESHOLD: Final = 750

STAGES: Final[list[dict[str, Any]]] = [
    P("Intake", "#94a3b8"), P("Conflict Check", "#60a5fa"), P("Engaged", "#38bdf8"), P("Active", "#a78bfa"),
    P("Settlement/Hearing", "#f59e0b"), P("Closed", "#16a34a", closed=True),
]  # fmt: skip
STAGE_ORDER: Final = [s["value"] for s in STAGES]
PRACTICE_AREAS: Final = [
    "Family", "Property & Conveyancing", "Wills & Estates", "Commercial", "Litigation", "Employment",
    "Criminal", "Personal Injury", "Immigration", "Other",
]  # fmt: skip
JURISDICTIONS: Final = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT", "Federal"]

LEGAL_MATTER: Final[dict[str, Any]] = {
    "api_name": "legal_matter", "label": "Matter", "plural_label": "Matters", "icon": "scale", "color": "#1e3a8a",
    "sharing": "private", "name_field_type": "auto_number", "name_label": "Matter Number", "name_format": "LM-{YYYY}-{0000}",
    "show_in_portal": True, "portal_fields": ["client"],
    "fields": [
        F("title", "Matter Title", "text", max_length=200, required=True, searchable=True),
        F("client", "Client", "lookup", target="contact", required=True, delete_rule="restrict", indexed=True, track_history=True),
        F("organisation", "Billing Organisation", "lookup", target="account", delete_rule="clear"),
        F("practice_area", "Practice Area", "picklist", values=PRACTICE_AREAS, indexed=True),
        F("stage", "Stage", "picklist", is_path=True, track_history=True, indexed=True, values=STAGES, default="Intake"),
        F("status", "Status", "picklist", values=[P("Open", "#16a34a"), P("On Hold", "#f59e0b"), P("Closed", "#64748b")], default="Open", track_history=True),
        F("responsible_solicitor", "Responsible Solicitor", "user", track_history=True, indexed=True),
        F("supervising_principal", "Supervising Principal", "user"),
        F("court", "Court / Tribunal", "text", max_length=120),
        F("jurisdiction", "Jurisdiction", "picklist", values=JURISDICTIONS),
        F("court_file_number", "Court File Number", "text", max_length=60, searchable=True),
        F("opened_date", "Opened", "date", default_value="today"),
        F("limitation_date", "Limitation Date", "date", indexed=True, track_history=True),
        F("next_court_date", "Next Court Date", "datetime", is_readonly=True),
        F("billing_method", "Billing Method", "picklist", values=["Hourly", "Fixed Fee", "Conditional", "Pro Bono"], default="Hourly"),
        F("hourly_rate", "Hourly Rate", "currency", min=0),
        F("estimated_costs", "Estimated Legal Costs", "currency", min=0, track_history=True),
        F("costs_disclosure_provided", "Costs Disclosure Provided", "checkbox", default_value=False, track_history=True),
        F("costs_disclosure_date", "Costs Disclosure Date", "date"),
        F("conflict_cleared", "Conflict Cleared", "checkbox", default_value=False, is_readonly=True, track_history=True),
        F("unbilled_amount", "Unbilled Time (WIP)", "currency", is_readonly=True),
        F("trust_balance", "Trust Balance", "currency", is_readonly=True),
        F("closed_date", "Closed", "date", is_readonly=True),
        F("description", "Matter Description", "long_text"),
    ],
    "page_layout": [
        section("Matter", ["name", "title", "client", "organisation", "practice_area", "stage", "status", "owner_id"]),
        section("Team", ["responsible_solicitor", "supervising_principal"]),
        section("Court & Key Dates", ["court", "jurisdiction", "court_file_number", "opened_date", "limitation_date", "next_court_date", "closed_date"]),
        section("Costs", ["billing_method", "hourly_rate", "estimated_costs", "costs_disclosure_provided", "costs_disclosure_date", "conflict_cleared", "unbilled_amount", "trust_balance"]),
        section("Description", ["description"], 1),
        SYSTEM_SECTION,
    ],
    "compact_layout": ["title", "client", "stage", "responsible_solicitor", "limitation_date"],
    "list_columns": ["name", "title", "client", "practice_area", "stage", "responsible_solicitor"],
    "related_lists": [
        related("party", "legal_matter", "Parties", ["name", "role", "contact", "organisation"]),
        related("conflict_check", "legal_matter", "Conflict Checks", ["name", "result", "checked_at"]),
        related("legal_time_entry", "legal_matter", "Time Entries", ["entry_date", "timekeeper", "units", "amount", "status"]),
        related("court_date", "legal_matter", "Court Dates", ["name", "date_time", "type", "court"]),
        related("trust_transaction", "legal_matter", "Trust Ledger", ["name", "type", "amount", "transaction_date", "balance_after"]),
        related("invoice", "legal_matter", "Invoices", ["name", "status", "total", "balance"]),
    ],
}  # fmt: skip

PARTY: Final[dict[str, Any]] = {
    "api_name": "party", "label": "Party", "plural_label": "Parties", "icon": "member", "color": "#1e3a8a",
    "is_detail_only": True, "allow_activities": False, "allow_files": False, "sharing": "controlled_by_parent",
    "fields": [
        F("legal_matter", "Matter", "master_detail", target="legal_matter", required=True),
        F("role", "Role", "picklist", required=True, values=["Other Party", "Other Side's Lawyer", "Related Party", "Witness", "Expert", "Insurer", "Guarantor"], default="Other Party"),
        F("contact", "Contact", "lookup", target="contact", delete_rule="clear"),
        F("organisation", "Organisation", "lookup", target="account", delete_rule="clear"),
        F("acn_abn", "ACN / ABN", "text", max_length=20, searchable=True),
        F("notes", "Notes", "textarea"),
    ],
    "page_layout": [section("Party", ["name", "legal_matter", "role", "contact", "organisation", "acn_abn", "notes"])],
    "list_columns": ["name", "role", "contact", "organisation"],
    "compact_layout": ["legal_matter", "role", "contact", "organisation"],
}  # fmt: skip

CONFLICT_CHECK: Final[dict[str, Any]] = {
    "api_name": "conflict_check", "label": "Conflict Check", "plural_label": "Conflict Checks", "icon": "shield",
    "color": "#1e3a8a", "is_detail_only": True, "allow_activities": False, "sharing": "controlled_by_parent",
    "name_field_type": "auto_number", "name_label": "Check Number", "name_format": "CC-{00000}",
    "fields": [
        F("legal_matter", "Matter", "master_detail", target="legal_matter", required=True),
        F("search_terms", "Names Searched", "long_text", help_text="One name per line. Defaults to the client and every party."),
        F("result", "Result", "picklist", is_path=True, track_history=True, values=[P("Pending", "#94a3b8"), P("Potential Conflict", "#f59e0b"), P("Conflict", "#dc2626", closed=True), P("Clear", "#16a34a", closed=True)], default="Pending"),
        F("matches", "Matches Found", "long_text", is_readonly=True),
        F("match_count", "Matches", "number", is_readonly=True),
        F("checked_by", "Checked By", "user", is_readonly=True),
        F("checked_at", "Checked", "datetime", is_readonly=True),
        F("cleared_by", "Cleared By", "user", is_readonly=True),
        F("clearance_notes", "Clearance Notes / Waiver", "long_text", track_history=True),
    ],
    "page_layout": [section("Conflict Check", ["name", "legal_matter", "result", "match_count", "checked_by", "checked_at", "cleared_by"]),
                    section("Search", ["search_terms", "matches", "clearance_notes"], 1), SYSTEM_SECTION],
    "list_columns": ["name", "legal_matter", "result", "match_count", "checked_at"],
    "compact_layout": ["legal_matter", "result", "match_count", "checked_by", "checked_at"],
}  # fmt: skip

TIME_ENTRY: Final[dict[str, Any]] = {
    "api_name": "legal_time_entry", "label": "Time Entry", "plural_label": "Time Entries", "icon": "clock",
    "color": "#1e3a8a", "sharing": "private", "allow_activities": False, "allow_files": False, "searchable": False,
    "name_field_type": "auto_number", "name_label": "Entry Number", "name_format": "TE-{000000}",
    "fields": [
        F("legal_matter", "Matter", "lookup", target="legal_matter", required=True, delete_rule="restrict", indexed=True),
        F("timekeeper", "Timekeeper", "user", indexed=True),
        F("entry_date", "Date", "date", required=True, default_value="today", indexed=True),
        F("units", "Units (6 min)", "number", required=True, min=1, max=240),
        F("hours", "Hours", "number", scale=1, is_readonly=True),
        F("rate", "Hourly Rate", "currency", min=0),
        F("amount", "Amount (ex GST)", "currency", is_readonly=True),
        F("billable", "Billable", "checkbox", default_value=True),
        F("activity", "Activity", "picklist", values=["Attendance", "Correspondence", "Drafting", "Research", "Court Appearance", "Travel", "Review", "Other"]),
        F("narrative", "Narrative", "long_text", required=True),
        F("status", "Status", "picklist", is_readonly=True, values=[P("Unbilled", "#f59e0b"), P("Billed", "#16a34a"), P("Written Off", "#64748b")], default="Unbilled", indexed=True),
        F("invoice", "Invoice", "lookup", target="invoice", delete_rule="restrict", is_readonly=True),
    ],
    "page_layout": [section("Time", ["name", "legal_matter", "timekeeper", "entry_date", "activity", "units", "hours", "rate", "amount", "billable", "status", "invoice"]),
                    section("Narrative", ["narrative"], 1), SYSTEM_SECTION],
    "compact_layout": ["legal_matter", "timekeeper", "entry_date", "units", "amount"],
    "list_columns": ["name", "legal_matter", "timekeeper", "entry_date", "units", "amount", "status"],
}  # fmt: skip

COURT_DATE: Final[dict[str, Any]] = {
    "api_name": "court_date", "label": "Court Date", "plural_label": "Court Dates", "icon": "event", "color": "#1e3a8a",
    "is_detail_only": True, "allow_files": False, "sharing": "controlled_by_parent", "show_in_portal": True,
    "fields": [
        F("legal_matter", "Matter", "master_detail", target="legal_matter", required=True),
        F("date_time", "Date and Time", "datetime", required=True, indexed=True),
        F("type", "Type", "picklist", required=True, values=["Mention", "Directions", "Hearing", "Trial", "Mediation", "Conciliation", "Judgment", "Filing Deadline"]),
        F("court", "Court / Tribunal", "text", max_length=120),
        F("courtroom", "Courtroom / Registry", "text", max_length=80),
        F("appearing", "Appearing", "user"),
        F("outcome", "Outcome", "textarea"),
        F("is_public", "Visible to Client", "checkbox", default_value=True),
    ],
    "page_layout": [section("Court Date", ["name", "legal_matter", "type", "date_time", "court", "courtroom", "appearing", "is_public", "outcome"])],
    "list_columns": ["name", "type", "date_time", "court", "appearing"],
    "compact_layout": ["legal_matter", "type", "date_time", "court", "appearing"],
}  # fmt: skip

TRUST: Final[dict[str, Any]] = {
    "api_name": "trust_transaction", "label": "Trust Transaction", "plural_label": "Trust Ledger", "icon": "ledger",
    "color": "#1e3a8a", "sharing": "private", "allow_activities": False, "allow_notes": False,
    "name_field_type": "auto_number", "name_label": "Receipt / Payment No.", "name_format": "TR-{000000}",
    "fields": [
        F("legal_matter", "Matter", "lookup", target="legal_matter", required=True, delete_rule="restrict", indexed=True),
        F("client", "Client", "lookup", target="contact", is_readonly=True, delete_rule="restrict", indexed=True),
        F("type", "Type", "picklist", required=True, values=["Receipt", "Payment", "Transfer to Office"]),
        F("amount", "Amount", "currency", required=True, min=0.01),
        F("signed_amount", "Ledger Amount", "currency", is_readonly=True),
        F("transaction_date", "Date", "date", required=True, default_value="today"),
        F("payer_payee", "Paid By / Paid To", "text", max_length=120, required=True),
        F("method", "Method", "picklist", values=["EFT", "Cheque", "BPAY", "Cash", "Card"], default="EFT"),
        F("reference", "Reference", "text", max_length=80),
        F("invoice", "Invoice", "lookup", target="invoice", delete_rule="restrict"),
        F("balance_after", "Matter Trust Balance After", "currency", is_readonly=True),
        F("description", "Purpose", "textarea", required=True),
    ],
    "page_layout": [section("Transaction", ["name", "legal_matter", "client", "type", "amount", "transaction_date", "payer_payee", "method", "reference", "invoice", "balance_after", "description"]), SYSTEM_SECTION],
    "compact_layout": ["legal_matter", "type", "amount", "transaction_date", "balance_after"],
    "list_columns": ["name", "legal_matter", "type", "amount", "transaction_date", "balance_after"],
}  # fmt: skip

STANDARD_FIELDS: Final[list[dict[str, Any]]] = [
    {
        **F("legal_matter", "Matter", "lookup", target="legal_matter", delete_rule="clear"),
        "object": "invoice",
    },
    {**F("date_of_birth", "Date of Birth", "date"), "object": "contact"},
    {
        **F("id_verified", "Identity Verified", "checkbox", default_value=False, track_history=True),
        "object": "contact",
    },
    {**F("id_verified_date", "Identity Verified On", "date"), "object": "contact"},
    {**F("acn", "ACN", "text", max_length=11, searchable=True), "object": "account"},
]

APP: Final[dict[str, Any]] = {
    "key": APP_KEY, "label": "Legal Practice", "icon": "scale", "color": "#1e3a8a", "sort_order": 5,
    "description": "Matters, clients, conflict checks, time, court dates and trust accounting.",
    "tabs": [{"kind": "home"}, {"kind": "object", "object": "lead"}, {"kind": "object", "object": "contact"},
             {"kind": "object", "object": "account"}, {"kind": "object", "object": "legal_matter"},
             {"kind": "object", "object": "legal_time_entry"}, {"kind": "object", "object": "trust_transaction"},
             {"kind": "object", "object": "invoice"}, {"kind": "calendar"}, {"kind": "reports"}, {"kind": "dashboards"}],
}  # fmt: skip

_OPEN = {"logic": "and", "conditions": [{"field": "status", "op": "not_equals", "value": "Closed"}]}
LIST_VIEWS: Final[list[dict[str, Any]]] = [
    {"key": "legal_matter_all", "object": "legal_matter", "name": "All Matters", "columns": LEGAL_MATTER["list_columns"], "kanban_field": "stage"},
    {"key": "legal_matter_mine", "object": "legal_matter", "name": "My Matters", "scope": "mine", "columns": LEGAL_MATTER["list_columns"], "kanban_field": "stage", "filters": _OPEN},
    {"key": "legal_matter_open", "object": "legal_matter", "name": "Open Matters", "columns": LEGAL_MATTER["list_columns"], "kanban_field": "stage", "filters": _OPEN},
    {"key": "legal_matter_limitation", "object": "legal_matter", "name": "Limitation Dates (90 days)", "columns": ["name", "title", "client", "limitation_date", "responsible_solicitor"],
     "filters": {"logic": "and", "conditions": [{"field": "limitation_date", "op": "equals", "value": "NEXT_N_DAYS:90"}]}, "sort": [{"field": "limitation_date", "direction": "asc"}]},
    {"key": "legal_time_entry_mine", "object": "legal_time_entry", "name": "My Time", "scope": "mine", "columns": TIME_ENTRY["list_columns"], "sort": [{"field": "entry_date", "direction": "desc"}]},
    {"key": "legal_time_entry_unbilled", "object": "legal_time_entry", "name": "Unbilled Time (WIP)", "columns": TIME_ENTRY["list_columns"],
     "filters": {"logic": "and", "conditions": [{"field": "status", "op": "equals", "value": "Unbilled"}, {"field": "billable", "op": "equals", "value": True}]},
     "sort": [{"field": "entry_date", "direction": "asc"}]},
    {"key": "trust_transaction_all", "object": "trust_transaction", "name": "Trust Ledger", "columns": TRUST["list_columns"], "sort": [{"field": "created_at", "direction": "desc"}]},
]  # fmt: skip

PACK_OBJECTS: Final = [
    "legal_matter",
    "party",
    "conflict_check",
    "legal_time_entry",
    "court_date",
    "trust_transaction",
]


def bundle() -> dict[str, Any]:
    return {
        "objects": [LEGAL_MATTER, PARTY, CONFLICT_CHECK, TIME_ENTRY, COURT_DATE, TRUST],
        "fields": STANDARD_FIELDS,
        "apps": [APP],
        "list_views": LIST_VIEWS,
    }


PROFILES: Final[list[ProfileSpec]] = [
    ("lp_principal", "Principal", "Legal practitioner director / principal: every matter, trust account and conflict clearance.", "sales_manager",
     {"legal_matter": "RCED VA MA", "party": "RCED VA MA", "conflict_check": "RCED VA MA", "legal_time_entry": "RCED VA MA", "court_date": "RCED VA MA",
      "trust_transaction": "RC VA", "invoice": "RCE VA MA", "payment": "RC VA", "account": "RCED VA MA", "contact": "RCED VA MA"},
     ("manage_portal_users", "transfer_records", "export_data", "import_data", "manage_public_reports"), (CLEAR_CONFLICTS, MANAGE_TRUST)),
    ("lp_solicitor", "Solicitor", "Runs their own matters: time, parties, court dates and invoices.", "sales_representative",
     {"legal_matter": "RCE", "party": "RCED", "conflict_check": "RCE", "legal_time_entry": "RCE", "court_date": "RCED",
      "trust_transaction": "R", "invoice": "RCE"}, ("manage_portal_users",), ()),
    ("lp_paralegal", "Paralegal", "Supports solicitors on shared matters: parties, court dates, time and documents.", "service_agent",
     {"legal_matter": "RE", "party": "RCED", "conflict_check": "RC", "legal_time_entry": "RCE", "court_date": "RCED"}, (), ()),
    ("lp_accounts", "Trust Accountant", "Receipts and payments in the trust ledger, invoicing and payments.", "finance",
     {"legal_matter": "R VA", "legal_time_entry": "R VA", "trust_transaction": "RC VA"}, (), (MANAGE_TRUST,)),
    ("lp_auditor", "External Examiner", "Reads matters and the trust ledger for the annual trust examination; changes nothing.", "read_only",
     dict.fromkeys(PACK_OBJECTS, "R VA"), (), ()),
]  # fmt: skip

REPORT_FOLDER: Final = "legal_reports"
_UNBILLED = {
    "logic": "and",
    "conditions": [
        {"field": "status", "op": "equals", "value": "Unbilled"},
        {"field": "billable", "op": "equals", "value": True},
    ],
}
REPORTS: Final[list[tuple[str, str, str, dict[str, Any]]]] = [
    ("lp_matters_by_stage", "Open Matters by Stage", "legal_matter", {"format": "summary", "group_by": ["stage"], "aggregates": [{"op": "count"}], "filters": _OPEN, "chart": {"type": "funnel"}}),
    ("lp_matters_by_area", "Matters by Practice Area", "legal_matter", {"format": "summary", "group_by": ["practice_area"], "aggregates": [{"op": "count"}], "filters": _OPEN, "chart": {"type": "donut"}}),
    ("lp_wip", "Work in Progress (Unbilled Time)", "legal_time_entry", {"format": "summary", "group_by": ["legal_matter"], "aggregates": [{"op": "sum", "field": "amount"}, {"op": "sum", "field": "hours"}], "filters": _UNBILLED, "chart": {"type": "bar"}}),
    ("lp_billable_hours", "Billable Hours by Timekeeper", "legal_time_entry", {"format": "summary", "group_by": ["timekeeper"], "aggregates": [{"op": "sum", "field": "hours"}, {"op": "sum", "field": "amount"}],
                                                                             "filters": {"logic": "and", "conditions": [{"field": "billable", "op": "equals", "value": True}, {"field": "entry_date", "op": "equals", "value": "THIS_MONTH"}]}, "chart": {"type": "bar"}}),
    ("lp_trust_balances", "Trust Balances by Matter", "trust_transaction", {"format": "summary", "group_by": ["legal_matter"], "aggregates": [{"op": "sum", "field": "signed_amount"}, {"op": "count"}], "chart": {"type": "bar"}}),
    ("lp_limitation_dates", "Limitation Dates (next 90 days)", "legal_matter", {"format": "tabular", "columns": ["name", "title", "client", "limitation_date", "responsible_solicitor"],
                                                                                  "filters": {"logic": "and", "conditions": [{"field": "limitation_date", "op": "equals", "value": "NEXT_N_DAYS:90"}]}, "sort": [{"field": "limitation_date", "direction": "asc"}]}),
    ("lp_solicitor_workload", "Solicitor Workload", "legal_matter", {"format": "summary", "group_by": ["responsible_solicitor"], "aggregates": [{"op": "count"}], "filters": _OPEN, "chart": {"type": "bar"}}),
]  # fmt: skip


def install(conn: Connection) -> None:
    install_profiles(conn, KEY, PROFILES)
    ro = security_id("profile", "read_only")
    for obj in PACK_OBJECTS:
        install_object_permission(conn, ro, obj, {"can_read": True, "view_all": True})
    portal = security_id("profile", "customer_portal")
    for obj in ("legal_matter", "court_date"):
        install_object_permission(conn, portal, obj, {"can_read": True})
    for field in (
        "supervising_principal",
        "hourly_rate",
        "conflict_cleared",
        "unbilled_amount",
        "description",
        "organisation",
    ):
        install_field_security(conn, portal, "legal_matter", field, "hidden")
    install_folder(conn, REPORT_FOLDER, "Legal Practice Reports")
    for key, name, obj, definition in REPORTS:
        install_report(conn, key, REPORT_FOLDER, name, obj, definition, pack_key=KEY)
    install_dashboard(
        conn,
        "lp_practice_dashboard",
        REPORT_FOLDER,
        "Practice Dashboard",
        [
            {
                "report": "lp_matters_by_stage",
                "title": "Open matters by stage",
                "chart": "funnel",
                "width": 2,
            },
            {"report": "lp_matters_by_area", "title": "Practice areas", "chart": "donut", "width": 1},
            {"report": "lp_wip", "title": "Work in progress", "chart": "bar", "width": 2},
            {"report": "lp_billable_hours", "title": "Billable hours this month", "chart": "bar", "width": 1},
            {"report": "lp_limitation_dates", "title": "Limitation dates", "chart": "table", "width": 3},
        ],
        "Matters, WIP, billable hours and limitation dates.",
        pack_key=KEY,
    )
    set_setting(
        conn,
        KEY,
        {
            "default_hourly_rate": 380,
            "disclosure_threshold": DISCLOSURE_THRESHOLD,
            "limitation_reminder_days": [90, 30, 7],
            "court_reminder_days": [7, 1],
        },
    )

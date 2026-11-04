"""Accounting Practice (Australia) pack, version 1.0.0 (plan v4, section 6).

Engagements (tax returns, BAS/IAS, SMSF audits, bookkeeping, advisory), APES 305 engagement letters with
client e-signature, ATO lodgement deadlines, document requests through the portal, time recording, WIP
and recoverability. Default due dates are a starting point; the practice confirms them against the ATO
lodgment program for tax agents.
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

KEY: Final = "accounting_practice"
VERSION: Final = "1.1.0"
APP_KEY: Final = "accounting_practice"
LODGE: Final = "lodge_returns"

STAGES: Final[list[dict[str, Any]]] = [
    P("Not Started", "#94a3b8"), P("Awaiting Information", "#60a5fa"), P("In Progress", "#a78bfa"),
    P("Review", "#f59e0b"), P("Ready to Lodge", "#38bdf8"), P("Lodged", "#0ea5e9"), P("Complete", "#16a34a", closed=True),
]  # fmt: skip
STAGE_ORDER: Final = [s["value"] for s in STAGES]
ENGAGEMENT_TYPES: Final = [
    "Individual Tax Return", "Company Tax Return", "Trust Tax Return", "Partnership Tax Return", "SMSF Annual Return",
    "BAS", "IAS", "FBT Return", "SMSF Audit", "Bookkeeping", "Payroll", "Advisory",
]  # fmt: skip
LODGED_TYPES: Final = {
    "Individual Tax Return", "Company Tax Return", "Trust Tax Return", "Partnership Tax Return",
    "SMSF Annual Return", "BAS", "IAS", "FBT Return",
}  # fmt: skip
ENTITY_TYPES: Final = [
    "Individual",
    "Sole Trader",
    "Company",
    "Trust",
    "Partnership",
    "SMSF",
    "Not-for-profit",
]

ENGAGEMENT: Final[dict[str, Any]] = {
    "api_name": "engagement", "label": "Engagement", "plural_label": "Engagements", "icon": "calculator", "color": "#6d28d9",
    "sharing": "private", "name_field_type": "auto_number", "name_label": "Job Number", "name_format": "JOB-{YYYY}-{0000}",
    "show_in_portal": True, "portal_fields": ["client", "contact"],
    "fields": [
        F("client", "Client", "lookup", target="account", required=True, delete_rule="restrict", indexed=True, track_history=True),
        F("contact", "Client Contact", "lookup", target="contact", delete_rule="clear"),
        F("type", "Engagement Type", "picklist", required=True, values=ENGAGEMENT_TYPES, indexed=True),
        F("financial_year", "Financial Year", "text", max_length=7, help_text="e.g. 2025-26", indexed=True),
        F("period", "Period", "text", max_length=40, help_text="For BAS/IAS, e.g. Q1 Jul-Sep"),
        F("stage", "Stage", "picklist", is_path=True, track_history=True, indexed=True, values=STAGES, default="Not Started"),
        F("responsible_accountant", "Responsible Accountant", "user", track_history=True, indexed=True),
        F("reviewer", "Reviewer", "user", track_history=True),
        F("due_date", "Lodgement Due", "date", indexed=True, track_history=True),
        F("lodged_date", "Lodged", "date", is_readonly=True),
        F("ato_reference", "ATO Lodgement Reference", "text", max_length=40, searchable=True),
        F("noa_date", "Notice of Assessment", "date", help_text="When the ATO's notice of assessment was received."),
        F("noa_amount", "Refund / (Payable)", "currency", help_text="Refund as a positive amount, tax payable as negative."),
        F("fee_type", "Fee Type", "picklist", values=["Fixed Fee", "Time-based"], default="Fixed Fee"),
        F("fee", "Agreed Fee", "currency", min=0),
        F("letter_signed", "Engagement Letter Signed", "checkbox", default_value=False, is_readonly=True, track_history=True),
        F("time_cost", "Time Cost", "currency", is_readonly=True),
        F("unbilled_amount", "Unbilled Time (WIP)", "currency", is_readonly=True),
        F("recoverability", "Recoverability", "percent", is_readonly=True, help_text="Agreed fee as a percentage of time cost."),
        F("description", "Scope Notes", "long_text"),
    ],
    "page_layout": [
        section("Engagement", ["name", "client", "contact", "type", "financial_year", "period", "stage", "owner_id"]),
        section("Team", ["responsible_accountant", "reviewer"]),
        section("Lodgement", ["due_date", "lodged_date", "ato_reference", "noa_date", "noa_amount"]),
        section("Fees", ["fee_type", "fee", "letter_signed", "time_cost", "unbilled_amount", "recoverability"]),
        section("Scope", ["description"], 1),
        SYSTEM_SECTION,
    ],
    "compact_layout": ["client", "type", "financial_year", "stage", "due_date"],
    "list_columns": ["name", "client", "type", "financial_year", "stage", "due_date", "responsible_accountant"],
    "related_lists": [
        related("engagement_letter", "engagement", "Engagement Letters", ["name", "status", "fee_estimate", "signed_at"]),
        related("document_request", "engagement", "Document Requests", ["name", "status", "due_date", "is_public"]),
        related("engagement_time_entry", "engagement", "Time Entries", ["entry_date", "staff", "units", "amount", "status"]),
        related("lodgement_deadline", "engagement", "Lodgement Deadlines", ["name", "lodgement_type", "due_date", "status"]),
        related("invoice", "engagement", "Invoices", ["name", "status", "total", "balance"]),
    ],
}  # fmt: skip

LETTER: Final[dict[str, Any]] = {
    "api_name": "engagement_letter", "label": "Engagement Letter", "plural_label": "Engagement Letters", "icon": "agreement",
    "color": "#6d28d9", "is_detail_only": True, "allow_activities": False, "sharing": "controlled_by_parent",
    "show_in_portal": True, "name_field_type": "auto_number", "name_label": "Letter Number", "name_format": "EL-{00000}",
    "fields": [
        F("engagement", "Engagement", "master_detail", target="engagement", required=True),
        F("scope", "Scope and Responsibilities (APES 305)", "long_text", required=True),
        F("client_responsibilities", "Client Responsibilities", "long_text"),
        F("fee_estimate", "Fee / Basis of Fees", "currency", min=0),
        F("valid_until", "Covers Engagements Until", "date"),
        F("status", "Status", "picklist", is_path=True, is_readonly=True, values=[P("Draft", "#94a3b8"), P("Sent", "#60a5fa"), P("Signed", "#16a34a", closed=True), P("Cancelled", "#64748b", closed=True)], default="Draft"),
        F("practitioner", "Tax Practitioner", "user", is_readonly=True),
        F("tax_agent_number", "Tax Agent Number", "text", max_length=12, is_readonly=True),
        F("sent_at", "Sent", "datetime", is_readonly=True),
        F("signed_name", "Signed By", "text", max_length=120, is_readonly=True),
        F("signed_at", "Signed", "datetime", is_readonly=True),
        F("signed_ip", "Signed From IP", "text", max_length=45, is_readonly=True),
    ],
    "page_layout": [section("Letter", ["name", "engagement", "status", "fee_estimate", "valid_until", "practitioner", "tax_agent_number"]),
                    section("Terms", ["scope", "client_responsibilities"], 1),
                    section("Signature", ["sent_at", "signed_name", "signed_at", "signed_ip"]), SYSTEM_SECTION],
    "list_columns": ["name", "engagement", "status", "fee_estimate", "signed_at"],
    "compact_layout": ["engagement", "status", "fee_estimate", "sent_at", "signed_at"],
}  # fmt: skip

DEADLINE: Final[dict[str, Any]] = {
    "api_name": "lodgement_deadline", "label": "Lodgement Deadline", "plural_label": "Lodgement Deadlines", "icon": "event",
    "color": "#6d28d9", "sharing": "private", "allow_files": False,
    "name_field_type": "auto_number", "name_label": "Deadline Number", "name_format": "DL-{00000}",
    "fields": [
        F("client", "Client", "lookup", target="account", required=True, delete_rule="restrict", indexed=True),
        F("engagement", "Engagement", "lookup", target="engagement", delete_rule="clear"),
        F("lodgement_type", "Lodgement", "picklist", required=True, values=["BAS", "IAS", "Income Tax Return", "FBT Return", "SMSF Annual Return", "TPAR", "Payroll Tax", "Super Guarantee"]),
        F("period", "Period", "text", max_length=40),
        F("due_date", "Due Date", "date", required=True, indexed=True),
        F("status", "Status", "picklist", values=[P("Upcoming", "#60a5fa"), P("Overdue", "#dc2626"), P("Lodged", "#16a34a"), P("Deferred", "#f59e0b")], default="Upcoming", indexed=True),
        F("lodged_on", "Lodged On", "date"),
        F("responsible", "Responsible", "user", indexed=True),
        F("notes", "Notes", "textarea"),
    ],
    "page_layout": [section("Deadline", ["name", "client", "engagement", "lodgement_type", "period", "due_date", "status", "lodged_on", "responsible", "notes"]), SYSTEM_SECTION],
    "list_columns": ["name", "client", "lodgement_type", "period", "due_date", "status", "responsible"],
    "compact_layout": ["client", "lodgement_type", "period", "due_date", "status"],
}  # fmt: skip

DOCUMENT_REQUEST: Final[dict[str, Any]] = {
    "api_name": "document_request", "label": "Document Request", "plural_label": "Document Requests", "icon": "checklist",
    "color": "#6d28d9", "is_detail_only": True, "allow_activities": False, "sharing": "controlled_by_parent",
    "show_in_portal": True, "searchable": False,
    "fields": [
        F("engagement", "Engagement", "master_detail", target="engagement", required=True),
        F("status", "Status", "picklist", track_history=True, values=[P("Requested", "#94a3b8"), P("Uploaded", "#60a5fa"), P("Accepted", "#16a34a"), P("Not Applicable", "#64748b")], default="Requested"),
        F("due_date", "Due Date", "date"),
        F("instructions", "Instructions", "textarea"),
        F("is_public", "Visible to Client", "checkbox", default_value=True),
        F("sort_order", "Order", "number"),
    ],
    "page_layout": [section("Request", ["name", "engagement", "status", "due_date", "is_public", "sort_order", "instructions"])],
    "list_columns": ["name", "status", "due_date", "is_public"],
    "compact_layout": ["engagement", "status", "due_date", "is_public"],
}  # fmt: skip

TIME_ENTRY: Final[dict[str, Any]] = {
    "api_name": "engagement_time_entry", "label": "Time Entry", "plural_label": "Time Entries", "icon": "clock",
    "color": "#6d28d9", "sharing": "private", "allow_activities": False, "allow_files": False, "searchable": False,
    "name_field_type": "auto_number", "name_label": "Entry Number", "name_format": "TS-{000000}",
    "fields": [
        F("engagement", "Engagement", "lookup", target="engagement", required=True, delete_rule="restrict", indexed=True),
        F("staff", "Staff Member", "user", indexed=True),
        F("entry_date", "Date", "date", required=True, default_value="today", indexed=True),
        F("units", "Units (6 min)", "number", required=True, min=1, max=240),
        F("hours", "Hours", "number", scale=1, is_readonly=True),
        F("rate", "Charge-out Rate", "currency", min=0),
        F("amount", "Amount (ex GST)", "currency", is_readonly=True),
        F("billable", "Billable", "checkbox", default_value=True),
        F("narrative", "Work Done", "textarea", required=True),
        F("status", "Status", "picklist", is_readonly=True, values=[P("Unbilled", "#f59e0b"), P("Billed", "#16a34a"), P("Written Off", "#64748b")], default="Unbilled", indexed=True),
        F("invoice", "Invoice", "lookup", target="invoice", delete_rule="restrict", is_readonly=True),
    ],
    "page_layout": [section("Time", ["name", "engagement", "staff", "entry_date", "units", "hours", "rate", "amount", "billable", "status", "invoice", "narrative"]), SYSTEM_SECTION],
    "list_columns": ["name", "engagement", "staff", "entry_date", "units", "amount", "status"],
    "compact_layout": ["engagement", "staff", "entry_date", "units", "amount"],
}  # fmt: skip

STANDARD_FIELDS: Final[list[dict[str, Any]]] = [
    {**F("entity_type", "Entity Type", "picklist", values=ENTITY_TYPES), "object": "account"},
    {
        **F("tfn", "Tax File Number", "encrypted_text", max_length=11, default_access="hidden"),
        "object": "account",
    },
    {**F("gst_registered", "Registered for GST", "checkbox", default_value=False), "object": "account"},
    {
        **F(
            "bas_frequency",
            "BAS Frequency",
            "picklist",
            values=["Monthly", "Quarterly", "Annually", "Not Registered"],
        ),
        "object": "account",
    },
    {
        **F("year_end", "Financial Year End", "text", max_length=5, help_text="DD-MM, normally 30-06"),
        "object": "account",
    },
    {**F("client_manager", "Client Manager", "user", indexed=True), "object": "account"},
    {
        **F(
            "identity_verified",
            "Identity Verified",
            "checkbox",
            default_value=False,
            track_history=True,
            help_text="Proof of identity sighted for the client and its contact (TPB and ATO requirements).",
        ),
        "object": "account",
    },
    {**F("identity_verified_date", "Identity Verified On", "date"), "object": "account"},
    {
        **F(
            "agent_nominated",
            "Agent Nominated (Client-to-Agent Linking)",
            "checkbox",
            default_value=False,
            track_history=True,
            help_text="Business clients nominate the practice in ATO Online services for business.",
        ),
        "object": "account",
    },
    {
        **F("engagement", "Engagement", "lookup", target="engagement", delete_rule="clear"),
        "object": "invoice",
    },
]

APP: Final[dict[str, Any]] = {
    "key": APP_KEY, "label": "Accounting Practice", "icon": "calculator", "color": "#6d28d9", "sort_order": 5,
    "description": "Clients, engagements, engagement letters, lodgement deadlines and WIP.",
    "tabs": [{"kind": "home"}, {"kind": "object", "object": "lead"}, {"kind": "object", "object": "account"},
             {"kind": "object", "object": "contact"}, {"kind": "object", "object": "engagement"},
             {"kind": "object", "object": "lodgement_deadline"}, {"kind": "object", "object": "engagement_time_entry"},
             {"kind": "object", "object": "invoice"}, {"kind": "calendar"}, {"kind": "reports"}, {"kind": "dashboards"}],
}  # fmt: skip

_OPEN = {"logic": "and", "conditions": [{"field": "stage", "op": "not_equals", "value": "Complete"}]}
_DUE = {"logic": "and", "conditions": [{"field": "status", "op": "in", "value": ["Upcoming", "Overdue"]}]}
LIST_VIEWS: Final[list[dict[str, Any]]] = [
    {"key": "engagement_all", "object": "engagement", "name": "All Engagements", "columns": ENGAGEMENT["list_columns"], "kanban_field": "stage"},
    {"key": "engagement_mine", "object": "engagement", "name": "My Engagements", "scope": "mine", "columns": ENGAGEMENT["list_columns"], "kanban_field": "stage", "filters": _OPEN},
    {"key": "engagement_open", "object": "engagement", "name": "Open Engagements", "columns": ENGAGEMENT["list_columns"], "kanban_field": "stage", "filters": _OPEN,
     "sort": [{"field": "due_date", "direction": "asc"}]},
    {"key": "engagement_review", "object": "engagement", "name": "Awaiting Review", "columns": ENGAGEMENT["list_columns"],
     "filters": {"logic": "and", "conditions": [{"field": "stage", "op": "equals", "value": "Review"}]}},
    {"key": "lodgement_deadline_due", "object": "lodgement_deadline", "name": "Upcoming and Overdue", "columns": DEADLINE["list_columns"], "filters": _DUE,
     "sort": [{"field": "due_date", "direction": "asc"}]},
    {"key": "engagement_time_entry_mine", "object": "engagement_time_entry", "name": "My Timesheet", "scope": "mine", "columns": TIME_ENTRY["list_columns"],
     "sort": [{"field": "entry_date", "direction": "desc"}]},
]  # fmt: skip

PACK_OBJECTS: Final = [
    "engagement",
    "engagement_letter",
    "lodgement_deadline",
    "document_request",
    "engagement_time_entry",
]


def bundle() -> dict[str, Any]:
    return {
        "objects": [ENGAGEMENT, LETTER, DEADLINE, DOCUMENT_REQUEST, TIME_ENTRY],
        "fields": STANDARD_FIELDS,
        "apps": [APP],
        "list_views": LIST_VIEWS,
    }


PROFILES: Final[list[ProfileSpec]] = [
    ("ap_partner", "Partner", "Runs the practice: every client and engagement, review and lodgement, WIP and billing.", "sales_manager",
     {"engagement": "RCED VA MA", "engagement_letter": "RCED VA MA", "lodgement_deadline": "RCED VA MA", "document_request": "RCED VA MA",
      "engagement_time_entry": "RCED VA MA", "invoice": "RCE VA MA", "payment": "RC VA", "account": "RCED VA MA", "contact": "RCED VA MA"},
     ("manage_portal_users", "transfer_records", "export_data", "import_data", "manage_public_reports"), (LODGE,)),
    ("ap_accountant", "Accountant", "Registered tax agent staff: prepares and lodges returns, letters and document requests.", "sales_representative",
     {"engagement": "RCE", "engagement_letter": "RCE", "lodgement_deadline": "RCE", "document_request": "RCED",
      "engagement_time_entry": "RCE", "invoice": "RCE"}, ("manage_portal_users",), (LODGE,)),
    ("ap_bookkeeper", "Bookkeeper", "Bookkeeping and BAS preparation on assigned clients.", "service_agent",
     {"engagement": "RE", "document_request": "RCE", "lodgement_deadline": "RE", "engagement_time_entry": "RCE"}, (), ()),
    ("ap_practice_admin", "Practice Administrator", "Client onboarding, engagement letters, invoices and payments.", "finance",
     {"engagement": "RC VA", "engagement_letter": "RCE VA", "lodgement_deadline": "RCE VA", "document_request": "RCE VA",
      "engagement_time_entry": "R VA", "account": "RCE VA", "contact": "RCE VA"}, ("manage_portal_users",), ()),
]  # fmt: skip

# Added on upgrade to workspaces that already have the pack (see app.pack_upgrade).
NEW_ON_FORMS: Final = [
    ("engagement", "noa_date", "ato_reference"),
    ("engagement", "noa_amount", "noa_date"),
    ("engagement_letter", "practitioner", "valid_until"),
    ("engagement_letter", "tax_agent_number", "practitioner"),
    ("account", "identity_verified", "client_manager"),
    ("account", "identity_verified_date", "identity_verified"),
    ("account", "agent_nominated", "identity_verified_date"),
]
INDIVIDUAL_ENTITIES: Final = {"Individual", "Sole Trader"}

RETURN_DUE: Final[dict[str, str]] = {
    "Individual Tax Return": "31-10", "Company Tax Return": "28-02", "Trust Tax Return": "31-03",
    "Partnership Tax Return": "31-03", "SMSF Annual Return": "28-02", "FBT Return": "21-05",
}  # fmt: skip
SETTINGS_DEFAULTS: Final[dict[str, Any]] = {
    "default_charge_out_rate": 220,
    "deadline_reminder_days": [14, 3, 0],
    "letter_required": True,
    "tax_agent_number": "",
    "bas_due_dates": "standard",
    # Default due dates (DD-MM after the period ends); confirm against the tax agent lodgment program.
    "return_due": dict(RETURN_DUE),
}
SETTINGS_FIELDS: Final[list[dict[str, Any]]] = [
    {"key": "tax_agent_number", "label": "Practice tax agent number", "kind": "text",
     "hint": "The practice's TPB registration, shown on engagement letters when the practitioner has no number of their own."},
    {"key": "default_charge_out_rate", "label": "Default charge-out rate", "kind": "currency"},
    {"key": "letter_required", "label": "Engagement letter before work starts (APES 305)", "kind": "checkbox"},
    {"key": "bas_due_dates", "label": "BAS due dates", "kind": "select",
     "options": [{"value": "standard", "label": "Standard ATO dates"},
                 {"value": "tax_agent", "label": "Tax agent lodgment program (quarterly concession)"}],
     "hint": "The concession gives quarterly BAS lodged electronically through an agent more time (e.g. Q1 on 25 November)."},
    {"key": "deadline_reminder_days", "label": "Lodgement deadline reminders (days before)", "kind": "days"},
    *[{"key": f"return_due.{kind}", "label": f"{kind} due (DD-MM)", "kind": "text",
       "hint": "After the year ends (30 June; 31 March for FBT)."} for kind in RETURN_DUE],
]  # fmt: skip

REPORT_FOLDER: Final = "accounting_reports"
_UNBILLED = {
    "logic": "and",
    "conditions": [
        {"field": "status", "op": "equals", "value": "Unbilled"},
        {"field": "billable", "op": "equals", "value": True},
    ],
}
REPORTS: Final[list[tuple[str, str, str, dict[str, Any]]]] = [
    ("ap_engagements_by_stage", "Open Engagements by Stage", "engagement", {"format": "summary", "group_by": ["stage"], "aggregates": [{"op": "count"}], "filters": _OPEN, "chart": {"type": "funnel"}}),
    ("ap_engagements_by_type", "Engagements by Type", "engagement", {"format": "summary", "group_by": ["type"], "aggregates": [{"op": "count"}], "filters": _OPEN, "chart": {"type": "bar"}}),
    ("ap_workload", "Workload by Accountant", "engagement", {"format": "summary", "group_by": ["responsible_accountant"], "aggregates": [{"op": "count"}], "filters": _OPEN, "chart": {"type": "bar"}}),
    ("ap_wip", "Work in Progress (Unbilled Time)", "engagement_time_entry", {"format": "summary", "group_by": ["engagement"], "aggregates": [{"op": "sum", "field": "amount"}, {"op": "sum", "field": "hours"}], "filters": _UNBILLED, "chart": {"type": "bar"}}),
    ("ap_recoverability", "Recoverability by Engagement", "engagement", {"format": "tabular", "columns": ["name", "client", "type", "fee", "time_cost", "recoverability"],
                                                                          "filters": {"logic": "and", "conditions": [{"field": "time_cost", "op": "gt", "value": 0}]}, "sort": [{"field": "recoverability", "direction": "asc"}]}),
    ("ap_upcoming_deadlines", "Lodgement Deadlines (next 30 days)", "lodgement_deadline", {"format": "tabular", "columns": ["name", "client", "lodgement_type", "period", "due_date", "status", "responsible"],
                                                                                            "filters": {"logic": "and", "conditions": [{"field": "status", "op": "in", "value": ["Upcoming", "Overdue"]}, {"field": "due_date", "op": "lte", "value": "NEXT_N_DAYS:30"}]},
                                                                                            "sort": [{"field": "due_date", "direction": "asc"}]}),
    ("ap_overdue", "Overdue Lodgements", "lodgement_deadline", {"format": "summary", "group_by": ["responsible"], "aggregates": [{"op": "count"}],
                                                                "filters": {"logic": "and", "conditions": [{"field": "status", "op": "equals", "value": "Overdue"}]}, "chart": {"type": "bar"}}),
]  # fmt: skip


def install(conn: Connection) -> None:
    install_profiles(conn, KEY, PROFILES)
    for key in ("ap_partner", "ap_accountant", "ap_practice_admin"):
        install_field_security(conn, security_id("profile", key), "account", "tfn", "edit")
    ro = security_id("profile", "read_only")
    for obj in PACK_OBJECTS:
        install_object_permission(conn, ro, obj, {"can_read": True, "view_all": True})
    portal = security_id("profile", "customer_portal")
    for obj in ("engagement", "engagement_letter", "document_request"):
        install_object_permission(conn, portal, obj, {"can_read": True})
    for field in ("reviewer", "time_cost", "unbilled_amount", "recoverability", "description"):
        install_field_security(conn, portal, "engagement", field, "hidden")
    install_field_security(conn, portal, "engagement_letter", "signed_ip", "hidden")
    install_folder(conn, REPORT_FOLDER, "Accounting Practice Reports")
    for key, name, obj, definition in REPORTS:
        install_report(conn, key, REPORT_FOLDER, name, obj, definition, pack_key=KEY)
    install_dashboard(
        conn,
        "ap_practice_dashboard",
        REPORT_FOLDER,
        "Practice Dashboard",
        [
            {
                "report": "ap_engagements_by_stage",
                "title": "Open engagements by stage",
                "chart": "funnel",
                "width": 2,
            },
            {"report": "ap_overdue", "title": "Overdue lodgements", "chart": "bar", "width": 1},
            {"report": "ap_workload", "title": "Workload by accountant", "chart": "bar", "width": 2},
            {"report": "ap_wip", "title": "Work in progress", "chart": "bar", "width": 1},
            {"report": "ap_upcoming_deadlines", "title": "Lodgement deadlines", "chart": "table", "width": 3},
        ],
        "Engagements, deadlines, workload and WIP.",
        pack_key=KEY,
    )
    set_setting(conn, KEY, {**SETTINGS_DEFAULTS, "return_due": dict(RETURN_DUE)})

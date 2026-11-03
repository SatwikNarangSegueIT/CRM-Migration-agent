"""Migration Agency (Australia) pack, version 1.0.0: objects, fields, app, profiles, reports (plan v3, section 11).

Supports compliance with the Code of Conduct for registered migration agents; the principal confirms
against current OMARA guidance.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import Connection, text

from app.engine.installer import (
    install_dashboard,
    install_field_security,
    install_folder,
    install_object_permission,
    install_report,
    set_setting,
    stable_id,
)
from app.engine.standard_v1 import SYSTEM_SECTION, F, P, related, section
from app.packs import grant, permission_key
from app.security.seed_v1 import _flags
from app.security.seed_v1 import stable_id as security_id

KEY: Final = "migration_agency"
VERSION: Final = "1.0.0"
LODGE: Final = "lodge_applications"
OVERRIDE: Final = "override_agreement_gate"

STAGES: Final[list[dict[str, Any]]] = [
    P("Consultation", "#94a3b8"), P("Service Agreement", "#60a5fa"), P("Document Collection", "#38bdf8"),
    P("Preparation", "#a78bfa"), P("Ready to Lodge", "#f59e0b"), P("Lodged", "#0ea5e9"),
    P("Further Information", "#f97316"), P("Decision", "#16a34a", closed=True),
]  # fmt: skip
STAGE_ORDER: Final = [s["value"] for s in STAGES]
LODGE_STAGES: Final[set[str]] = {"Lodged", "Further Information", "Decision"}

VISA_TYPE: Final[dict[str, Any]] = {
    "api_name": "visa_type", "label": "Visa Type", "plural_label": "Visa Types", "icon": "passport", "color": "#0d9488",
    "sharing": "read", "allow_activities": False,
    "fields": [
        F("subclass", "Subclass", "text", max_length=10, required=True, searchable=True, indexed=True),
        F("stream", "Stream", "text", max_length=80),
        F("category", "Category", "picklist", values=["Skilled", "Employer Sponsored", "Family", "Student", "Visitor", "Business", "Humanitarian", "Other"]),
        F("default_professional_fee", "Default Professional Fee", "currency"),
        F("default_government_fee", "Default Government Fee (VAC)", "currency"),
        F("checklist_template", "Document Checklist", "long_text", help_text="One document per line. Copied to each new matter."),
        F("is_active", "Active", "checkbox", default_value=True),
        F("description", "Description", "long_text"),
    ],
    "page_layout": [section("Visa Type", ["name", "subclass", "stream", "category", "is_active"]),
                    section("Fees", ["default_professional_fee", "default_government_fee"]),
                    section("Checklist", ["checklist_template", "description"], 1), SYSTEM_SECTION],
    "compact_layout": ["subclass", "stream", "category", "is_active"],
    "list_columns": ["name", "subclass", "stream", "category", "is_active"],
    "related_lists": [related("matter", "visa_type", "Matters", ["name", "client", "stage", "status"])],
}  # fmt: skip

MATTER: Final[dict[str, Any]] = {
    "api_name": "matter", "label": "Matter", "plural_label": "Matters", "icon": "matter", "color": "#0f766e",
    "sharing": "private", "name_field_type": "auto_number", "name_label": "Matter Number", "name_format": "MAT-{YYYY}-{0000}",
    "show_in_portal": True, "portal_fields": ["client"],
    "fields": [
        F("client", "Client", "lookup", target="contact", required=True, delete_rule="restrict", indexed=True, track_history=True),
        F("sponsor", "Sponsor", "lookup", target="account", delete_rule="clear"),
        F("visa_type", "Visa Type", "lookup", target="visa_type", delete_rule="restrict", track_history=True),
        F("stage", "Stage", "picklist", is_path=True, track_history=True, indexed=True, values=STAGES, default="Consultation"),
        F("status", "Status", "picklist", values=[P("Active", "#16a34a"), P("On Hold", "#f59e0b"), P("Closed", "#64748b"), P("Withdrawn", "#dc2626")], default="Active", track_history=True),
        F("priority", "Priority", "picklist", values=["Low", "Normal", "High", "Urgent"], default="Normal"),
        F("location", "Applicant Location", "picklist", values=["Onshore", "Offshore"]),
        F("responsible_rma", "Responsible RMA", "user", track_history=True, indexed=True),
        F("case_officer", "Case Officer", "user", track_history=True),
        F("immi_trn", "ImmiAccount TRN", "text", max_length=40, searchable=True),
        F("lodgement_date", "Lodgement Date", "date", is_readonly=True),
        F("decision_date", "Decision Date", "date"),
        F("outcome", "Outcome", "picklist", values=[P("Granted", "#16a34a"), P("Refused", "#dc2626"), P("Withdrawn", "#64748b"), P("Invalid", "#f59e0b")], track_history=True),
        F("grant_number", "Grant Number", "text", max_length=40),
        F("visa_expiry", "Visa Expiry", "date", indexed=True),
        F("processing_days", "Processing Time (days)", "number", is_readonly=True),
        F("professional_fee", "Professional Fee", "currency"),
        F("government_fee", "Government Fee (VAC)", "currency"),
        F("agreement_override", "Agreement Gate Overridden", "checkbox", default_value=False, is_readonly=True),
        F("description", "Notes", "long_text"),
    ],
    "page_layout": [
        section("Matter", ["name", "client", "sponsor", "visa_type", "stage", "status", "priority", "location", "owner_id"]),
        section("Team", ["responsible_rma", "case_officer"]),
        section("Lodgement & Decision", ["immi_trn", "lodgement_date", "decision_date", "outcome", "grant_number", "visa_expiry", "processing_days"]),
        section("Fees", ["professional_fee", "government_fee", "agreement_override"]),
        section("Notes", ["description"], 1),
        SYSTEM_SECTION,
    ],
    "compact_layout": ["client", "visa_type", "stage", "responsible_rma", "status"],
    "list_columns": ["name", "client", "visa_type", "stage", "status", "responsible_rma"],
    "related_lists": [
        related("matter_applicant", "matter", "Applicants", ["contact", "role"]),
        related("checklist_item", "matter", "Document Checklist", ["name", "status", "due_date", "is_public"]),
        related("service_agreement", "matter", "Service Agreements", ["name", "status", "professional_fee", "signed_at"]),
        related("client_account_transaction", "matter", "Client Account", ["name", "type", "amount", "transaction_date", "balance_after"]),
        related("invoice", "matter", "Invoices", ["name", "status", "total", "balance"]),
    ],
}  # fmt: skip

MATTER_APPLICANT: Final[dict[str, Any]] = {
    "api_name": "matter_applicant", "label": "Matter Applicant", "plural_label": "Matter Applicants", "icon": "member",
    "color": "#0f766e", "is_detail_only": True, "allow_activities": False, "allow_files": False, "allow_notes": False,
    "searchable": False, "sharing": "controlled_by_parent",
    "fields": [
        F("matter", "Matter", "master_detail", target="matter", required=True),
        F("contact", "Applicant", "lookup", target="contact", required=True, delete_rule="restrict"),
        F("role", "Role", "picklist", values=["Primary", "Secondary", "Dependent", "Sponsor", "Nominator"], default="Primary"),
    ],
    "page_layout": [section("Applicant", ["matter", "contact", "role"])],
    "list_columns": ["contact", "role"],
}  # fmt: skip

CHECKLIST_ITEM: Final[dict[str, Any]] = {
    "api_name": "checklist_item", "label": "Checklist Item", "plural_label": "Checklist Items", "icon": "checklist",
    "color": "#0f766e", "is_detail_only": True, "allow_activities": False, "allow_notes": False, "searchable": False,
    "sharing": "controlled_by_parent", "show_in_portal": True,
    "fields": [
        F("matter", "Matter", "master_detail", target="matter", required=True),
        F("status", "Status", "picklist", values=[P("Requested", "#94a3b8"), P("Received", "#60a5fa"), P("Approved", "#16a34a"), P("Not Required", "#64748b")], default="Requested", track_history=True),
        F("due_date", "Due Date", "date"),
        F("notes", "Notes", "textarea"),
        F("is_public", "Visible to Client", "checkbox", default_value=True),
        F("sort_order", "Order", "number"),
    ],
    "page_layout": [section("Item", ["name", "matter", "status", "due_date", "is_public", "sort_order", "notes"])],
    "list_columns": ["name", "status", "due_date", "is_public"],
}  # fmt: skip

SERVICE_AGREEMENT: Final[dict[str, Any]] = {
    "api_name": "service_agreement", "label": "Service Agreement", "plural_label": "Service Agreements", "icon": "agreement",
    "color": "#0f766e", "is_detail_only": True, "allow_activities": False, "sharing": "controlled_by_parent",
    "show_in_portal": True, "name_field_type": "auto_number", "name_label": "Agreement Number", "name_format": "SA-{00000}",
    "fields": [
        F("matter", "Matter", "master_detail", target="matter", required=True),
        F("scope", "Scope of Services", "long_text", required=True),
        F("professional_fee", "Professional Fee", "currency", required=True, min=0),
        F("government_fee", "Government Fee (VAC)", "currency", min=0),
        F("estimated_disbursements", "Estimated Disbursements", "currency", min=0),
        F("consumer_guide_provided", "Consumer Guide Provided", "checkbox", default_value=False, track_history=True),
        F("status", "Status", "picklist", is_path=True, is_readonly=True, values=[P("Draft", "#94a3b8"), P("Sent", "#60a5fa"), P("Signed", "#16a34a", closed=True), P("Cancelled", "#64748b", closed=True)], default="Draft"),
        F("sent_at", "Sent", "datetime", is_readonly=True),
        F("signed_name", "Signed By", "text", max_length=120, is_readonly=True),
        F("signed_at", "Signed", "datetime", is_readonly=True),
        F("signed_ip", "Signed From IP", "text", max_length=45, is_readonly=True),
    ],
    "page_layout": [section("Agreement", ["name", "matter", "status", "consumer_guide_provided"]),
                    section("Fees", ["professional_fee", "government_fee", "estimated_disbursements"]),
                    section("Scope", ["scope"], 1),
                    section("Signature", ["sent_at", "signed_name", "signed_at", "signed_ip"]), SYSTEM_SECTION],
    "compact_layout": ["matter", "status", "professional_fee", "signed_at"],
    "list_columns": ["name", "matter", "status", "professional_fee", "signed_at"],
}  # fmt: skip

TRANSACTION: Final[dict[str, Any]] = {
    "api_name": "client_account_transaction", "label": "Client Account Transaction", "plural_label": "Client Account",
    "icon": "ledger", "color": "#0f766e", "sharing": "private", "allow_activities": False, "allow_notes": False,
    "name_field_type": "auto_number", "name_label": "Transaction Number", "name_format": "TRX-{000000}",
    "fields": [
        F("client", "Client", "lookup", target="contact", required=True, delete_rule="restrict", indexed=True),
        F("matter", "Matter", "lookup", target="matter", delete_rule="restrict"),
        F("type", "Type", "picklist", required=True, values=["Deposit", "Withdrawal", "Transfer to Office"]),
        F("amount", "Amount", "currency", required=True, min=0.01),
        F("signed_amount", "Ledger Amount", "currency", is_readonly=True, help_text="Positive for deposits, negative for withdrawals and transfers."),
        F("transaction_date", "Date", "date", required=True, default_value="today"),
        F("reference", "Reference", "text", max_length=80),
        F("invoice", "Invoice", "lookup", target="invoice", delete_rule="restrict"),
        F("balance_after", "Client Balance After", "currency", is_readonly=True),
        F("description", "Description", "textarea"),
    ],
    "page_layout": [section("Transaction", ["name", "client", "matter", "type", "amount", "transaction_date", "reference", "invoice", "balance_after", "description"]), SYSTEM_SECTION],
    "compact_layout": ["client", "type", "amount", "transaction_date", "balance_after"],
    "list_columns": ["name", "client", "matter", "type", "amount", "transaction_date", "balance_after"],
}  # fmt: skip

STANDARD_FIELDS: Final[list[dict[str, Any]]] = [
    {**F("citizenship", "Citizenship", "text", max_length=80), "object": "contact"},
    {**F("country_of_birth", "Country of Birth", "text", max_length=80), "object": "contact"},
    {
        **F("passport_number", "Passport Number", "encrypted_text", max_length=40, default_access="hidden"),
        "object": "contact",
    },
    {**F("passport_expiry", "Passport Expiry", "date", indexed=True), "object": "contact"},
    {**F("current_visa", "Current Visa", "text", max_length=80), "object": "contact"},
    {**F("current_visa_expiry", "Current Visa Expiry", "date", indexed=True), "object": "contact"},
    {**F("in_australia", "In Australia", "checkbox", default_value=False), "object": "contact"},
    {
        **F("privacy_consent", "Privacy Act Consent", "checkbox", default_value=False, track_history=True),
        "object": "contact",
    },
    {**F("privacy_consent_date", "Privacy Consent Date", "date"), "object": "contact"},
    {**F("is_sponsor", "Approved Sponsor", "checkbox", default_value=False), "object": "account"},
    {**F("sponsorship_approval_date", "Sponsorship Approved", "date"), "object": "account"},
    {**F("sponsorship_expiry", "Sponsorship Expiry", "date", indexed=True), "object": "account"},
    {**F("matter", "Matter", "lookup", target="matter", delete_rule="clear"), "object": "invoice"},
]

APP: Final[dict[str, Any]] = {
    "key": "migration_practice", "label": "Migration Practice", "icon": "passport", "color": "#0f766e", "sort_order": 5,
    "description": "Matters, visa types, client accounts and the practice's clients.",
    "tabs": [{"kind": "home"}, {"kind": "object", "object": "lead"}, {"kind": "object", "object": "contact"},
             {"kind": "object", "object": "account"}, {"kind": "object", "object": "matter"}, {"kind": "object", "object": "visa_type"},
             {"kind": "object", "object": "invoice"}, {"kind": "object", "object": "client_account_transaction"},
             {"kind": "calendar"}, {"kind": "reports"}],
}  # fmt: skip

LIST_VIEWS: Final[list[dict[str, Any]]] = [
    {"key": "matter_all", "object": "matter", "name": "All Matters", "columns": MATTER["list_columns"], "kanban_field": "stage"},
    {"key": "matter_mine", "object": "matter", "name": "My Matters", "scope": "mine", "columns": MATTER["list_columns"], "kanban_field": "stage"},
    {"key": "matter_active", "object": "matter", "name": "Active Matters", "columns": MATTER["list_columns"], "kanban_field": "stage",
     "filters": {"logic": "and", "conditions": [{"field": "status", "op": "equals", "value": "Active"}]}},
    {"key": "matter_expiring", "object": "matter", "name": "Visas Expiring (90 days)", "columns": ["name", "client", "visa_type", "visa_expiry", "responsible_rma"],
     "filters": {"logic": "and", "conditions": [{"field": "visa_expiry", "op": "equals", "value": "NEXT_N_DAYS:90"}]},
     "sort": [{"field": "visa_expiry", "direction": "asc"}]},
    {"key": "visa_type_all", "object": "visa_type", "name": "All Visa Types", "columns": VISA_TYPE["list_columns"], "sort": [{"field": "subclass", "direction": "asc"}]},
    {"key": "client_account_transaction_all", "object": "client_account_transaction", "name": "All Transactions",
     "columns": TRANSACTION["list_columns"], "sort": [{"field": "created_at", "direction": "desc"}]},
]  # fmt: skip

PACK_OBJECTS: Final = [
    "visa_type",
    "matter",
    "matter_applicant",
    "checklist_item",
    "service_agreement",
    "client_account_transaction",
]


def bundle() -> dict[str, Any]:
    return {
        "objects": [VISA_TYPE, MATTER, MATTER_APPLICANT, CHECKLIST_ITEM, SERVICE_AGREEMENT, TRANSACTION],
        "fields": STANDARD_FIELDS,
        "apps": [APP],
        "list_views": LIST_VIEWS,
    }


# Pack profiles: (key, name, description, base profile, {object: code}, system permissions, custom permissions)
PROFILES: Final = [
    ("ma_practice_manager", "Practice Manager", "Runs the practice: sales manager rights, finance read and every matter.", "sales_manager",
     {"matter": "RCED VA", "matter_applicant": "RCED VA", "checklist_item": "RCED VA", "service_agreement": "RCED VA",
      "visa_type": "RCED", "client_account_transaction": "R VA", "invoice": "R VA", "payment": "R VA", "product": "R"},
     ("manage_portal_users", "transfer_records", "export_data", "import_data", "manage_public_reports"), (LODGE, OVERRIDE)),
    ("ma_registered_agent", "Registered Migration Agent", "Registered migration agent (MARA): all matters, lodgement, agreements.", "sales_representative",
     {"matter": "RCE VA", "matter_applicant": "RCED VA", "checklist_item": "RCED VA", "service_agreement": "RCE VA",
      "visa_type": "R", "client_account_transaction": "R", "invoice": "RCE"}, ("manage_portal_users",), (LODGE,)),
    ("ma_case_officer", "Case Officer", "Works matters where they are case officer or responsible RMA.", "service_agent",
     {"matter": "RE", "matter_applicant": "RCE", "checklist_item": "RCED", "service_agreement": "R", "visa_type": "R"}, (), ()),
    ("ma_intake", "Intake Consultant", "Handles enquiries: own leads, contacts and lead conversion.", "sales_representative",
     {"matter": "RC", "visa_type": "R"}, (), ()),
    ("ma_accounts", "Accounts", "Finance plus the client account (trust) ledger.", "finance",
     {"matter": "R VA", "client_account_transaction": "RCE VA", "visa_type": "R"}, (), ()),
    ("ma_auditor", "Practice Auditor", "Reads all data including the client account; changes nothing.", "read_only",
     dict.fromkeys(PACK_OBJECTS, "R VA"), (), ()),
]  # fmt: skip

REPORT_FOLDER: Final = "migration_reports"
REPORTS: Final[list[tuple[str, str, str, dict[str, Any]]]] = [
    ("ma_matters_by_stage", "Matters by Stage", "matter", {"format": "summary", "group_by": ["stage"], "aggregates": [{"op": "count"}],
                                                           "filters": {"logic": "and", "conditions": [{"field": "status", "op": "equals", "value": "Active"}]}, "chart": {"type": "funnel"}}),
    ("ma_matters_by_visa", "Matters by Visa Type", "matter", {"format": "summary", "group_by": ["visa_type"], "aggregates": [{"op": "count"}], "chart": {"type": "bar"}}),
    ("ma_outcomes", "Grant Rate", "matter", {"format": "summary", "group_by": ["outcome"], "aggregates": [{"op": "count"}],
                                             "filters": {"logic": "and", "conditions": [{"field": "outcome", "op": "is_not_null"}]}, "chart": {"type": "donut"}}),
    ("ma_processing_time", "Processing Time by Visa Type", "matter", {"format": "summary", "group_by": ["visa_type"],
                                                                      "aggregates": [{"op": "avg", "field": "processing_days"}, {"op": "count"}],
                                                                      "filters": {"logic": "and", "conditions": [{"field": "processing_days", "op": "is_not_null"}]}, "chart": {"type": "bar"}}),
    ("ma_client_balances", "Client Account Balances", "client_account_transaction", {"format": "summary", "group_by": ["client"],
                                                                                    "aggregates": [{"op": "sum", "field": "signed_amount"}, {"op": "count"}], "chart": {"type": "bar"}}),
    ("ma_upcoming_expiries", "Upcoming Visa Expiries", "matter", {"format": "tabular", "columns": ["name", "client", "visa_type", "visa_expiry", "responsible_rma"],
                                                                  "filters": {"logic": "and", "conditions": [{"field": "visa_expiry", "op": "equals", "value": "NEXT_N_DAYS:90"}]},
                                                                  "sort": [{"field": "visa_expiry", "direction": "asc"}]}),
    ("ma_agent_workload", "Agent Workload", "matter", {"format": "summary", "group_by": ["responsible_rma"], "aggregates": [{"op": "count"}],
                                                      "filters": {"logic": "and", "conditions": [{"field": "status", "op": "equals", "value": "Active"}]}, "chart": {"type": "bar"}}),
]  # fmt: skip


def install(conn: Connection) -> None:
    for key, name, description, base, objects, system, custom in PROFILES:
        pid = security_id("profile", key)
        conn.execute(
            text(
                "INSERT INTO profiles (id, key, name, description, is_locked, is_portal, created_at, updated_at) "
                "VALUES (:id, :key, :name, :description, false, false, now(), now()) ON CONFLICT DO NOTHING"
            ),
            {"id": pid, "key": key, "name": name, "description": description},
        )
        base_id = security_id("profile", base)
        conn.execute(
            text(
                "INSERT INTO profile_object_permissions (profile_id, object_api_name, can_read, can_create, can_edit, can_delete, view_all, modify_all) "
                "SELECT :pid, object_api_name, can_read, can_create, can_edit, can_delete, view_all, modify_all "
                "FROM profile_object_permissions WHERE profile_id = :base ON CONFLICT DO NOTHING"
            ),
            {"pid": pid, "base": base_id},
        )
        conn.execute(
            text(
                "INSERT INTO profile_system_permissions (profile_id, permission) SELECT :pid, permission FROM profile_system_permissions "
                "WHERE profile_id = :base AND permission NOT LIKE 'pack:%' ON CONFLICT DO NOTHING"
            ),
            {"pid": pid, "base": base_id},
        )
        conn.execute(
            text(
                "INSERT INTO profile_field_permissions (profile_id, object_api_name, field_api_name, access) SELECT :pid, object_api_name, "
                "field_api_name, access FROM profile_field_permissions WHERE profile_id = :base ON CONFLICT DO NOTHING"
            ),
            {"pid": pid, "base": base_id},
        )
        for obj, code in objects.items():
            # Upsert: pack grants override the copied base row for these objects.
            flags = _flags(code)
            conn.execute(
                text(
                    "INSERT INTO profile_object_permissions (profile_id, object_api_name, can_read, can_create, can_edit, can_delete, view_all, modify_all) "
                    "VALUES (:p, :o, :r, :c, :e, :d, :va, :ma) ON CONFLICT (profile_id, object_api_name) DO UPDATE SET can_read = EXCLUDED.can_read, "
                    "can_create = EXCLUDED.can_create, can_edit = EXCLUDED.can_edit, can_delete = EXCLUDED.can_delete, view_all = EXCLUDED.view_all, "
                    "modify_all = EXCLUDED.modify_all"
                ),
                {
                    "p": pid,
                    "o": obj,
                    "r": flags["can_read"],
                    "c": flags["can_create"],
                    "e": flags["can_edit"],
                    "d": flags["can_delete"],
                    "va": flags["view_all"],
                    "ma": flags["modify_all"],
                },
            )
        for perm in system:
            grant(conn, pid, perm)
        for perm in custom:
            grant(conn, pid, permission_key(KEY, perm))
        if key in ("ma_registered_agent", "ma_practice_manager", "ma_auditor", "ma_accounts"):
            install_field_security(
                conn, pid, "contact", "passport_number", "edit" if key != "ma_auditor" else "read"
            )
    # Default profiles: auditors read everything; portal clients see their matters, checklist and agreements.
    ro = security_id("profile", "read_only")
    for obj in PACK_OBJECTS:
        install_object_permission(conn, ro, obj, {"can_read": True, "view_all": True})
    portal = security_id("profile", "customer_portal")
    for obj in ("matter", "checklist_item", "service_agreement", "matter_applicant"):
        install_object_permission(conn, portal, obj, {"can_read": True})
    for field in (
        "case_officer",
        "responsible_rma",
        "professional_fee",
        "government_fee",
        "agreement_override",
        "description",
        "processing_days",
    ):
        install_field_security(conn, portal, "matter", field, "hidden")
    install_field_security(conn, portal, "checklist_item", "notes", "read")
    install_field_security(conn, portal, "service_agreement", "signed_ip", "hidden")
    for p in ("service_agent", "marketing_user", "customer_portal", "sales_representative", "finance"):
        install_field_security(conn, security_id("profile", p), "contact", "passport_number", "hidden")
    install_folder(conn, REPORT_FOLDER, "Migration Practice Reports")
    for key, name, obj, definition in REPORTS:
        install_report(conn, key, REPORT_FOLDER, name, obj, definition, pack_key=KEY)
    install_dashboard(
        conn,
        "ma_practice_dashboard",
        REPORT_FOLDER,
        "Practice Dashboard",
        [
            {
                "report": "ma_matters_by_stage",
                "title": "Active matters by stage",
                "chart": "funnel",
                "width": 2,
            },
            {"report": "ma_outcomes", "title": "Grant rate", "chart": "donut", "width": 1},
            {"report": "ma_agent_workload", "title": "Agent workload", "chart": "bar", "width": 2},
            {"report": "ma_matters_by_visa", "title": "Matters by visa type", "chart": "bar", "width": 1},
            {
                "report": "ma_upcoming_expiries",
                "title": "Upcoming visa expiries",
                "chart": "table",
                "width": 3,
            },
        ],
        "Matters, outcomes, workload and expiries.",
        pack_key=KEY,
    )
    set_setting(
        conn,
        "migration_agency",
        {"retention_years": 7, "expiry_reminder_days": [90, 30], "consumer_guide_required": True},
    )
    _ = stable_id

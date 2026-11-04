"""Loan Broker (Australia) pack, version 1.0.0 (plan v4, section 6).

Loan applications from enquiry to settlement, lender panel, fact finds, commissions (upfront, trail,
clawback) and NCCP / Best Interests Duty records. The pack supports compliance; the licensee confirms
against current ASIC guidance.
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

KEY: Final = "loan_broker"
VERSION: Final = "1.1.0"
APP_KEY: Final = "loan_broking"
SUBMIT: Final = "submit_to_lender"
COMMISSIONS: Final = "manage_commissions"

STAGES: Final[list[dict[str, Any]]] = [
    P("Enquiry", "#94a3b8"), P("Fact Find", "#60a5fa"), P("Preliminary Assessment", "#38bdf8"), P("Lodged", "#a78bfa"),
    P("Conditional Approval", "#f59e0b"), P("Valuation", "#fb923c"), P("Unconditional", "#22c55e"),
    P("Settlement", "#0ea5e9"), P("Settled", "#16a34a", closed=True), P("Declined", "#dc2626", closed=True),
]  # fmt: skip
STAGE_ORDER: Final = [s["value"] for s in STAGES]
FINAL_STAGES: Final = {"Settled", "Declined"}
PURPOSES: Final = [
    "Purchase - Owner Occupied", "Purchase - Investment", "Refinance", "Construction", "Equity Release",
    "First Home Buyer", "Commercial", "Car / Asset Finance", "Personal",
]  # fmt: skip

LOAN: Final[dict[str, Any]] = {
    "api_name": "loan_application", "label": "Loan Application", "plural_label": "Loan Applications", "icon": "home",
    "color": "#b45309", "sharing": "private", "name_field_type": "auto_number", "name_label": "Application Number",
    "name_format": "LA-{YYYY}-{0000}", "show_in_portal": True, "portal_fields": ["primary_borrower", "co_borrower"],
    "fields": [
        F("primary_borrower", "Primary Borrower", "lookup", target="contact", required=True, delete_rule="restrict", indexed=True, track_history=True),
        F("co_borrower", "Co-borrower", "lookup", target="contact", delete_rule="clear"),
        F("purpose", "Purpose", "picklist", required=True, values=PURPOSES, indexed=True),
        F("stage", "Stage", "picklist", is_path=True, track_history=True, indexed=True, values=STAGES, default="Enquiry"),
        F("loan_amount", "Loan Amount", "currency", required=True, min=0, track_history=True),
        F("security_value", "Security Value", "currency", min=0),
        F("security_address", "Security Property", "text", max_length=255),
        F("lvr", "LVR", "percent", is_readonly=True),
        F("lmi_likely", "LMI Likely (LVR over 80%)", "checkbox", default_value=False, is_readonly=True),
        F("lender", "Lender", "lookup", target="lender", delete_rule="restrict", track_history=True, indexed=True),
        F("product", "Product", "text", max_length=120),
        F("interest_rate", "Interest Rate", "percent", scale=2),
        F("rate_type", "Rate Type", "picklist", values=["Variable", "Fixed", "Split"]),
        F("fixed_rate_expiry", "Fixed Rate Expiry", "date", indexed=True),
        F("term_years", "Term (years)", "number", min=1, max=40),
        F("repayment_type", "Repayments", "picklist", values=["Principal & Interest", "Interest Only"]),
        F("assessment_rate", "Assessment Rate", "percent", scale=2, is_readonly=True,
          help_text="The interest rate plus the practice's serviceability buffer."),
        F("estimated_repayment", "Monthly Repayment at Assessment Rate", "currency", is_readonly=True,
          help_text="Principal and interest over the term, used in the preliminary assessment."),
        F("broker", "Broker", "user", track_history=True, indexed=True),
        F("processor", "Loan Processor", "user"),
        F("lender_reference", "Lender Reference", "text", max_length=60, searchable=True),
        F("credit_guide_date", "Credit Guide Provided", "date", track_history=True),
        F("privacy_consent_date", "Privacy / Credit Check Consent", "date", track_history=True),
        F("broker_fee", "Broker Fee to Client", "currency", min=0,
          help_text="A fee the client pays the broker needs a credit quote first (NCCP s 114)."),
        F("credit_quote_date", "Credit Quote Given", "date", track_history=True),
        F("credit_proposal_date", "Credit Proposal Disclosure Given", "date", track_history=True,
          help_text="Before applying: the fees, charges and commissions involved (NCCP s 121)."),
        F("customer_objectives", "Requirements and Objectives", "long_text"),
        F("products_considered", "Products Considered", "long_text"),
        F("recommendation_reason", "Why This Product Is in the Client's Best Interests", "long_text"),
        F("bid_completed", "Best Interests Duty Recorded", "checkbox", default_value=False, is_readonly=True, track_history=True),
        F("preliminary_assessment_date", "Preliminary Assessment Completed", "date", is_readonly=True),
        F("lodged_date", "Lodged With Lender", "date", is_readonly=True),
        F("approval_expiry", "Approval Expiry", "date", indexed=True),
        F("settlement_date", "Settlement Date", "date", indexed=True, track_history=True),
        F("rate_review_date", "Next Rate Review", "date", indexed=True),
        F("decline_reason", "Decline Reason", "textarea"),
        F("expected_upfront", "Expected Upfront Commission", "currency", is_readonly=True),
        F("discharged_date", "Discharged / Refinanced Away", "date", is_readonly=True, track_history=True),
    ],
    "page_layout": [
        section("Application", ["name", "primary_borrower", "co_borrower", "purpose", "stage", "broker", "processor", "owner_id"]),
        section("Loan", ["loan_amount", "security_value", "lvr", "lmi_likely", "security_address", "lender", "product", "interest_rate", "rate_type",
                         "fixed_rate_expiry", "term_years", "repayment_type", "assessment_rate", "estimated_repayment", "lender_reference"]),
        section("Credit Compliance (NCCP)", ["credit_guide_date", "privacy_consent_date", "broker_fee", "credit_quote_date", "credit_proposal_date",
                                             "bid_completed", "preliminary_assessment_date"]),
        section("Best Interests Duty", ["customer_objectives", "products_considered", "recommendation_reason"], 1),
        section("Key Dates", ["lodged_date", "approval_expiry", "settlement_date", "rate_review_date", "expected_upfront", "discharged_date", "decline_reason"]),
        SYSTEM_SECTION,
    ],
    "compact_layout": ["primary_borrower", "loan_amount", "lender", "stage", "settlement_date"],
    "list_columns": ["name", "primary_borrower", "purpose", "loan_amount", "lender", "stage", "broker"],
    "related_lists": [
        related("fact_find", "loan_application", "Fact Finds", ["name", "status", "net_position", "monthly_surplus"]),
        related("commission", "loan_application", "Commissions", ["name", "type", "amount", "status", "received_date"]),
    ],
}  # fmt: skip

LENDER: Final[dict[str, Any]] = {
    "api_name": "lender", "label": "Lender", "plural_label": "Lenders", "icon": "building", "color": "#b45309",
    "sharing": "read", "allow_activities": True,
    "fields": [
        F("lender_type", "Type", "picklist", values=["Major Bank", "Bank", "Non-bank", "Credit Union / Mutual", "Private"]),
        F("accreditation_number", "Accreditation / Broker ID", "text", max_length=40),
        F("upfront_rate", "Upfront Commission Rate", "percent", scale=3),
        F("trail_rate", "Trail Commission Rate (p.a.)", "percent", scale=3),
        F("clawback_months", "Clawback Period (months)", "number", min=0, max=36),
        F("clawback_half_after", "Clawback Halves After (months)", "number", min=0, max=36,
          help_text="Many lenders claw back all the upfront commission in the first 12 months and half after that."),
        F("bdm_name", "BDM", "text", max_length=120),
        F("bdm_email", "BDM E-mail", "email"),
        F("bdm_phone", "BDM Phone", "phone"),
        F("is_active", "On Panel", "checkbox", default_value=True),
        F("notes", "Notes", "long_text"),
    ],
    "page_layout": [section("Lender", ["name", "lender_type", "accreditation_number", "is_active"]),
                    section("Commission", ["upfront_rate", "trail_rate", "clawback_months", "clawback_half_after"]),
                    section("Relationship", ["bdm_name", "bdm_email", "bdm_phone", "notes"]), SYSTEM_SECTION],
    "list_columns": ["name", "lender_type", "upfront_rate", "trail_rate", "is_active"],
    "compact_layout": ["lender_type", "upfront_rate", "trail_rate", "clawback_months", "is_active"],
    "related_lists": [related("loan_application", "lender", "Loan Applications", ["name", "primary_borrower", "loan_amount", "stage"])],
}  # fmt: skip

FACT_FIND: Final[dict[str, Any]] = {
    "api_name": "fact_find", "label": "Fact Find", "plural_label": "Fact Finds", "icon": "checklist", "color": "#b45309",
    "is_detail_only": True, "allow_activities": False, "sharing": "controlled_by_parent", "searchable": False,
    "name_field_type": "auto_number", "name_label": "Fact Find", "name_format": "FF-{00000}",
    "fields": [
        F("loan_application", "Loan Application", "master_detail", target="loan_application", required=True),
        F("status", "Status", "picklist", values=[P("Draft", "#94a3b8"), P("Complete", "#16a34a")], default="Draft"),
        F("employment_type", "Employment", "picklist", values=["PAYG Full-time", "PAYG Part-time", "Casual", "Self-employed", "Contractor", "Retired", "Other"]),
        F("gross_annual_income", "Gross Annual Income", "currency", min=0),
        F("other_annual_income", "Other Annual Income", "currency", min=0),
        F("monthly_living_expenses", "Monthly Living Expenses", "currency", min=0),
        F("monthly_commitments", "Monthly Loan / Card Repayments", "currency", min=0),
        F("dependants", "Dependants", "number", min=0, max=20),
        F("total_assets", "Total Assets", "currency", min=0),
        F("total_liabilities", "Total Liabilities", "currency", min=0),
        F("net_position", "Net Position", "currency", is_readonly=True),
        F("monthly_surplus", "Monthly Surplus (before new loan)", "currency", is_readonly=True),
        F("expenses_verified", "Expenses Verified (bank statements)", "checkbox", default_value=False),
        F("notes", "Notes", "long_text"),
    ],
    "page_layout": [section("Fact Find", ["name", "loan_application", "status", "employment_type", "dependants", "expenses_verified"]),
                    section("Income and Expenses", ["gross_annual_income", "other_annual_income", "monthly_living_expenses", "monthly_commitments", "monthly_surplus"]),
                    section("Assets and Liabilities", ["total_assets", "total_liabilities", "net_position"]),
                    section("Notes", ["notes"], 1), SYSTEM_SECTION],
    "list_columns": ["name", "status", "gross_annual_income", "net_position", "monthly_surplus"],
    "compact_layout": ["loan_application", "status", "gross_annual_income", "monthly_surplus", "expenses_verified"],
}  # fmt: skip

COMMISSION: Final[dict[str, Any]] = {
    "api_name": "commission", "label": "Commission", "plural_label": "Commissions", "icon": "ledger", "color": "#b45309",
    "sharing": "private", "allow_activities": False, "allow_notes": False, "searchable": False,
    "name_field_type": "auto_number", "name_label": "Commission No.", "name_format": "COM-{000000}",
    "fields": [
        F("loan_application", "Loan Application", "lookup", target="loan_application", required=True, delete_rule="restrict", indexed=True),
        F("lender", "Lender", "lookup", target="lender", is_readonly=True, delete_rule="restrict", indexed=True),
        F("broker", "Broker", "user", is_readonly=True, indexed=True),
        F("type", "Type", "picklist", required=True, values=["Upfront", "Trail", "Clawback"]),
        F("amount", "Amount", "currency", required=True, min=0.01),
        F("signed_amount", "Ledger Amount", "currency", is_readonly=True),
        F("period", "Statement Period", "date", default_value="today", indexed=True),
        F("status", "Status", "picklist", values=[P("Expected", "#f59e0b"), P("Received", "#16a34a")], default="Expected"),
        F("received_date", "Received", "date"),
        F("reference", "Statement Reference", "text", max_length=80),
    ],
    "page_layout": [section("Commission", ["name", "loan_application", "lender", "broker", "type", "amount", "signed_amount", "period", "status", "received_date", "reference"]), SYSTEM_SECTION],
    "list_columns": ["name", "loan_application", "lender", "type", "amount", "status", "period"],
    "compact_layout": ["loan_application", "lender", "type", "amount", "status"],
}  # fmt: skip

STANDARD_FIELDS: Final[list[dict[str, Any]]] = [
    {**F("date_of_birth", "Date of Birth", "date"), "object": "contact"},
    {
        **F(
            "residency_status",
            "Residency Status",
            "picklist",
            values=["Australian Citizen", "Permanent Resident", "Temporary Visa", "Non-resident"],
        ),
        "object": "contact",
    },
    {**F("first_home_buyer", "First Home Buyer", "checkbox", default_value=False), "object": "contact"},
    {
        **F("id_verified", "ID Verified (100 points)", "checkbox", default_value=False, track_history=True),
        "object": "contact",
    },
    {
        **F(
            "drivers_licence",
            "Driver Licence Number",
            "encrypted_text",
            max_length=20,
            default_access="hidden",
        ),
        "object": "contact",
    },
]

APP: Final[dict[str, Any]] = {
    "key": APP_KEY, "label": "Loan Broking", "icon": "home", "color": "#b45309", "sort_order": 5,
    "description": "Loan applications from enquiry to settlement, lenders, commissions and NCCP records.",
    "tabs": [{"kind": "home"}, {"kind": "object", "object": "lead"}, {"kind": "object", "object": "contact"},
             {"kind": "object", "object": "loan_application"}, {"kind": "object", "object": "lender"},
             {"kind": "object", "object": "commission"}, {"kind": "object", "object": "account"},
             {"kind": "calendar"}, {"kind": "reports"}, {"kind": "dashboards"}],
}  # fmt: skip

_ACTIVE = {
    "logic": "and",
    "conditions": [{"field": "stage", "op": "not_in", "value": ["Settled", "Declined"]}],
}
LIST_VIEWS: Final[list[dict[str, Any]]] = [
    {"key": "loan_application_all", "object": "loan_application", "name": "All Applications", "columns": LOAN["list_columns"], "kanban_field": "stage"},
    {"key": "loan_application_mine", "object": "loan_application", "name": "My Pipeline", "scope": "mine", "columns": LOAN["list_columns"], "kanban_field": "stage", "filters": _ACTIVE},
    {"key": "loan_application_pipeline", "object": "loan_application", "name": "Active Pipeline", "columns": LOAN["list_columns"], "kanban_field": "stage", "filters": _ACTIVE},
    {"key": "loan_application_settling", "object": "loan_application", "name": "Settling (30 days)", "columns": ["name", "primary_borrower", "loan_amount", "lender", "settlement_date", "broker"],
     "filters": {"logic": "and", "conditions": [{"field": "settlement_date", "op": "equals", "value": "NEXT_N_DAYS:30"}]}, "sort": [{"field": "settlement_date", "direction": "asc"}]},
    {"key": "loan_application_fixed_expiry", "object": "loan_application", "name": "Fixed Rates Expiring (90 days)", "columns": ["name", "primary_borrower", "lender", "interest_rate", "fixed_rate_expiry", "broker"],
     "filters": {"logic": "and", "conditions": [{"field": "fixed_rate_expiry", "op": "equals", "value": "NEXT_N_DAYS:90"}]}, "sort": [{"field": "fixed_rate_expiry", "direction": "asc"}]},
    {"key": "lender_panel", "object": "lender", "name": "Lender Panel", "columns": LENDER["list_columns"],
     "filters": {"logic": "and", "conditions": [{"field": "is_active", "op": "equals", "value": True}]}},
    {"key": "commission_expected", "object": "commission", "name": "Expected Commissions", "columns": COMMISSION["list_columns"],
     "filters": {"logic": "and", "conditions": [{"field": "status", "op": "equals", "value": "Expected"}]}, "sort": [{"field": "period", "direction": "asc"}]},
]  # fmt: skip

PACK_OBJECTS: Final = ["loan_application", "lender", "fact_find", "commission"]

# Added on upgrade to workspaces that already have the pack (see app.pack_upgrade).
NEW_ON_FORMS: Final = [
    ("loan_application", "lmi_likely", "lvr"),
    ("loan_application", "assessment_rate", "repayment_type"),
    ("loan_application", "estimated_repayment", "assessment_rate"),
    ("loan_application", "broker_fee", "privacy_consent_date"),
    ("loan_application", "credit_quote_date", "broker_fee"),
    ("loan_application", "credit_proposal_date", "credit_quote_date"),
    ("loan_application", "discharged_date", "expected_upfront"),
    ("lender", "clawback_half_after", "clawback_months"),
]
_PORTAL_HIDDEN: Final = (
    "broker",
    "processor",
    "products_considered",
    "expected_upfront",
    "lender_reference",
    "decline_reason",
)

SETTINGS_DEFAULTS: Final[dict[str, Any]] = {
    "settlement_reminder_days": [7, 1],
    "fixed_rate_reminder_days": [90, 30],
    "rate_review_reminder_days": [7],
    "approval_expiry_reminder_days": [14],
    "bid_retention_years": 7,
    "serviceability_buffer": 3.0,
    "minimum_assessment_rate": 0,
}
SETTINGS_FIELDS: Final[list[dict[str, Any]]] = [
    {"key": "serviceability_buffer", "label": "Serviceability buffer (% above the product rate)", "kind": "number",
     "hint": "APRA expects lenders to assess at least 3 percentage points above the loan rate."},
    {"key": "minimum_assessment_rate", "label": "Minimum assessment rate (%)", "kind": "number",
     "hint": "A floor for the assessment rate (0 for none)."},
    {"key": "bid_retention_years", "label": "Keep assessments and BID records for (years)", "kind": "number",
     "hint": "Preliminary assessments must be kept for 7 years (NCCP)."},
    {"key": "settlement_reminder_days", "label": "Settlement reminders (days before)", "kind": "days"},
    {"key": "approval_expiry_reminder_days", "label": "Approval expiry reminders (days before)", "kind": "days"},
    {"key": "fixed_rate_reminder_days", "label": "Fixed rate expiry reminders (days before)", "kind": "days"},
    {"key": "rate_review_reminder_days", "label": "Rate review reminders (days before)", "kind": "days"},
]  # fmt: skip


def upgrade(conn: Connection) -> None:
    """Add-only extras for workspaces that already have the pack."""
    portal = security_id("profile", "customer_portal")
    for field in _PORTAL_HIDDEN:
        install_field_security(conn, portal, "loan_application", field, "hidden")


def bundle() -> dict[str, Any]:
    return {
        "objects": [LENDER, LOAN, FACT_FIND, COMMISSION],
        "fields": STANDARD_FIELDS,
        "apps": [APP],
        "list_views": LIST_VIEWS,
    }


PROFILES: Final[list[ProfileSpec]] = [
    ("lb_principal", "Principal Broker", "Credit licensee / principal: the whole pipeline, lender panel and commission ledger.", "sales_manager",
     {"loan_application": "RCED VA MA", "lender": "RCED VA MA", "fact_find": "RCED VA MA", "commission": "RCED VA MA", "contact": "RCED VA MA", "account": "RCED VA MA"},
     ("manage_portal_users", "transfer_records", "export_data", "import_data", "manage_public_reports"), (SUBMIT, COMMISSIONS)),
    ("lb_broker", "Broker", "Credit representative: own clients and applications, fact finds and BID records.", "sales_representative",
     {"loan_application": "RCE", "lender": "R", "fact_find": "RCED", "commission": "R"}, ("manage_portal_users",), (SUBMIT,)),
    ("lb_processor", "Loan Processor", "Prepares and tracks applications with lenders through to settlement.", "service_agent",
     {"loan_application": "RE VA", "lender": "R", "fact_find": "RCE VA"}, (), ()),
    ("lb_admin", "Commissions Administrator", "Reconciles lender commission statements.", "finance",
     {"loan_application": "R VA", "lender": "RCE", "commission": "RCE VA MA"}, (), (COMMISSIONS,)),
]  # fmt: skip

REPORT_FOLDER: Final = "loan_broker_reports"
REPORTS: Final[list[tuple[str, str, str, dict[str, Any]]]] = [
    ("lb_pipeline", "Pipeline by Stage", "loan_application", {"format": "summary", "group_by": ["stage"], "aggregates": [{"op": "sum", "field": "loan_amount"}, {"op": "count"}], "filters": _ACTIVE, "chart": {"type": "funnel"}}),
    ("lb_settled_by_lender", "Settled Volume by Lender", "loan_application", {"format": "summary", "group_by": ["lender"], "aggregates": [{"op": "sum", "field": "loan_amount"}, {"op": "count"}],
                                                                                "filters": {"logic": "and", "conditions": [{"field": "stage", "op": "equals", "value": "Settled"}]}, "chart": {"type": "bar"}}),
    ("lb_broker_volume", "Broker Volume (this year)", "loan_application", {"format": "summary", "group_by": ["broker"], "aggregates": [{"op": "sum", "field": "loan_amount"}, {"op": "count"}],
                                                                            "filters": {"logic": "and", "conditions": [{"field": "stage", "op": "equals", "value": "Settled"}, {"field": "settlement_date", "op": "equals", "value": "THIS_YEAR"}]}, "chart": {"type": "bar"}}),
    ("lb_commission_by_type", "Commission by Type", "commission", {"format": "summary", "group_by": ["type"], "aggregates": [{"op": "count"}, {"op": "sum", "field": "signed_amount"}], "chart": {"type": "bar"}}),
    ("lb_commission_ledger", "Commission Ledger by Lender", "commission", {"format": "summary", "group_by": ["lender"], "aggregates": [{"op": "sum", "field": "signed_amount"}], "chart": {"type": "bar"}}),
    ("lb_upcoming_settlements", "Upcoming Settlements", "loan_application", {"format": "tabular", "columns": ["name", "primary_borrower", "loan_amount", "lender", "settlement_date", "broker"],
                                                                               "filters": {"logic": "and", "conditions": [{"field": "settlement_date", "op": "equals", "value": "NEXT_N_DAYS:30"}]}, "sort": [{"field": "settlement_date", "direction": "asc"}]}),
    ("lb_fixed_expiries", "Fixed Rate Expiries", "loan_application", {"format": "tabular", "columns": ["name", "primary_borrower", "lender", "interest_rate", "fixed_rate_expiry", "broker"],
                                                                         "filters": {"logic": "and", "conditions": [{"field": "fixed_rate_expiry", "op": "equals", "value": "NEXT_N_DAYS:90"}]}, "sort": [{"field": "fixed_rate_expiry", "direction": "asc"}]}),
]  # fmt: skip


def install(conn: Connection) -> None:
    install_profiles(conn, KEY, PROFILES)
    for key in ("lb_principal", "lb_broker", "lb_processor"):
        install_field_security(conn, security_id("profile", key), "contact", "drivers_licence", "edit")
    ro = security_id("profile", "read_only")
    for obj in PACK_OBJECTS:
        install_object_permission(conn, ro, obj, {"can_read": True, "view_all": True})
    portal = security_id("profile", "customer_portal")
    install_object_permission(conn, portal, "loan_application", {"can_read": True})
    # Clients see which lender their loan is with, not the broker's commission rates or BDM.
    install_object_permission(conn, portal, "lender", {"can_read": True})
    for field in (
        "upfront_rate",
        "trail_rate",
        "clawback_months",
        "clawback_half_after",
        "accreditation_number",
        "bdm_name",
        "bdm_email",
        "bdm_phone",
        "notes",
    ):
        install_field_security(conn, portal, "lender", field, "hidden")
    for field in _PORTAL_HIDDEN:
        install_field_security(conn, portal, "loan_application", field, "hidden")
    install_folder(conn, REPORT_FOLDER, "Loan Broking Reports")
    for key, name, obj, definition in REPORTS:
        install_report(conn, key, REPORT_FOLDER, name, obj, definition, pack_key=KEY)
    install_dashboard(
        conn,
        "lb_broker_dashboard",
        REPORT_FOLDER,
        "Broking Dashboard",
        [
            {"report": "lb_pipeline", "title": "Pipeline by stage", "chart": "funnel", "width": 2},
            {
                "report": "lb_commission_by_type",
                "title": "Net commission by type",
                "chart": "bar",
                "width": 1,
            },
            {"report": "lb_settled_by_lender", "title": "Settled by lender", "chart": "bar", "width": 2},
            {"report": "lb_broker_volume", "title": "Broker volume", "chart": "bar", "width": 1},
            {
                "report": "lb_upcoming_settlements",
                "title": "Upcoming settlements",
                "chart": "table",
                "width": 3,
            },
        ],
        "Pipeline, settlements, lenders and commission.",
        pack_key=KEY,
    )
    set_setting(conn, KEY, dict(SETTINGS_DEFAULTS))

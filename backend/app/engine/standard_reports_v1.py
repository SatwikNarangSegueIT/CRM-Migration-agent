"""Standard reports and dashboards, version 1 (plan v3, section 12). FROZEN once released."""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import Connection

from app.engine.installer import install_dashboard, install_folder, install_report

FOLDER = "standard_reports"


def _c(field: str, op: str, value: Any = None) -> dict[str, Any]:
    return {"field": field, "op": op, "value": value}


def _and(*conds: dict[str, Any]) -> dict[str, Any]:
    return {"logic": "and", "conditions": list(conds)}


COUNT: Final = {"op": "count"}
REPORTS: Final[list[tuple[str, str, str, dict[str, Any], str]]] = [
    (
        "pipeline_by_stage",
        "Pipeline by Stage",
        "opportunity",
        {
            "format": "summary",
            "group_by": ["stage"],
            "filters": _and(_c("is_closed", "equals", False)),
            "aggregates": [COUNT, {"op": "sum", "field": "amount"}],
            "chart": {"type": "funnel"},
        },
        "Open opportunities and their value by stage.",
    ),
    (
        "forecast",
        "Forecast by Close Month",
        "opportunity",
        {
            "format": "matrix",
            "group_by": ["close_date"],
            "group_columns": ["forecast_category"],
            "date_granularity": {"close_date": "month"},
            "filters": _and(_c("close_date", "equals", "THIS_YEAR")),
            "aggregates": [{"op": "sum", "field": "amount"}],
            "chart": {"type": "column"},
        },
        "Opportunity amounts by close month and forecast category (this year).",
    ),
    (
        "win_rate",
        "Win Rate",
        "opportunity",
        {
            "format": "summary",
            "group_by": ["is_won"],
            "filters": _and(_c("is_closed", "equals", True)),
            "aggregates": [COUNT, {"op": "sum", "field": "amount"}],
            "chart": {"type": "donut"},
        },
        "Closed opportunities: won versus lost.",
    ),
    (
        "lead_conversion_by_source",
        "Lead Conversion by Source",
        "lead",
        {
            "format": "matrix",
            "group_by": ["lead_source"],
            "group_columns": ["is_converted"],
            "aggregates": [COUNT],
            "chart": {"type": "bar"},
        },
        "Leads by source, converted and not converted.",
    ),
    (
        "campaign_roi",
        "Campaign ROI",
        "opportunity",
        {
            "format": "summary",
            "group_by": ["campaign"],
            "filters": _and(_c("is_won", "equals", True), _c("campaign", "is_not_null")),
            "aggregates": [COUNT, {"op": "sum", "field": "amount"}],
            "chart": {"type": "bar"},
        },
        "Won revenue by primary campaign source; compare with campaign costs.",
    ),
    (
        "campaign_costs",
        "Campaign Costs",
        "campaign",
        {
            "format": "tabular",
            "columns": ["name", "type", "status", "budgeted_cost", "actual_cost", "expected_revenue"],
            "aggregates": [{"op": "sum", "field": "actual_cost"}],
        },
        "Budgeted and actual cost per campaign.",
    ),
    (
        "email_engagement",
        "E-mail Engagement",
        "email_send",
        {
            "format": "tabular",
            "columns": [
                "name",
                "subject",
                "sent_at",
                "recipients_count",
                "delivered_count",
                "opened_count",
                "clicked_count",
                "unsubscribed_count",
                "bounced_count",
            ],
            "filters": _and(_c("status", "equals", "Sent")),
            "sort": [{"field": "sent_at", "direction": "desc"}],
            "aggregates": [
                {"op": "sum", "field": "delivered_count"},
                {"op": "sum", "field": "opened_count"},
                {"op": "sum", "field": "clicked_count"},
            ],
        },
        "Delivery, opens and clicks per e-mail send.",
    ),
    (
        "case_volume",
        "Case Volume by Status",
        "case",
        {
            "format": "summary",
            "group_by": ["status", "priority"],
            "aggregates": [COUNT],
            "chart": {"type": "bar"},
        },
        "Cases by status and priority.",
    ),
    (
        "case_sla",
        "SLA Compliance",
        "case",
        {
            "format": "summary",
            "group_by": ["is_escalated"],
            "filters": _and(_c("created_at", "equals", "LAST_N_DAYS:90")),
            "aggregates": [COUNT],
            "chart": {"type": "donut"},
        },
        "Cases in the last 90 days that breached (escalated) or met their resolution SLA.",
    ),
    (
        "open_cases_by_owner",
        "Open Cases by Owner",
        "case",
        {
            "format": "summary",
            "group_by": ["owner_id"],
            "filters": _and(_c("status", "not_equals", "Closed")),
            "aggregates": [COUNT],
            "chart": {"type": "bar"},
        },
        "Workload of open cases.",
    ),
    (
        "aged_receivables",
        "Aged Receivables",
        "invoice",
        {
            "format": "summary",
            "group_by": ["age:due_date"],
            "filters": _and(_c("status", "in", ["Issued", "Partially Paid"])),
            "aggregates": [COUNT, {"op": "sum", "field": "balance"}],
            "chart": {"type": "column"},
        },
        "Unpaid invoice balances by days overdue.",
    ),
    (
        "revenue_by_month",
        "Revenue by Month",
        "invoice",
        {
            "format": "summary",
            "group_by": ["issue_date"],
            "date_granularity": {"issue_date": "month"},
            "filters": _and(
                _c("status", "in", ["Issued", "Partially Paid", "Paid"]),
                _c("issue_date", "equals", "LAST_N_DAYS:365"),
            ),
            "aggregates": [{"op": "sum", "field": "total"}, {"op": "sum", "field": "amount_paid"}],
            "chart": {"type": "line"},
        },
        "Invoiced and collected amounts for the last 12 months.",
    ),
    (
        "my_open_opportunities",
        "My Open Opportunities",
        "opportunity",
        {
            "format": "tabular",
            "scope": "mine",
            "columns": ["name", "account", "stage", "amount", "close_date"],
            "filters": _and(_c("is_closed", "equals", False)),
            "sort": [{"field": "close_date", "direction": "asc"}],
            "aggregates": [{"op": "sum", "field": "amount"}],
        },
        "Your open pipeline.",
    ),
    (
        "total_pipeline",
        "Total Open Pipeline",
        "opportunity",
        {
            "format": "summary",
            "group_by": ["forecast_category"],
            "filters": _and(_c("is_closed", "equals", False)),
            "aggregates": [{"op": "sum", "field": "amount"}],
            "chart": {"type": "kpi"},
        },
        "Open pipeline value.",
    ),
]

DASHBOARDS: Final[list[tuple[str, str, str, list[dict[str, Any]]]]] = [
    (
        "sales_dashboard",
        "Sales Dashboard",
        "Pipeline, forecast and win rate.",
        [
            {"report": "total_pipeline", "title": "Open pipeline", "chart": "kpi", "width": 1},
            {"report": "pipeline_by_stage", "title": "Pipeline by stage", "chart": "funnel", "width": 2},
            {"report": "forecast", "title": "Forecast by month", "chart": "column", "width": 2},
            {"report": "win_rate", "title": "Win rate", "chart": "donut", "width": 1},
            {
                "report": "lead_conversion_by_source",
                "title": "Lead conversion by source",
                "chart": "bar",
                "width": 3,
            },
        ],
    ),
    (
        "service_dashboard",
        "Service Dashboard",
        "Case volume and SLA compliance.",
        [
            {"report": "case_volume", "title": "Cases by status", "chart": "bar", "width": 2},
            {"report": "case_sla", "title": "SLA compliance (90 days)", "chart": "donut", "width": 1},
            {"report": "open_cases_by_owner", "title": "Open cases by owner", "chart": "bar", "width": 3},
        ],
    ),
    (
        "marketing_dashboard",
        "Marketing Dashboard",
        "Campaign returns and e-mail engagement.",
        [
            {"report": "campaign_roi", "title": "Won revenue by campaign", "chart": "bar", "width": 2},
            {"report": "lead_conversion_by_source", "title": "Leads by source", "chart": "donut", "width": 1},
            {"report": "email_engagement", "title": "E-mail engagement", "chart": "table", "width": 3},
        ],
    ),
    (
        "billing_dashboard",
        "Billing Dashboard",
        "Receivables and revenue.",
        [
            {"report": "aged_receivables", "title": "Aged receivables", "chart": "column", "width": 2},
            {"report": "revenue_by_month", "title": "Revenue by month", "chart": "line", "width": 3},
        ],
    ),
]


def apply(conn: Connection) -> None:
    install_folder(conn, FOLDER, "Standard Reports")
    for key, name, obj, definition, description in REPORTS:
        install_report(conn, key, FOLDER, name, obj, definition, description)
    for key, name, description, components in DASHBOARDS:
        install_dashboard(conn, key, FOLDER, name, components, description)

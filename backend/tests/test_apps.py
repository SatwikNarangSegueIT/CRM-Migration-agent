"""Business logic of the standard apps (plan v3, section 8), analytics, import/export, portal, public
forms and the Migration Agency pack."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.installer import stable_id as record_id
from app.models import EmailDelivery, Notification, Record
from tests.conftest import Outbox, login, make_user
from tests.test_records_engine import as_user, create

API = "/api/v1"


def action(
    c: TestClient, obj: str, rid: str, name: str, payload: dict[str, Any] | None = None, expect: int = 200
) -> dict[str, Any]:
    r = c.post(f"{API}/objects/{obj}/records/{rid}/actions/{name}", json=payload or {})
    assert r.status_code == expect, r.text
    out: dict[str, Any] = r.json()
    return out


def get(c: TestClient, obj: str, rid: str) -> dict[str, Any]:
    r = c.get(f"{API}/objects/{obj}/records/{rid}")
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    return out


# ------------------------------------------------------------------ sales


def test_lead_conversion_moves_activities_and_locks_the_lead(
    client: TestClient, db: Session, no_mfa: None
) -> None:
    rep = as_user(client, db, "sales_representative", role="sales_representative")
    lead = create(
        rep,
        "lead",
        {
            "first_name": "Lee",
            "last_name": "Dunn",
            "company": "Dunn Logistics",
            "email": "lee@dunn.example",
            "lead_source": "Web",
            "industry": "Transport",
        },
    )
    assert lead["name"] == "Lee Dunn" and lead["fields"]["status"] == "New"
    task = create(
        rep, "task", {"related_to": lead["id"], "due_date": date.today().isoformat()}, name="Call Lee"
    )
    dupes = action(rep, "lead", lead["id"], "convert", {"check_duplicates": True})
    assert dupes["duplicates"] == {"accounts": [], "contacts": []}
    result = action(
        rep, "lead", lead["id"], "convert", {"create_opportunity": True, "opportunity_name": "Dunn fleet"}
    )
    account, contact, opp = (get(rep, o, result[f"{o}_id"]) for o in ("account", "contact", "opportunity"))
    assert account["name"] == "Dunn Logistics" and account["fields"]["industry"] == "Transport"
    assert contact["fields"]["email"] == "lee@dunn.example" and contact["fields"]["account"] == account["id"]
    assert opp["name"] == "Dunn fleet" and opp["fields"]["primary_contact"] == contact["id"]
    assert get(rep, "task", task["id"])["fields"]["related_to"] == contact["id"]
    converted = get(rep, "lead", lead["id"])
    assert converted["fields"]["is_converted"] is True and converted["fields"]["status"] == "Qualified"
    locked = rep.patch(
        f"{API}/objects/lead/records/{lead['id']}",
        json={"version": converted["version"], "fields": {"title": "x"}},
    )
    assert locked.status_code == 422
    assert action(rep, "lead", lead["id"], "convert", expect=422)


def test_opportunity_stage_rules(admin_client: TestClient) -> None:
    c = admin_client
    acct = create(c, "account", name="Stage Co")
    opp = create(c, "opportunity", {"account": acct["id"], "close_date": "2030-06-30"}, name="Deal")
    assert opp["fields"]["probability"] == 10 and opp["fields"]["forecast_category"] == "Pipeline"
    url = f"{API}/objects/opportunity/records/{opp['id']}"
    r = c.patch(url, json={"version": opp["version"], "fields": {"stage": "Negotiation"}})
    assert r.json()["fields"]["probability"] == 80 and r.json()["fields"]["forecast_category"] == "Commit"
    lost = c.patch(url, json={"version": r.json()["version"], "fields": {"stage": "Closed Lost"}})
    assert lost.status_code == 422 and "loss_reason" in lost.json()["error"]["fields"]
    won = c.patch(url, json={"version": r.json()["version"], "fields": {"stage": "Closed Won"}}).json()
    assert won["fields"]["is_won"] is True and won["fields"]["closed_date"] == date.today().isoformat()
    reopen = c.patch(url, json={"version": won["version"], "fields": {"stage": "Proposal"}})
    assert reopen.status_code == 422


# ------------------------------------------------------------------ billing


def test_quote_to_invoice_to_payments(admin_client: TestClient) -> None:
    c = admin_client
    acct = create(c, "account", {"abn": "51 824 753 556"}, name="Billing Pty Ltd")
    product = create(c, "product", {"product_code": "CONSULT", "standard_price": 150}, name="Consulting hour")
    quote = create(c, "quote", {"title": "Website build", "account": acct["id"]})
    assert quote["name"] == "Q-00001"
    create(c, "quote_line", {"quote": quote["id"], "product": product["id"], "quantity": 2, "discount": 20})
    q = get(c, "quote", quote["id"])
    # 2 x 150 = 300, less 20 discount = 280 net, GST 10% = 28, total 308.
    assert (
        q["fields"]["subtotal"],
        q["fields"]["discount_total"],
        q["fields"]["tax_total"],
        q["fields"]["total"],
    ) == (300, 20, 28, 308)
    action(c, "quote", quote["id"], "create_invoice", expect=422)  # not accepted yet
    q = c.patch(
        f"{API}/objects/quote/records/{quote['id']}",
        json={"version": q["version"], "fields": {"status": "Accepted"}},
    ).json()
    inv_id = action(c, "quote", quote["id"], "create_invoice")["invoice_id"]
    inv = get(c, "invoice", inv_id)
    assert (
        inv["fields"]["status"] == "Draft"
        and inv["fields"]["total"] == 308
        and inv["name"].startswith("Draft")
    )
    lines = c.get(f"{API}/objects/invoice/records/{inv_id}/related/invoice_line/invoice").json()["items"]
    assert len(lines) == 1 and lines[0]["fields"]["line_total"] == 280

    issued = action(c, "invoice", inv_id, "issue")
    assert issued["fields"]["status"] == "Issued" and issued["fields"]["invoice_number"] == "INV-000001"
    assert issued["fields"]["due_date"] == (date.today() + timedelta(days=14)).isoformat()
    edit_line = c.patch(
        f"{API}/objects/invoice_line/records/{lines[0]['id']}",
        json={"version": lines[0]["version"], "fields": {"quantity": 5}},
    )
    assert edit_line.status_code == 422  # issued invoices are locked

    over = c.post(f"{API}/objects/payment/records", json={"fields": {"invoice": inv_id, "amount": 400}})
    assert over.status_code == 422
    pay1 = create(c, "payment", {"invoice": inv_id, "amount": "100.00", "reference": "EFT-1"})
    assert get(c, "invoice", inv_id)["fields"]["status"] == "Partially Paid"
    assert get(c, "invoice", inv_id)["fields"]["balance"] == 208
    action(c, "invoice", inv_id, "void", {"reason": "Wrong"}, expect=422)  # payments must be reversed first
    create(c, "payment", {"invoice": inv_id, "amount": 208})
    paid = get(c, "invoice", inv_id)
    assert paid["fields"]["status"] == "Paid" and paid["fields"]["balance"] == 0
    action(c, "payment", pay1["id"], "reverse", {"reason": "Bounced"})
    assert get(c, "invoice", inv_id)["fields"]["status"] == "Partially Paid"
    pdf = c.get(f"{API}/objects/invoice/records/{inv_id}/pdf")
    assert (
        pdf.status_code == 200
        and pdf.content.startswith(b"%PDF")
        and pdf.headers["content-type"] == "application/pdf"
    )
    assert c.delete(f"{API}/objects/invoice/records/{inv_id}").status_code == 422


def test_price_books_and_opportunity_products(admin_client: TestClient) -> None:
    c = admin_client
    product = create(c, "product", {"product_code": "P1", "standard_price": 100}, name="Thing")
    book = create(c, "price_book", name="Partner prices")
    create(c, "price_book_entry", {"price_book": book["id"], "product": product["id"], "list_price": 80})
    dup = c.post(
        f"{API}/objects/price_book_entry/records",
        json={"fields": {"price_book": book["id"], "product": product["id"], "list_price": 1}},
    )
    assert dup.status_code == 409
    acct = create(c, "account", name="Partner Co")
    opp = create(
        c,
        "opportunity",
        {"account": acct["id"], "close_date": "2030-01-01", "price_book": book["id"]},
        name="Partner deal",
    )
    line = create(
        c, "opportunity_product", {"opportunity": opp["id"], "product": product["id"], "quantity": 2}
    )
    assert line["fields"]["unit_price"] == 80 and line["fields"]["line_total"] == 160
    opp_now = get(c, "opportunity", opp["id"])
    assert opp_now["fields"]["amount"] == 160 and opp_now["fields"]["has_products"] is True
    manual = c.patch(
        f"{API}/objects/opportunity/records/{opp['id']}",
        json={"version": opp_now["version"], "fields": {"amount": 5}},
    )
    assert manual.status_code == 422
    # Changing the standard price on the product updates its standard price-book entry.
    p = get(c, "product", product["id"])
    c.patch(
        f"{API}/objects/product/records/{product['id']}",
        json={"version": p["version"], "fields": {"standard_price": 120}},
    )
    entries = c.get(f"{API}/objects/product/records/{product['id']}/related/price_book_entry/product").json()[
        "items"
    ]
    assert sorted(e["fields"]["list_price"] for e in entries) == [80, 120]


# ------------------------------------------------------------------ service


def test_case_sla_close_and_escalation(admin_client: TestClient, db: Session) -> None:
    c = admin_client
    case = create(c, "case", {"subject": "Down", "priority": "High"})
    created = datetime.fromisoformat(case["created_at"].replace("Z", "+00:00"))
    due = datetime.fromisoformat(case["fields"]["resolution_due"].replace("Z", "+00:00"))
    assert abs((due - created) - timedelta(hours=24)) < timedelta(minutes=1)
    url = f"{API}/objects/case/records/{case['id']}"
    no_res = c.patch(url, json={"version": case["version"], "fields": {"status": "Closed"}})
    assert no_res.status_code == 422 and "resolution" in no_res.json()["error"]["fields"]
    late = create(c, "case", {"subject": "Overdue", "priority": "Low"})
    from app.apps.service import escalate_overdue_cases

    assert escalate_overdue_cases(db, now=datetime.now(UTC) + timedelta(days=30)) == 2
    escalated = get(c, "case", late["id"])
    assert escalated["fields"]["is_escalated"] is True and escalated["fields"]["status"] == "Escalated"
    assert db.scalar(select(Notification).where(Notification.record_id == uuid.UUID(late["id"]))) is not None
    assert c.get(f"{API}/me/notifications").json()["unread"] == 2
    closed = action(c, "case", case["id"], "close", {"resolution": "Rebooted"})
    assert closed["fields"]["status"] == "Closed" and closed["fields"]["closed_at"]


# ------------------------------------------------------------------ marketing


def test_email_send_consent_tracking_and_unsubscribe(client: TestClient, db: Session, no_mfa: None) -> None:
    mkt = as_user(client, db, "marketing_user", role="marketing_user")
    people = {
        "opted": create(
            mkt, "contact", {"last_name": "Opted", "email": "opted@ex.example", "email_opt_in": True}
        ),
        "no_consent": create(mkt, "contact", {"last_name": "Nope", "email": "nope@ex.example"}),
        "dupe": create(
            mkt, "contact", {"last_name": "Dupe", "email": "OPTED@ex.example", "email_opt_in": True}
        ),
        "bounced": create(
            mkt, "contact", {"last_name": "Bad", "email": "bad@ex.example", "email_opt_in": True}
        ),
    }
    create(mkt, "consent", {"contact": people["bounced"]["id"], "channel": "Email", "status": "Opted Out"})
    assert get(mkt, "contact", people["bounced"]["id"])["fields"]["email_opt_in"] is False
    segment = create(
        mkt,
        "segment",
        {
            "target_object": "contact",
            "criteria": json.dumps(
                {"logic": "and", "conditions": [{"field": "email", "op": "contains", "value": "@ex.example"}]}
            ),
        },
        name="Everyone",
    )
    assert segment["fields"]["member_count"] == 4
    send = create(
        mkt,
        "email_send",
        {
            "subject": "Hello {{first_name}}",
            "segment": segment["id"],
            "html_body": '<p>Hi {{name}}, <a href="https://example.com/offer">see offer</a></p>',
        },
        name="Launch",
    )
    action(mkt, "email_send", send["id"], "schedule", {"scheduled_at": "2001-01-01T00:00:00Z"})
    from app.apps.marketing import process_send

    process_send(db, uuid.UUID(send["id"]))
    all_deliveries = list(db.scalars(select(EmailDelivery)))
    deliveries = {d.email: d for d in all_deliveries if d.status != "skipped"}
    assert deliveries["opted@ex.example"].status == "sent"
    reasons = sorted(d.skip_reason or "" for d in all_deliveries if d.status == "skipped")
    assert reasons == ["duplicate", "no_consent", "no_consent"]
    sent = get(mkt, "email_send", send["id"])
    assert (
        sent["fields"]["status"] == "Sent"
        and sent["fields"]["delivered_count"] == 1
        and sent["fields"]["skipped_count"] == 3
    )

    token = deliveries["opted@ex.example"].tracking_token
    anon = TestClient(client.app)
    assert anon.get(f"{API}/public/e/{token}/open.gif").headers["content-type"] == "image/gif"
    from app.apps.marketing import click_link

    link = click_link(token, "https://example.com/offer")
    path = link.split("localhost:5173", 1)[1]
    r = anon.get(path, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://example.com/offer"
    assert (
        anon.get(
            f"{API}/public/e/{token}/click",
            params={"u": "https://evil.example", "s": "x"},
            follow_redirects=False,
        ).status_code
        == 400
    )
    assert anon.get(f"{API}/public/unsubscribe/{token}").json()["unsubscribed"] is False
    assert anon.post(f"{API}/public/unsubscribe/{token}").json() == {"unsubscribed": True}
    assert get(mkt, "contact", people["opted"]["id"])["fields"]["email_opt_in"] is False
    final = get(mkt, "email_send", send["id"])["fields"]
    assert (final["opened_count"], final["clicked_count"], final["unsubscribed_count"]) == (1, 1, 1)
    # Sending needs Send Mass Email: sales reps can't.
    rep = as_user(client, db, "sales_representative")
    assert rep.get(f"{API}/objects/email_send/records").status_code == 403


def test_campaign_members_from_segment(admin_client: TestClient) -> None:
    c = admin_client
    camp = create(c, "campaign", {"type": "Event"}, name="Expo")
    lead = create(c, "lead", {"last_name": "Visitor", "company": "V Co"})
    contact = create(c, "contact", {"last_name": "Guest"})
    added = action(
        c, "campaign", camp["id"], "add_members", {"record_ids": [lead["id"], contact["id"], contact["id"]]}
    )
    assert added == {"added": 2, "skipped": 0}
    again = action(c, "campaign", camp["id"], "add_members", {"record_ids": [lead["id"]]})
    assert again == {"added": 0, "skipped": 1}
    members = c.get(f"{API}/objects/campaign/records/{camp['id']}/related/campaign_member/campaign").json()[
        "items"
    ]
    assert sorted(m["name"] for m in members) == ["Guest", "Visitor"]


# ------------------------------------------------------------------ analytics


def test_reports_respect_sharing_and_formats(
    client: TestClient, db: Session, admin_client: TestClient
) -> None:
    rep = as_user(client, db, "sales_representative", role="sales_representative")
    acct = create(admin_client, "account", {"industry": "Retail"}, name="Report Co")
    create(
        rep,
        "opportunity",
        {"account": acct["id"], "close_date": date.today().isoformat(), "amount": 100, "stage": "Proposal"},
        name="Mine",
    )
    create(
        admin_client,
        "opportunity",
        {"account": acct["id"], "close_date": date.today().isoformat(), "amount": 900, "stage": "Proposal"},
        name="Admin's",
    )
    reports = {r["key"]: r for r in admin_client.get(f"{API}/reports").json()}
    assert {"pipeline_by_stage", "aged_receivables", "revenue_by_month", "win_rate"} <= set(reports)
    pipe_id = reports["pipeline_by_stage"]["id"]
    admin_run = admin_client.post(f"{API}/reports/{pipe_id}/run").json()
    proposal = next(g for g in admin_run["groups"] if g["keys"] == ["Proposal"])
    assert proposal["values"] == {"count": 2, "sum:amount": 1000}
    rep_run = rep.post(f"{API}/reports/{pipe_id}/run").json()
    assert next(g for g in rep_run["groups"] if g["keys"] == ["Proposal"])["values"] == {
        "count": 1,
        "sum:amount": 100,
    }

    matrix = admin_client.post(
        f"{API}/reports/run",
        json={
            "name": "x",
            "object_api_name": "opportunity",
            "definition": {
                "format": "matrix",
                "group_by": ["account.industry"],
                "group_columns": ["stage"],
                "aggregates": [{"op": "sum", "field": "amount"}],
            },
        },
    ).json()
    assert (
        matrix["groups"][0]["labels"] == ["Retail", "Proposal"]
        and matrix["groups"][0]["values"]["sum:amount"] == 1000
    )
    tab = admin_client.post(
        f"{API}/reports/run",
        json={
            "name": "x",
            "object_api_name": "opportunity",
            "definition": {
                "format": "tabular",
                "columns": ["name", "account", "account.industry", "amount"],
                "sort": [{"field": "amount", "direction": "desc"}],
                "aggregates": [{"op": "sum", "field": "amount"}],
            },
        },
    ).json()
    assert [r["cells"][0]["label"] for r in tab["rows"]] == ["Admin's", "Mine"]
    assert tab["rows"][0]["cells"][1]["label"] == "Report Co" and tab["totals"]["sum:amount"] == 1000
    bad = admin_client.post(
        f"{API}/reports/run",
        json={
            "name": "x",
            "object_api_name": "opportunity",
            "definition": {"format": "summary", "group_by": ["description"]},
        },
    )
    assert bad.status_code == 422

    saved = rep.post(
        f"{API}/reports",
        json={
            "name": "My pipe",
            "object_api_name": "opportunity",
            "definition": {"format": "summary", "group_by": ["stage"]},
        },
    )
    assert saved.status_code == 201
    assert rep.get(f"{API}/reports/{saved.json()['id']}/export.csv").status_code == 403  # needs Export Data
    csv_text = admin_client.get(f"{API}/reports/{pipe_id}/export.csv").text
    assert csv_text.splitlines()[0] == "Stage,Record Count,Sum of Amount"
    dashboards = {d["key"]: d for d in admin_client.get(f"{API}/dashboards").json()}
    run = admin_client.post(f"{API}/dashboards/{dashboards['sales_dashboard']['id']}/run").json()
    assert len(run["components"]) == 5 and all(comp["error"] is None for comp in run["components"])


# ------------------------------------------------------------------ import / export


def test_import_wizard_and_export(admin_client: TestClient) -> None:
    c = admin_client
    create(c, "contact", {"last_name": "Existing", "email": "dup@ex.example"})
    acct = create(c, "account", name="Import Co")
    csv_text = "First Name,Last Name,Email,Account,Lead Source\nAmy,Adams,amy@ex.example,Import Co,Web\n,Broken,not-an-email,,\nDan,Dupe,dup@ex.example,,Event\n"
    info = c.post(f"{API}/imports/analyze", json={"object_api_name": "contact", "csv": csv_text}).json()
    assert info["suggested_mapping"] == {
        "First Name": "first_name",
        "Last Name": "last_name",
        "Email": "email",
        "Account": "account",
        "Lead Source": "lead_source",
    }
    body = {
        "object_api_name": "contact",
        "csv": csv_text,
        "mapping": info["suggested_mapping"],
        "match_field": "email",
        "duplicate_action": "update",
    }
    dry = c.post(f"{API}/imports", json={**body, "dry_run": True}).json()
    assert (dry["created"], dry["updated"], dry["errors"]) == (1, 1, 1)
    assert c.get(f"{API}/objects/contact/records").json()["total"] == 1  # nothing written
    job = c.post(f"{API}/imports", json=body).json()
    assert job["status"] == "completed" and (job["created"], job["updated"], job["errors"]) == (1, 1, 1)
    errors = c.get(f"{API}/imports/{job['id']}/errors.csv").text
    assert "Row,Error" in errors and "3," in errors
    amy = c.post(f"{API}/objects/contact/records/query", json={"search": "amy@ex.example"}).json()["items"][0]
    assert amy["fields"]["account"] == acct["id"]
    exported = c.post(
        f"{API}/exports", json={"object_api_name": "contact", "columns": ["name", "email", "account"]}
    )
    assert exported.status_code == 200
    lines = exported.text.lstrip("﻿").splitlines()
    assert lines[0] == "Id,Name,E-mail,Account" and len(lines) == 3
    assert c.get(f"{API}/admin/audit-logs", params={"action": "EXPORT"}).json()["total"] == 1


# ------------------------------------------------------------------ portal and public


def test_customer_portal(admin_client: TestClient, client: TestClient, db: Session, outbox: Outbox) -> None:
    c = admin_client
    acct = create(c, "account", name="Customer Co")
    other_acct = create(c, "account", name="Other Co")
    contact = create(
        c,
        "contact",
        {"first_name": "Pat", "last_name": "Portal", "email": "pat@customer.example", "account": acct["id"]},
    )
    other = create(
        c, "contact", {"last_name": "Else", "email": "else@other.example", "account": other_acct["id"]}
    )
    invited = c.post(f"{API}/portal-users/invite/{contact['id']}")
    assert invited.status_code == 201, invited.text
    token = outbox.token_for("pat@customer.example")
    anon = TestClient(client.app)
    assert (
        anon.post(
            f"{API}/auth/invitation/accept", json={"token": token, "password": "Sunny-Harbour-2026!"}
        ).status_code
        == 200
    )
    portal = TestClient(client.app)
    assert login(portal, "pat@customer.example", "Sunny-Harbour-2026!") == "authenticated"
    me = portal.get(f"{API}/portal/me").json()
    assert me["contact"]["name"] == "Pat Portal" and me["account"]["name"] == "Customer Co"
    assert {o["api_name"] for o in me["objects"]} >= {"case", "invoice"}

    mine = portal.post(
        f"{API}/portal/cases", json={"subject": "Help please", "description": "It broke"}
    ).json()
    assert mine["fields"]["origin"] == "Portal" and mine["fields"]["contact"] == contact["id"]
    assert mine["owner"]["type"] == "queue"
    others = create(c, "case", {"subject": "Not yours", "contact": other["id"]})
    listing = portal.get(f"{API}/portal/objects/case/records").json()
    assert [i["id"] for i in listing["items"]] == [mine["id"]]
    assert portal.get(f"{API}/portal/objects/case/records/{others['id']}").status_code == 404
    described = portal.get(f"{API}/portal/objects/case/describe").json()
    assert described["label"] == "Case"
    assert "subject" in described["fields"] and "status" in described["fields"]
    assert "list_views" not in described and "actions" not in described
    assert portal.get(f"{API}/portal/objects/lead/describe").status_code == 403  # no object access
    assert c.get(f"{API}/portal/objects/case/describe").status_code == 403
    create(c, "note", {"related_to": mine["id"], "body": "internal only"}, name="Internal")
    create(c, "note", {"related_to": mine["id"], "body": "We're on it", "is_public": True}, name="Reply")
    portal.post(f"{API}/portal/objects/case/records/{mine['id']}/comments", json={"body": "Thanks!"})
    detail = portal.get(f"{API}/portal/objects/case/records/{mine['id']}").json()
    assert sorted(n["name"] for n in detail["timeline"]["note"]) == ["Comment from Pat Portal", "Reply"]

    inv = create(c, "invoice", {"account": acct["id"]})
    create(c, "invoice_line", {"invoice": inv["id"], "description": "Support", "unit_price": 50})
    other_inv = create(c, "invoice", {"account": other_acct["id"]})
    _ = other_inv
    assert (
        portal.get(f"{API}/portal/objects/invoice/records/{inv['id']}/pdf").status_code == 404
    )  # drafts hidden
    action(c, "invoice", inv["id"], "issue")
    invoices = portal.get(f"{API}/portal/objects/invoice/records").json()["items"]
    assert [i["id"] for i in invoices] == [inv["id"]]
    assert portal.get(f"{API}/portal/objects/invoice/records/{inv['id']}/pdf").content.startswith(b"%PDF")
    assert portal.get(f"{API}/objects/case/records").status_code == 403  # staff API
    assert c.get(f"{API}/portal/me").status_code == 403  # staff never use portal APIs
    users = c.get(f"{API}/portal-users").json()
    assert [u["email"] for u in users] == ["pat@customer.example"]
    c.post(f"{API}/portal-users/{users[0]['id']}/deactivate")
    assert portal.get(f"{API}/portal/me").status_code == 401


def test_public_web_forms(client: TestClient, admin_client: TestClient) -> None:
    anon = TestClient(client.app)
    assert anon.get(f"{API}/public/branding").json()["name"] == "Meridian CRM"
    r = anon.post(
        f"{API}/public/web-to-lead",
        json={"last_name": "Web", "company": "Web Co", "email": "web@lead.example", "email_opt_in": True},
    )
    assert r.status_code == 202
    bot = anon.post(f"{API}/public/web-to-lead", json={"last_name": "Bot", "website_url": "http://spam"})
    assert bot.status_code == 202
    leads = admin_client.get(f"{API}/objects/lead/records").json()["items"]
    assert [lead["name"] for lead in leads] == ["Web"] and leads[0]["fields"]["lead_source"] == "Web"
    consents = admin_client.get(f"{API}/objects/consent/records").json()["items"]
    assert consents[0]["fields"]["status"] == "Opted In" and consents[0]["fields"]["source"] == "Web Form"
    case = anon.post(
        f"{API}/public/web-to-case", json={"name": "Wendy", "email": "wendy@ex.example", "subject": "Broken"}
    )
    assert re.search(r"CASE-\d{5}", case.json()["message"])
    cases = admin_client.get(f"{API}/objects/case/records").json()["items"]
    assert cases[0]["fields"]["origin"] == "Web" and cases[0]["owner"]["name"] == "Customer Support"


# ------------------------------------------------------------------ Migration Agency pack


def test_migration_agency_pack(
    admin_client: TestClient, client: TestClient, db: Session, outbox: Outbox
) -> None:
    c = admin_client
    packs = c.get(f"{API}/setup/packs").json()
    assert packs[0]["key"] == "migration_agency" and packs[0]["installed_version"] is None
    assert c.get(f"{API}/objects/matter/records").status_code == 404
    installed = c.post(f"{API}/setup/packs/migration_agency/install").json()[0]
    assert installed["installed_version"] == "1.0.0" and installed["is_enabled"] is True
    assert "migration_practice" in {a["key"] for a in c.get(f"{API}/meta/apps").json()}

    agent_user = make_user(db, profile="ma_registered_agent", email="rma@practice.example")
    officer_user = make_user(db, profile="ma_case_officer", email="officer@practice.example")
    agent, officer = TestClient(client.app), TestClient(client.app)
    login(agent, agent_user.email)
    login(officer, officer_user.email)

    visa = create(
        c,
        "visa_type",
        {
            "subclass": "482",
            "stream": "Core Skills",
            "default_professional_fee": 3300,
            "checklist_template": "Passport\n- Skills assessment\nEnglish test results\n",
        },
        name="Skills in Demand",
    )
    client_contact = create(
        c,
        "contact",
        {
            "first_name": "Mia",
            "last_name": "Nguyen",
            "email": "mia@client.example",
            "passport_number": "PA1234567",
            "passport_expiry": "2031-01-01",
        },
    )
    assert client_contact["fields"]["passport_number"] == "PA1234567"  # encrypted at rest, admin can read
    stored = db.get(Record, uuid.UUID(client_contact["id"]))
    assert stored is not None and "PA1234567" not in json.dumps(stored.data)
    assert (
        "passport_number"
        not in get(as_user(client, db, "service_agent"), "contact", client_contact["id"])["fields"]
    )

    matter = create(
        agent,
        "matter",
        {"client": client_contact["id"], "visa_type": visa["id"], "case_officer": str(officer_user.id)},
    )
    assert re.fullmatch(rf"MAT-{date.today().year}-0001", matter["name"])
    assert matter["fields"]["professional_fee"] == 3300
    checklist = agent.get(f"{API}/objects/matter/records/{matter['id']}/related/checklist_item/matter").json()
    assert sorted(i["name"] for i in checklist["items"]) == [
        "English test results",
        "Passport",
        "Skills assessment",
    ]
    # The case officer reaches the matter through the team share.
    assert officer.get(f"{API}/objects/matter/records/{matter['id']}").status_code == 200

    url = f"{API}/objects/matter/records/{matter['id']}"
    gate = agent.patch(url, json={"version": matter["version"], "fields": {"stage": "Document Collection"}})
    assert gate.status_code == 422 and "signed service agreement" in gate.json()["error"]["message"]
    agreement = create(
        agent, "service_agreement", {"matter": matter["id"], "scope": "Prepare and lodge a 482 application."}
    )
    action(agent, "service_agreement", agreement["id"], "send", expect=422)  # Consumer Guide first
    ag = get(agent, "service_agreement", agreement["id"])
    agent.patch(
        f"{API}/objects/service_agreement/records/{agreement['id']}",
        json={"version": ag["version"], "fields": {"consumer_guide_provided": True}},
    )
    action(agent, "service_agreement", agreement["id"], "send")
    assert get(agent, "matter", matter["id"])["fields"]["stage"] == "Service Agreement"

    c.post(f"{API}/portal-users/invite/{client_contact['id']}")
    anon = TestClient(client.app)
    anon.post(
        f"{API}/auth/invitation/accept",
        json={"token": outbox.token_for("mia@client.example"), "password": "Client-Pass-2026!"},
    )
    portal = TestClient(client.app)
    login(portal, "mia@client.example", "Client-Pass-2026!")
    pm = portal.get(f"{API}/portal/objects/matter/records/{matter['id']}").json()
    assert "case_officer" not in pm["fields"] and "professional_fee" not in pm["fields"]
    sa = next(r for r in pm["related"] if r["object"] == "service_agreement")["items"][0]
    signed = portal.post(
        f"{API}/portal/objects/service_agreement/records/{sa['id']}/actions/sign",
        json={"full_name": "Mia Nguyen", "accept": True},
    )
    assert signed.status_code == 200, signed.text
    assert signed.json()["fields"]["status"] == "Signed"

    m = get(agent, "matter", matter["id"])
    m = agent.patch(url, json={"version": m["version"], "fields": {"stage": "Ready to Lodge"}}).json()
    assert m["fields"]["stage"] == "Ready to Lodge"
    # Case officers lack Lodge Applications.
    assert officer.post(f"{url}/actions/lodge", json={"immi_trn": "EGO123"}).status_code == 403
    lodged = action(agent, "matter", matter["id"], "lodge", {"immi_trn": "EGO1234567"})
    assert (
        lodged["fields"]["stage"] == "Lodged"
        and lodged["fields"]["lodgement_date"] == date.today().isoformat()
    )

    # Client account (trust ledger): never negative; transfer to office pays an issued invoice.
    accounts_user = make_user(db, profile="ma_accounts", email="trust@practice.example")
    accounts = TestClient(client.app)
    login(accounts, accounts_user.email)
    create(
        accounts,
        "client_account_transaction",
        {"client": client_contact["id"], "matter": matter["id"], "type": "Deposit", "amount": 1000},
    )
    over = accounts.post(
        f"{API}/objects/client_account_transaction/records",
        json={"fields": {"client": client_contact["id"], "type": "Withdrawal", "amount": 1500}},
    )
    assert over.status_code == 422 and "negative" in over.json()["error"]["message"]
    acct = create(c, "account", name="Mia household")
    inv = create(c, "invoice", {"account": acct["id"], "contact": client_contact["id"]})
    create(
        c,
        "invoice_line",
        {
            "invoice": inv["id"],
            "description": "Professional fee",
            "unit_price": 400,
            "tax_rate": str(record_id("record", "tax_rate.gst_free")),
        },
    )
    draft_transfer = accounts.post(
        f"{API}/objects/client_account_transaction/records",
        json={
            "fields": {
                "client": client_contact["id"],
                "type": "Transfer to Office",
                "amount": 400,
                "invoice": inv["id"],
            }
        },
    )
    assert draft_transfer.status_code == 422
    action(c, "invoice", inv["id"], "issue")
    tx = create(
        accounts,
        "client_account_transaction",
        {"client": client_contact["id"], "type": "Transfer to Office", "amount": 400, "invoice": inv["id"]},
    )
    assert tx["fields"]["balance_after"] == 600
    assert get(c, "invoice", inv["id"])["fields"]["status"] == "Paid"
    statement = accounts.get(f"{API}/packs/migration_agency/statement/{client_contact['id']}").json()
    assert statement["balance"] == 600 and [t["running_balance"] for t in statement["transactions"]] == [
        1000,
        600,
    ]
    assert accounts.delete(f"{API}/objects/client_account_transaction/records/{tx['id']}").status_code in (
        403,
        422,
    )

    from app.packs.migration_agency import expiry_reminders

    m = get(agent, "matter", matter["id"])
    db.expire_all()
    c.patch(
        url,
        json={
            "version": m["version"],
            "fields": {"visa_expiry": (date.today() + timedelta(days=30)).isoformat()},
        },
    )
    assert expiry_reminders(db) == 1
    assert expiry_reminders(db) == 0  # once per threshold
    reports = {r["key"] for r in c.get(f"{API}/reports").json()}
    assert {"ma_matters_by_stage", "ma_client_balances"} <= reports
    c.post(f"{API}/setup/packs/migration_agency/disable")
    assert c.get(f"{API}/objects/matter/records").status_code == 404
    assert "ma_matters_by_stage" not in {r["key"] for r in c.get(f"{API}/reports").json()}

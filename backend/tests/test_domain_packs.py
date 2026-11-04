"""Domain packs (plan v4, section 6): Legal Practice, Accounting Practice and Loan Broker, plus domain-first
navigation and terminology applied at sign-up."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import local_today
from app.models import Notification
from tests.conftest import Outbox, set_csrf
from tests.test_apps import action, get
from tests.test_records_engine import as_user, create

API = "/api/v1"


def patch(c: TestClient, obj: str, rid: str, fields: dict[str, Any], expect: int = 200) -> dict[str, Any]:
    current = get(c, obj, rid)
    r = c.patch(f"{API}/objects/{obj}/records/{rid}", json={"version": current["version"], "fields": fields})
    assert r.status_code == expect, r.text
    out: dict[str, Any] = r.json()
    return out


def install(c: TestClient, key: str) -> None:
    r = c.post(f"{API}/setup/packs/{key}/install")
    assert r.status_code == 200, r.text
    assert {p["key"]: p for p in r.json()}[key]["is_enabled"] is True


def related(c: TestClient, obj: str, field: str, rid: str) -> list[dict[str, Any]]:
    r = c.post(
        f"{API}/objects/{obj}/records/query",
        json={"filters": {"logic": "and", "conditions": [{"field": field, "op": "equals", "value": rid}]}},
    )
    assert r.status_code == 200, r.text
    records: list[dict[str, Any]] = r.json()["items"]
    return records


def test_all_domain_packs_are_available(admin_client: TestClient) -> None:
    keys = {p["key"] for p in admin_client.get(f"{API}/setup/packs").json()}
    assert {"legal_practice", "migration_agency", "accounting_practice", "loan_broker"} <= keys


# ------------------------------------------------------------------ legal


def test_legal_practice_pack(admin_client: TestClient, client: TestClient, db: Session) -> None:
    c = admin_client
    install(c, "legal_practice")
    client_contact = create(c, "contact", {"first_name": "Grace", "last_name": "Hopper"})
    matter = create(
        c,
        "legal_matter",
        {"title": "Hopper property purchase", "client": client_contact["id"], "practice_area": "Family"},
    )
    matter = get(c, "legal_matter", matter["id"])
    assert matter["name"].startswith("LM-")
    # A conflict check ran on opening: nothing else on file, so it is clear.
    checks = related(c, "conflict_check", "legal_matter", matter["id"])
    assert len(checks) == 1 and checks[0]["fields"]["result"] == "Clear"
    assert matter["fields"]["stage"] == "Conflict Check" and matter["fields"]["conflict_cleared"] is True

    # Costs disclosure is required before engaging (no estimate means it may exceed $750).
    r = c.patch(
        f"{API}/objects/legal_matter/records/{matter['id']}",
        json={"version": matter["version"], "fields": {"stage": "Engaged"}},
    )
    assert r.status_code == 422 and "costs disclosure" in r.text.lower()
    matter = patch(c, "legal_matter", matter["id"], {"costs_disclosure_provided": True, "stage": "Engaged"})
    assert matter["fields"]["costs_disclosure_date"] == local_today().isoformat()

    # A second matter where Grace is the other party -> potential conflict, cleared only by a principal.
    other_client = create(c, "contact", {"first_name": "Alan", "last_name": "Turing"})
    second = create(c, "legal_matter", {"title": "Turing v Hopper", "client": other_client["id"]})
    create(c, "party", {"legal_matter": second["id"], "role": "Other Party"}, name="Grace Hopper")
    second = get(c, "legal_matter", second["id"])
    assert second["fields"]["conflict_cleared"] is False
    flagged = [
        x
        for x in related(c, "conflict_check", "legal_matter", second["id"])
        if x["fields"]["result"] != "Clear"
    ]
    assert flagged and "Grace Hopper" in flagged[0]["fields"]["matches"]
    solicitor = as_user(client, db, "lp_solicitor")
    r = solicitor.patch(
        f"{API}/objects/conflict_check/records/{flagged[0]['id']}",
        json={"version": flagged[0]["version"], "fields": {"result": "Clear", "clearance_notes": "x"}},
    )
    assert r.status_code in (403, 404, 422)
    patch(c, "conflict_check", flagged[0]["id"], {"result": "Clear"}, expect=422)  # notes required
    patch(
        c,
        "conflict_check",
        flagged[0]["id"],
        {"result": "Clear", "clearance_notes": "Different person, ID checked"},
    )
    assert get(c, "legal_matter", second["id"])["fields"]["conflict_cleared"] is True

    # Time in 6-minute units -> WIP -> invoice.
    entry = create(
        c, "legal_time_entry", {"legal_matter": matter["id"], "units": 15, "rate": 400, "narrative": "Advice"}
    )
    assert entry["fields"]["hours"] == 1.5 and float(entry["fields"]["amount"]) == 600
    create(
        c, "legal_time_entry", {"legal_matter": matter["id"], "units": 3, "rate": 400, "narrative": "Letter"}
    )
    assert float(get(c, "legal_matter", matter["id"])["fields"]["unbilled_amount"]) == 720
    billed = action(c, "legal_matter", matter["id"], "bill_time")
    assert billed["entries"] == 2
    invoice = get(c, "invoice", billed["invoice_id"])
    assert invoice["fields"]["legal_matter"] == matter["id"] and float(invoice["fields"]["subtotal"]) == 720
    assert float(get(c, "legal_matter", matter["id"])["fields"]["unbilled_amount"]) == 0
    patch(c, "legal_time_entry", entry["id"], {"units": 1}, expect=422)  # billed time is locked
    # An individual is billed through one organisation in their name, reused on their next matter.
    billing = invoice["fields"]["account"]
    assert get(c, "contact", client_contact["id"])["fields"]["account"] == billing
    later = create(c, "legal_matter", {"title": "Hopper will", "client": client_contact["id"]})
    create(c, "legal_time_entry", {"legal_matter": later["id"], "units": 2, "rate": 400, "narrative": "Will"})
    again = action(c, "legal_matter", later["id"], "bill_time")
    assert get(c, "invoice", again["invoice_id"])["fields"]["account"] == billing

    # Trust ledger: no overdraw, transfers only against the matter's issued invoices, append-only.
    t = {"legal_matter": matter["id"], "payer_payee": "Grace Hopper", "description": "Funds on account"}
    r = c.post(
        f"{API}/objects/trust_transaction/records", json={"fields": {**t, "type": "Payment", "amount": 10}}
    )
    assert r.status_code == 422 and "overdrawn" in r.text
    receipt = create(c, "trust_transaction", {**t, "type": "Receipt", "amount": 1000})
    assert float(receipt["fields"]["balance_after"]) == 1000
    r = c.post(
        f"{API}/objects/trust_transaction/records",
        json={"fields": {**t, "type": "Transfer to Office", "amount": 100, "invoice": invoice["id"]}},
    )
    assert r.status_code == 422  # invoice still a draft
    action(c, "invoice", invoice["id"], "issue")
    issued = get(c, "invoice", invoice["id"])
    transfer = create(
        c,
        "trust_transaction",
        {**t, "type": "Transfer to Office", "amount": issued["fields"]["total"], "invoice": invoice["id"]},
    )
    assert get(c, "invoice", invoice["id"])["fields"]["status"] == "Paid"
    patch(c, "trust_transaction", transfer["id"], {"reference": "x"}, expect=422)
    statement = c.get(f"{API}/packs/legal_practice/trust-statement/{matter['id']}").json()
    assert len(statement["transactions"]) == 2
    balance = float(statement["balance"])
    if balance:
        r = c.patch(
            f"{API}/objects/legal_matter/records/{matter['id']}",
            json={"version": get(c, "legal_matter", matter["id"])["version"], "fields": {"stage": "Closed"}},
        )
        assert r.status_code == 422 and "trust" in r.text

    # Limitation-date reminder to the responsible solicitor.
    soon = (local_today() + timedelta(days=30)).isoformat()
    patch(c, "legal_matter", matter["id"], {"limitation_date": soon})
    from app.packs.legal_practice import daily_reminders

    assert daily_reminders(db) >= 1
    assert db.scalar(select(Notification.id).where(Notification.title.like("Limitation date in 30 days%")))


# ------------------------------------------------------------------ accounting


def portal_for(
    c: TestClient, app_client: TestClient, outbox: Outbox, contact_id: str, email: str
) -> TestClient:
    """Invite a client contact to the portal and sign them in."""
    from tests.conftest import login

    assert c.post(f"{API}/portal-users/invite/{contact_id}").status_code == 201
    anon = TestClient(app_client.app)
    r = anon.post(
        f"{API}/auth/invitation/accept",
        json={"token": outbox.token_for(email), "password": "Sunny-Harbour-2026!"},
    )
    assert r.status_code == 200, r.text
    portal = TestClient(app_client.app)
    assert login(portal, email, "Sunny-Harbour-2026!") == "authenticated"
    return portal


def test_accounting_practice_pack(
    admin_client: TestClient, client: TestClient, db: Session, outbox: Outbox
) -> None:
    c = admin_client
    install(c, "accounting_practice")
    entity = create(
        c,
        "account",
        {"entity_type": "Company", "bas_frequency": "Quarterly", "gst_registered": True},
        name="Wattle Pty Ltd",
    )
    eng = create(c, "engagement", {"client": entity["id"], "type": "Company Tax Return", "fee": 2200})
    eng = get(c, "engagement", eng["id"])
    assert eng["name"].startswith("JOB-") and eng["fields"]["financial_year"]
    assert eng["fields"]["due_date"].endswith("-02-28")  # default company return due date
    docs = related(c, "document_request", "engagement", eng["id"])
    assert len(docs) == 3
    assert len(related(c, "lodgement_deadline", "engagement", eng["id"])) == 1

    # APES 305: no work before the engagement letter is signed.
    patch(c, "engagement", eng["id"], {"stage": "In Progress"}, expect=422)
    letter = create(
        c, "engagement_letter", {"engagement": eng["id"], "scope": "Prepare and lodge the company return."}
    )
    assert float(letter["fields"]["fee_estimate"]) == 2200
    action(c, "engagement_letter", letter["id"], "send")
    sign = {"full_name": "Wendy Wattle", "accept": True}
    # The signature is the client's own: staff can't sign for them, and don't see the action.
    r = c.post(f"{API}/objects/engagement_letter/records/{letter['id']}/actions/sign", json=sign)
    assert r.status_code == 403
    assert "sign" not in {a["name"] for a in get(c, "engagement_letter", letter["id"])["actions"]}
    wendy = create(
        c,
        "contact",
        {
            "first_name": "Wendy",
            "last_name": "Wattle",
            "email": "wendy@wattle.example",
            "account": entity["id"],
        },
    )
    portal = portal_for(c, client, outbox, wendy["id"], "wendy@wattle.example")
    r = portal.post(f"{API}/portal/objects/engagement_letter/records/{letter['id']}/actions/sign", json=sign)
    assert r.status_code == 200, r.text
    assert get(c, "engagement_letter", letter["id"])["fields"]["status"] == "Signed"
    eng = get(c, "engagement", eng["id"])
    assert eng["fields"]["letter_signed"] is True and eng["fields"]["stage"] == "Awaiting Information"

    # Accepting every document request moves the job on.
    for doc in docs:
        patch(c, "document_request", doc["id"], {"status": "Accepted"})
    assert get(c, "engagement", eng["id"])["fields"]["stage"] == "In Progress"

    # Time, WIP and recoverability.
    create(
        c,
        "engagement_time_entry",
        {"engagement": eng["id"], "units": 50, "rate": 200, "narrative": "Prepare return"},
    )
    eng = get(c, "engagement", eng["id"])
    assert float(eng["fields"]["time_cost"]) == 1000 and float(eng["fields"]["recoverability"]) == 220

    # Review by someone other than the preparer before it is ready to lodge.
    patch(c, "engagement", eng["id"], {"stage": "Review"})
    patch(c, "engagement", eng["id"], {"stage": "Ready to Lodge"}, expect=422)
    me = c.get(f"{API}/auth/me").json()["user"]["id"]
    patch(c, "engagement", eng["id"], {"reviewer": me, "responsible_accountant": me})
    patch(c, "engagement", eng["id"], {"stage": "Ready to Lodge"}, expect=422)  # reviewer = preparer
    other = as_user(client, db, "ap_accountant")
    other_id = other.get(f"{API}/auth/me").json()["user"]["id"]
    patch(c, "engagement", eng["id"], {"responsible_accountant": other_id})
    patch(c, "engagement", eng["id"], {"stage": "Ready to Lodge"})
    eng = patch(c, "engagement", eng["id"], {"stage": "Lodged"})
    assert eng["fields"]["lodged_date"] == local_today().isoformat()
    deadline = related(c, "lodgement_deadline", "engagement", eng["id"])[0]
    assert deadline["fields"]["status"] == "Lodged"

    billed = action(c, "engagement", eng["id"], "create_invoice")
    assert float(get(c, "invoice", billed["invoice_id"])["fields"]["subtotal"]) == 2200
    action(c, "engagement", eng["id"], "create_invoice", expect=422)  # fixed fee invoiced once

    # BAS deadlines from the client's frequency; overdue marking.
    made = action(c, "account", entity["id"], "generate_bas_deadlines")
    assert 1 <= made["created"] <= 4
    past = create(
        c, "lodgement_deadline", {"client": entity["id"], "lodgement_type": "IAS", "due_date": "2020-01-21"}
    )
    assert past["fields"]["status"] == "Overdue"


def test_financial_year_helpers() -> None:
    from app.packs.accounting_practice import bas_periods, financial_year

    assert financial_year(date(2026, 11, 4), ended=False) == "2026-27"
    assert financial_year(date(2026, 11, 4), ended=True) == "2025-26"
    assert financial_year(date(2026, 3, 1), ended=True) == "2024-25"
    assert [d.isoformat() for _, d in bas_periods("Quarterly", 2026)] == [
        "2026-10-28", "2027-02-28", "2027-04-28", "2027-07-28",
    ]  # fmt: skip
    monthly = bas_periods("Monthly", 2026)
    assert (
        len(monthly) == 12 and monthly[0][1] == date(2026, 8, 21) and monthly[5][1] == date(2027, 2, 21)
    )  # December: 21 February


# ------------------------------------------------------------------ loan broking


def test_loan_broker_pack(admin_client: TestClient, client: TestClient, db: Session) -> None:
    c = admin_client
    install(c, "loan_broker")
    lender = create(
        c,
        "lender",
        {"lender_type": "Major Bank", "upfront_rate": 0.65, "trail_rate": 0.15},
        name="Harbour Bank",
    )
    borrower = create(c, "contact", {"first_name": "Sam", "last_name": "Lee"})
    loan = create(
        c,
        "loan_application",
        {
            "primary_borrower": borrower["id"],
            "purpose": "Purchase - Owner Occupied",
            "loan_amount": 600000,
            "security_value": 800000,
        },
    )
    assert loan["name"].startswith("LA-") and float(loan["fields"]["lvr"]) == 75

    # NCCP: credit guide and consent before credit assistance; assessment + BID before lodging.
    patch(c, "loan_application", loan["id"], {"stage": "Preliminary Assessment"}, expect=422)
    today = local_today().isoformat()
    patch(
        c,
        "loan_application",
        loan["id"],
        {"credit_guide_date": today, "privacy_consent_date": today, "stage": "Fact Find"},
    )
    action(c, "loan_application", loan["id"], "record_assessment", expect=422)
    ff = create(c, "fact_find", {"loan_application": loan["id"], "gross_annual_income": 180000, "monthly_living_expenses": 4000,
                                 "monthly_commitments": 500, "total_assets": 250000, "total_liabilities": 20000})  # fmt: skip
    assert float(ff["fields"]["net_position"]) == 230000 and float(ff["fields"]["monthly_surplus"]) == 10500
    patch(c, "fact_find", ff["id"], {"status": "Complete"})
    patch(
        c,
        "loan_application",
        loan["id"],
        {"customer_objectives": "Buy a home, offset account", "products_considered": "Harbour Bank, Two Bank",
         "recommendation_reason": "Lowest cost with offset", "lender": lender["id"]},
    )  # fmt: skip
    patch(c, "loan_application", loan["id"], {"stage": "Lodged"}, expect=422)
    assessed = action(c, "loan_application", loan["id"], "record_assessment")
    assert (
        assessed["fields"]["bid_completed"] is True
        and assessed["fields"]["stage"] == "Preliminary Assessment"
    )
    patch(c, "loan_application", loan["id"], {"recommendation_reason": "changed"}, expect=422)  # BID locked
    processor = as_user(client, db, "lb_processor")
    r = processor.patch(
        f"{API}/objects/loan_application/records/{loan['id']}",
        json={"version": assessed["version"], "fields": {"stage": "Lodged"}},
    )
    assert r.status_code in (403, 404, 422)
    loan = patch(c, "loan_application", loan["id"], {"stage": "Lodged"})
    assert loan["fields"]["lodged_date"] == today

    # Settlement creates the expected upfront commission from the lender's rate.
    loan = patch(c, "loan_application", loan["id"], {"stage": "Settled"})
    assert loan["fields"]["settlement_date"] == today and float(loan["fields"]["expected_upfront"]) == 3900
    commissions = related(c, "commission", "loan_application", loan["id"])
    assert len(commissions) == 1 and float(commissions[0]["fields"]["amount"]) == 3900
    claw = create(c, "commission", {"loan_application": loan["id"], "type": "Clawback", "amount": 1950})
    assert float(claw["fields"]["signed_amount"]) == -1950
    patch(c, "commission", claw["id"], {"amount": 1}, expect=422)
    r = c.delete(f"{API}/objects/loan_application/records/{loan['id']}")
    assert r.status_code == 422  # BID records kept 7 years


# ------------------------------------------------------------------ provisioning per domain


@pytest.mark.parametrize(
    ("domain", "app_key", "core_object", "client_label"),
    [
        ("legal", "legal_practice", "legal_matter", "Client"),
        ("migration", "migration_practice", "matter", "Client"),
        ("accounting", "accounting_practice", "engagement", "Contact Person"),
        ("lending", "loan_broking", "loan_application", "Client"),
    ],
)
def test_signup_shapes_the_workspace(
    client: TestClient,
    outbox: Outbox,
    no_mfa: None,
    domain: str,
    app_key: str,
    core_object: str,
    client_label: str,
) -> None:
    email = f"admin@{domain}.example.com"
    body = {
        "domain": domain,
        "firm_name": f"{domain.title()} Firm",
        "name": "Ada Admin",
        "email": email,
        "password": "Fresh-Firm-Password-77",
        "accept_terms": True,
    }
    assert client.post(f"{API}/signup", json=body).status_code in (200, 201, 202)
    r = client.post(f"{API}/signup/verify", json={"token": outbox.token_for(email)})
    assert r.status_code == 200, r.text
    set_csrf(client)
    apps = client.get(f"{API}/meta/apps").json()
    keys = [a["key"] for a in apps]
    assert keys[0] == app_key and apps[0]["is_primary"] is True
    assert not {"sales", "service", "marketing", "billing"} & set(keys)
    contact = client.get(f"{API}/meta/objects/contact").json()
    assert contact["label"] == client_label
    views = {v["name"] for v in contact.get("list_views", [])}
    assert not any("Contacts" in v for v in views)
    # The domain's core record can be created straight away.
    describe = client.get(f"{API}/meta/objects/{core_object}")
    assert describe.status_code == 200


def test_domain_related_lists_follow_the_visible_apps(db: Session) -> None:
    from sqlalchemy import select as _select

    from app.domains import apply_domain
    from app.models import ObjectDefinition

    apply_domain(db, "migration", None)
    db.flush()
    contact = db.scalar(_select(ObjectDefinition).where(ObjectDefinition.api_name == "contact"))
    assert contact is not None
    objects = [rl["object"] for rl in contact.related_lists]
    assert objects[0] == "matter"
    assert "opportunity" not in objects and "case" not in objects and "campaign_member" not in objects
    assert "consent" in objects and "invoice" in objects
    db.rollback()


def test_accounting_safeguards(admin_client: TestClient, client: TestClient, db: Session) -> None:
    from app.core.validators import is_valid_tfn
    from app.packs.accounting_practice import bas_periods
    from tests.conftest import login, make_user

    c = admin_client
    install(c, "accounting_practice")
    assert is_valid_tfn("123 456 782") and not is_valid_tfn("123456789")
    assert dict(bas_periods("Monthly", 2026))["Dec 2026"].isoformat() == "2027-02-21"
    bad = c.post(
        f"{API}/objects/account/records", json={"name": "Typo Pty Ltd", "fields": {"tfn": "123456789"}}
    )
    assert bad.status_code == 422 and "TFN" in bad.text
    entity = create(c, "account", {"entity_type": "Company", "tfn": "123456782"}, name="Gum Tree Pty Ltd")
    assert get(c, "account", entity["id"])["fields"]["tfn"] == "123456782"

    # The client manager works the client's file without owning it.
    manager_user = make_user(db, profile="ap_accountant", email="cm@ledger.example")
    manager = TestClient(client.app)
    login(manager, manager_user.email)
    patch(c, "account", entity["id"], {"client_manager": str(manager_user.id), "bas_frequency": "Quarterly"})
    assert manager.get(f"{API}/objects/account/records/{entity['id']}").status_code == 200
    assert action(manager, "account", entity["id"], "generate_bas_deadlines")["created"] >= 0

    # Preparer with lodging rights still can't sign off their own review.
    reviewer_user = make_user(db, profile="ap_accountant", email="rev@ledger.example")
    eng = create(manager, "engagement", {"client": entity["id"], "type": "Advisory", "fee": 900})
    letter = create(manager, "engagement_letter", {"engagement": eng["id"], "scope": "Structure advice."})
    action(manager, "engagement_letter", letter["id"], "send")
    # Signed on paper: only a partner records it; with nothing to request the work starts.
    action(
        manager,
        "engagement_letter",
        letter["id"],
        "record_paper_signature",
        {"full_name": "Gus Gum", "reason": "x"},
        expect=403,
    )
    action(
        c, "engagement_letter", letter["id"], "record_paper_signature", {"full_name": "Gus Gum"}, expect=422
    )
    action(
        c,
        "engagement_letter",
        letter["id"],
        "record_paper_signature",
        {"full_name": "Gus Gum", "reason": "Scan attached"},
    )
    assert get(c, "engagement", eng["id"])["fields"]["stage"] == "In Progress"
    patch(manager, "engagement", eng["id"], {"reviewer": str(reviewer_user.id), "stage": "Review"})
    r = manager.patch(
        f"{API}/objects/engagement/records/{eng['id']}",
        json={
            "version": get(manager, "engagement", eng["id"])["version"],
            "fields": {"stage": "Ready to Lodge"},
        },
    )
    assert r.status_code == 422 and "reviewer" in r.text.lower()

    # The return's deadline follows the engagement's due date.
    ret = create(manager, "engagement", {"client": entity["id"], "type": "Company Tax Return"})
    later = (local_today() + timedelta(days=90)).isoformat()
    patch(manager, "engagement", ret["id"], {"due_date": later})
    deadlines = related(c, "lodgement_deadline", "engagement", ret["id"])
    assert [d["fields"]["due_date"] for d in deadlines] == [later]

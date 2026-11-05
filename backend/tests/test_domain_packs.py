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


def practice_tan(db: Session, number: str = "25678009") -> None:
    """The practice's tax agent number (engagement letters show it)."""
    from app.services.settings import get_setting, set_setting

    set_setting(
        db,
        "accounting_practice",
        {**(get_setting(db, "accounting_practice") or {}), "tax_agent_number": number},
    )
    db.commit()


def test_accounting_practice_pack(
    admin_client: TestClient, client: TestClient, db: Session, outbox: Outbox
) -> None:
    c = admin_client
    install(c, "accounting_practice")
    practice_tan(db)
    entity = create(
        c,
        "account",
        {"entity_type": "Company", "bas_frequency": "Quarterly", "gst_registered": True,
         "identity_verified": True, "agent_nominated": True},
        name="Wattle Pty Ltd",
    )  # fmt: skip
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
        len(monthly) == 12 and monthly[0][1] == date(2026, 8, 21) and monthly[5][1] == date(2027, 1, 21)
    )  # December: 21 January, or 21 February under the registered agent lodgment program
    assert dict(bas_periods("Monthly", 2026, tax_agent=True))["Dec 2026"] == date(2027, 2, 21)
    assert bas_periods("Annually", 2026) == [("FY 2026-27", date(2027, 10, 31))]  # annual GST return


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
            "interest_rate": 6.0,
            "term_years": 30,
        },
    )
    assert loan["name"].startswith("LA-") and float(loan["fields"]["lvr"]) == 75
    # Assessed at the product rate plus the 3% buffer.
    assert (
        float(loan["fields"]["assessment_rate"]) == 9
        and 4800 < float(loan["fields"]["estimated_repayment"]) < 4900
    )

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
    action(
        c, "loan_application", loan["id"], "record_assessment", expect=422
    )  # income and expenses unverified
    patch(c, "fact_find", ff["id"], {"expenses_verified": True})
    patch(
        c,
        "loan_application",
        loan["id"],
        {"customer_objectives": "Buy a home, offset account", "products_considered": "Harbour Bank, Two Bank",
         "recommendation_reason": "Lowest cost with offset", "lender": lender["id"], "credit_proposal_date": today},
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
    practice_tan(db)
    assert is_valid_tfn("123 456 782") and not is_valid_tfn("123456789")
    assert dict(bas_periods("Monthly", 2026))["Dec 2026"].isoformat() == "2027-01-21"
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


def test_loan_broker_safeguards(admin_client: TestClient, client: TestClient, db: Session) -> None:
    from tests.conftest import login, make_user

    c = admin_client
    install(c, "loan_broker")
    broker_user = make_user(db, profile="lb_broker", email="bro@loans.example")
    broker = TestClient(client.app)
    login(broker, broker_user.email)
    lender = create(c, "lender", {"upfront_rate": 0.6}, name="Harbour Bank")
    other = create(c, "lender", {"upfront_rate": 0.5}, name="Two Bank")
    person = create(broker, "contact", {"first_name": "Ana", "last_name": "Ruiz"})
    today = local_today().isoformat()
    loan = create(
        broker,
        "loan_application",
        {"primary_borrower": person["id"], "purpose": "Refinance", "loan_amount": 500000, "lender": lender["id"],
         "credit_guide_date": today, "privacy_consent_date": today, "customer_objectives": "Lower rate",
         "products_considered": "Harbour, Two", "recommendation_reason": "Cheapest", "interest_rate": 6.0,
         "term_years": 30, "credit_proposal_date": today},
    )  # fmt: skip
    ff = create(
        broker,
        "fact_find",
        {"loan_application": loan["id"], "gross_annual_income": 150000, "monthly_living_expenses": 3000,
         "expenses_verified": True},
    )  # fmt: skip
    patch(broker, "fact_find", ff["id"], {"status": "Complete"})
    action(broker, "loan_application", loan["id"], "record_assessment")
    # Switching lender after the assessment means assessing again before lodging.
    assert (
        patch(broker, "loan_application", loan["id"], {"lender": other["id"]})["fields"]["bid_completed"]
        is False
    )
    patch(broker, "loan_application", loan["id"], {"stage": "Lodged"}, expect=422)
    action(broker, "loan_application", loan["id"], "record_assessment")
    patch(broker, "loan_application", loan["id"], {"stage": "Lodged"})
    patch(c, "loan_application", loan["id"], {"stage": "Settled"})
    # Settled is final for a broker (a principal can correct a mistake).
    patch(broker, "loan_application", loan["id"], {"stage": "Declined", "decline_reason": "x"}, expect=422)
    # The broker reads the commission on their loan.
    mine = broker.post(f"{API}/objects/commission/records/query", json={}).json()["items"]
    assert [m["fields"]["type"] for m in mine] == ["Upfront"]


def test_legal_uniform_law_rules(admin_client: TestClient, client: TestClient, db: Session) -> None:
    """Costs disclosure tiers and changes, VOI, limitation dates, closing, fixed fees and trust cash."""
    c = admin_client
    install(c, "legal_practice")
    person = create(c, "contact", {"first_name": "Vera", "last_name": "Voi"})

    # Conveyancing: the client's identity is verified (VOI) before engaging.
    conv = create(
        c,
        "legal_matter",
        {"title": "Sale of 1 Elm St", "client": person["id"], "practice_area": "Property & Conveyancing",
         "estimated_costs": 1800, "billing_method": "Fixed Fee", "fixed_fee": 1650},
    )  # fmt: skip
    r = c.patch(
        f"{API}/objects/legal_matter/records/{conv['id']}",
        json={
            "version": get(c, "legal_matter", conv["id"])["version"],
            "fields": {"costs_disclosure_provided": True, "stage": "Engaged"},
        },
    )
    assert r.status_code == 422 and "VOI" in r.text
    patch(c, "contact", person["id"], {"id_verified": True})
    # $1,800 may use the uniform standard disclosure form.
    m = patch(
        c, "legal_matter", conv["id"],
        {"costs_disclosure_provided": True, "disclosure_method": "Uniform Standard Disclosure Form", "stage": "Engaged"},
    )  # fmt: skip
    assert m["fields"]["stage"] == "Engaged"
    # ...but not once the estimate passes $3,000, and the rise needs updated disclosure.
    patch(c, "legal_matter", conv["id"], {"estimated_costs": 4000}, expect=422)
    m = patch(
        c,
        "legal_matter",
        conv["id"],
        {"estimated_costs": 4000, "disclosure_method": "Full Written Disclosure"},
    )
    assert m["fields"]["disclosure_update_due"] is True
    action(c, "legal_matter", conv["id"], "bill_fixed_fee", expect=422)  # disclose the change first
    m = patch(
        c,
        "legal_matter",
        conv["id"],
        {"costs_disclosure_date": (local_today() + timedelta(days=1)).isoformat()},
    )
    assert m["fields"]["disclosure_update_due"] is False
    billed = action(c, "legal_matter", conv["id"], "bill_fixed_fee")
    invoice = get(c, "invoice", billed["invoice_id"])
    assert float(invoice["fields"]["subtotal"]) == 1650
    action(c, "legal_matter", conv["id"], "bill_fixed_fee", expect=422)  # once
    action(c, "invoice", invoice["id"], "issue")
    assert float(get(c, "legal_matter", conv["id"])["fields"]["billed_to_date"]) == 1650

    # Commercial clients don't need disclosure (s 170); claims need a limitation date before engaging.
    acme = create(c, "contact", {"last_name": "Acme Legal Dept"})
    claim = create(
        c, "legal_matter",
        {"title": "Acme v Supplier", "client": acme["id"], "practice_area": "Litigation", "client_type": "Commercial or Government"},
    )  # fmt: skip
    r = c.patch(
        f"{API}/objects/legal_matter/records/{claim['id']}",
        json={"version": get(c, "legal_matter", claim["id"])["version"], "fields": {"stage": "Engaged"}},
    )
    assert r.status_code == 422 and "limitation date" in r.text
    m = patch(c, "legal_matter", claim["id"], {"limitation_date": "2029-06-30", "stage": "Engaged"})
    assert m["fields"]["stage"] == "Engaged" and not m["fields"]["costs_disclosure_provided"]

    # Billing past the disclosed estimate is refused until the estimate is updated and disclosed.
    hourly = create(c, "legal_matter", {"title": "Advice", "client": person["id"], "estimated_costs": 1000})
    patch(c, "legal_matter", hourly["id"], {"costs_disclosure_provided": True, "stage": "Engaged"})
    create(
        c, "legal_time_entry", {"legal_matter": hourly["id"], "units": 40, "rate": 400, "narrative": "Advice"}
    )
    r = c.post(f"{API}/objects/legal_matter/records/{hourly['id']}/actions/bill_time", json={})
    assert r.status_code == 422 and "estimate" in r.text
    # Closing needs the WIP billed or written off.
    r = c.patch(
        f"{API}/objects/legal_matter/records/{hourly['id']}",
        json={"version": get(c, "legal_matter", hourly["id"])["version"], "fields": {"stage": "Closed"}},
    )
    assert r.status_code == 422 and "unbilled" in r.text

    # Trust: never paid out in cash; a $10,000 cash receipt creates an AUSTRAC task.
    t = {"legal_matter": hourly["id"], "payer_payee": "Vera Voi", "description": "Funds"}
    receipt = create(c, "trust_transaction", {**t, "type": "Receipt", "amount": 12000, "method": "Cash"})
    tasks = c.post(f"{API}/objects/task/records/query", json={}).json()["items"]
    assert any("AUSTRAC" in x["name"] for x in tasks)
    assert get(c, "trust_transaction", receipt["id"])["access"]["edit"] is True  # reference still to record
    patch(c, "trust_transaction", receipt["id"], {"austrac_reference": "SCTR-1234"})
    patch(c, "trust_transaction", receipt["id"], {"amount": 1}, expect=422)  # still append-only
    assert get(c, "trust_transaction", receipt["id"])["access"]["edit"] is False
    # A practice that reports from a lower amount can record the reference on those receipts too.
    r = c.put(
        f"{API}/setup/practice-settings/legal_practice", json={"values": {"significant_cash_threshold": 5000}}
    )
    assert r.status_code == 200, r.text
    smaller = create(c, "trust_transaction", {**t, "type": "Receipt", "amount": 6000, "method": "Cash"})
    assert get(c, "trust_transaction", smaller["id"])["access"]["edit"] is True
    patch(c, "trust_transaction", smaller["id"], {"austrac_reference": "SCTR-5678"})
    small = create(c, "trust_transaction", {**t, "type": "Receipt", "amount": 900, "method": "Cash"})
    assert get(c, "trust_transaction", small["id"])["access"]["edit"] is False
    r = c.post(
        f"{API}/objects/trust_transaction/records",
        json={"fields": {**t, "type": "Payment", "amount": 100, "method": "Cash"}},
    )
    assert r.status_code == 422 and "cash" in r.text.lower()


def test_monthly_trust_reconciliation(admin_client: TestClient, client: TestClient, db: Session) -> None:
    from app.packs.legal_practice import reconciliation_reminders
    from tests.conftest import login, make_user

    c = admin_client
    install(c, "legal_practice")
    person = create(c, "contact", {"first_name": "Rex", "last_name": "Recon"})
    matter = create(c, "legal_matter", {"title": "Estate", "client": person["id"]})
    t = {"legal_matter": matter["id"], "payer_payee": "Rex Recon", "description": "Funds", "method": "EFT"}
    create(c, "trust_transaction", {**t, "type": "Receipt", "amount": 5000, "transaction_date": "2026-09-14"})
    create(c, "trust_transaction", {**t, "type": "Payment", "amount": 1200, "transaction_date": "2026-09-20"})
    create(c, "trust_transaction", {**t, "type": "Receipt", "amount": 300, "transaction_date": "2026-10-02"})
    bad = c.post(
        f"{API}/objects/trust_reconciliation/records",
        json={"fields": {"period_end": "2026-09-15", "bank_balance": 3800}},
    )
    assert bad.status_code == 422 and "last day of the month" in bad.text
    # The trust accountant prepares it; the principal signs it off.
    accountant_user = make_user(db, profile="lp_accounts", email="trustacct@firm.example")
    accountant = TestClient(client.app)
    login(accountant, accountant_user.email)
    rec = create(accountant, "trust_reconciliation", {"period_end": "2026-09-30", "bank_balance": 4000})
    assert rec["name"] == "Trust reconciliation September 2026"
    assert float(rec["fields"]["ledger_total"]) == 3800 and float(rec["fields"]["difference"]) == 200
    patch(
        accountant, "trust_reconciliation", rec["id"], {"status": "Reconciled"}, expect=422
    )  # doesn't balance
    patch(
        accountant,
        "trust_reconciliation",
        rec["id"],
        {"adjustments": -200, "notes": "Cheque 1042 unpresented"},
    )
    r = accountant.patch(
        f"{API}/objects/trust_reconciliation/records/{rec['id']}",
        json={
            "version": get(c, "trust_reconciliation", rec["id"])["version"],
            "fields": {"status": "Reconciled"},
        },
    )
    assert r.status_code == 422 and "principal" in r.text  # a principal signs off
    done = patch(c, "trust_reconciliation", rec["id"], {"status": "Reconciled"})
    assert done["fields"]["reconciled_by"] and done["access"]["edit"] is False
    patch(c, "trust_reconciliation", rec["id"], {"notes": "x"}, expect=422)
    dup = c.post(
        f"{API}/objects/trust_reconciliation/records",
        json={"fields": {"period_end": "2026-09-30", "bank_balance": 3800}},
    )
    assert dup.status_code == 422
    # October isn't reconciled: from 10 November principals and trust accountants are reminded (once).
    from datetime import date as _date

    assert reconciliation_reminders(db, _date(2026, 11, 12)) >= 1
    assert reconciliation_reminders(db, _date(2026, 11, 13)) == 0
    db.commit()


def test_accounting_tax_agent_obligations(
    admin_client: TestClient, client: TestClient, db: Session, outbox: Outbox
) -> None:
    """FBT year, BAS concession dates, proof of identity and agent linking, auditor independence, TAN."""
    from datetime import date as _date

    from app.packs.accounting_practice import bas_periods, default_due_date, fbt_year
    from app.services.settings import get_setting, set_setting
    from tests.conftest import login, make_user

    assert fbt_year(_date(2026, 5, 1)) == "2025-26" and fbt_year(_date(2026, 3, 1)) == "2024-25"
    c = admin_client
    install(c, "accounting_practice")
    assert default_due_date(db, "FBT Return", "2025-26") == "2026-05-21"  # FBT year ends 31 March
    assert default_due_date(db, "Individual Tax Return", "2025-26") == "2026-10-31"
    assert default_due_date(db, "Company Tax Return", "2025-26") == "2027-02-28"
    q = dict(bas_periods("Quarterly", 2026, tax_agent=True))
    assert q["Q1 Jul-Sep"].isoformat() == "2026-11-25" and q["Q3 Jan-Mar"].isoformat() == "2027-05-26"

    # Letters name the practitioner and their registration; without a number they aren't sent.
    preparer_user = make_user(
        db, profile="ap_accountant", email="prep@ledger.example", mara_number="25678009"
    )
    preparer = TestClient(client.app)
    login(preparer, preparer_user.email)
    trust = create(preparer, "account", {"entity_type": "Trust"}, name="Banksia Family Trust")
    eng = create(preparer, "engagement", {"client": trust["id"], "type": "Trust Tax Return", "fee": 1800})
    letter = create(preparer, "engagement_letter", {"engagement": eng["id"], "scope": "Trust return."})
    action(preparer, "engagement_letter", letter["id"], "send")
    sent = get(preparer, "engagement_letter", letter["id"])
    assert sent["fields"]["tax_agent_number"] == "25678009" and sent["fields"]["practitioner"] == str(
        preparer_user.id
    )
    # Lodging needs proof of identity and, for a business client, client-to-agent linking.
    import uuid

    from app.engine.records import RecordService
    from app.models import Record

    rec = db.get(Record, uuid.UUID(eng["id"]))
    assert rec is not None
    RecordService.as_system(db).update(
        "engagement", rec.id, {"stage": "Ready to Lodge", "letter_signed": True}, record=rec
    )
    db.commit()
    url = f"{API}/objects/engagement/records/{eng['id']}"
    r = preparer.patch(
        url, json={"version": get(c, "engagement", eng["id"])["version"], "fields": {"stage": "Lodged"}}
    )
    assert r.status_code == 422 and "identity" in r.text.lower()
    patch(c, "account", trust["id"], {"identity_verified": True})
    r = preparer.patch(
        url, json={"version": get(c, "engagement", eng["id"])["version"], "fields": {"stage": "Lodged"}}
    )
    assert r.status_code == 422 and "client-to-agent" in r.text
    patch(c, "account", trust["id"], {"agent_nominated": True})
    lodged = patch(
        preparer,
        "engagement",
        eng["id"],
        {"stage": "Lodged", "noa_amount": -1250.5, "noa_date": "2026-12-01"},
    )
    assert lodged["fields"]["stage"] == "Lodged" and float(lodged["fields"]["noa_amount"]) == -1250.5

    # SMSF audit independence: not the person who prepared the fund's return that year.
    fund = create(c, "account", {"entity_type": "SMSF", "identity_verified": True}, name="Wattle Super Fund")
    create(c, "engagement", {"client": fund["id"], "type": "SMSF Annual Return", "financial_year": "2025-26",
                             "responsible_accountant": str(preparer_user.id)})  # fmt: skip
    r = c.post(
        f"{API}/objects/engagement/records",
        json={"fields": {"client": fund["id"], "type": "SMSF Audit", "financial_year": "2025-26",
                         "responsible_accountant": str(preparer_user.id)}},
    )  # fmt: skip
    assert r.status_code == 422 and "independent" in r.text
    auditor = make_user(db, profile="ap_accountant", email="aud@ledger.example")
    create(c, "engagement", {"client": fund["id"], "type": "SMSF Audit", "financial_year": "2025-26",
                             "responsible_accountant": str(auditor.id)})  # fmt: skip

    # The practice setting switches BAS deadlines to the tax agent concession dates.
    set_setting(
        db,
        "accounting_practice",
        {**(get_setting(db, "accounting_practice") or {}), "bas_due_dates": "tax_agent"},
    )
    db.commit()
    shop = create(
        c, "account", {"entity_type": "Company", "bas_frequency": "Quarterly"}, name="Corner Shop Pty Ltd"
    )
    action(c, "account", shop["id"], "generate_bas_deadlines")
    dues = {
        d["fields"]["period"]: d["fields"]["due_date"]
        for d in related(c, "lodgement_deadline", "client", shop["id"])
    }
    assert all(v[5:] in ("11-25", "02-28", "05-26", "08-25") for v in dues.values())


def test_loan_broker_nccp_disclosures_serviceability_and_clawback(
    admin_client: TestClient, db: Session
) -> None:
    from decimal import Decimal

    from app.packs.loan_broker import monthly_repayment

    # $500,000 over 30 years at 9%: about $4,023 a month.
    assert monthly_repayment(Decimal(500000), Decimal(9), Decimal(30)) == Decimal("4023.11")
    c = admin_client
    install(c, "loan_broker")
    lender = create(
        c,
        "lender",
        {"upfront_rate": 0.6, "clawback_months": 24, "clawback_half_after": 12},
        name="Harbour Bank",
    )
    person = create(c, "contact", {"first_name": "Lin", "last_name": "Tan"})
    today = local_today().isoformat()
    loan = create(
        c,
        "loan_application",
        {"primary_borrower": person["id"], "purpose": "Purchase - Investment", "loan_amount": 900000, "security_value": 1000000,
         "interest_rate": 6.5, "term_years": 30, "broker_fee": 990, "credit_guide_date": today, "privacy_consent_date": today,
         "customer_objectives": "Investment", "products_considered": "Harbour", "recommendation_reason": "Best fit",
         "lender": lender["id"]},
    )  # fmt: skip
    assert loan["fields"]["lmi_likely"] is True  # 90% LVR
    # A fee charged to the client needs a credit quote before credit assistance.
    patch(c, "loan_application", loan["id"], {"stage": "Preliminary Assessment"}, expect=422)
    patch(c, "loan_application", loan["id"], {"credit_quote_date": today})
    # Repayments at 9.5% (~$7,568) exceed a $6,000 surplus: the loan looks unsuitable.
    ff = create(c, "fact_find", {"loan_application": loan["id"], "gross_annual_income": 96000, "monthly_living_expenses": 2000,
                                 "expenses_verified": True})  # fmt: skip
    patch(c, "fact_find", ff["id"], {"status": "Complete"})
    r = c.post(f"{API}/objects/loan_application/records/{loan['id']}/actions/record_assessment", json={})
    assert r.status_code == 422 and "unsuitable" in r.text
    patch(c, "fact_find", ff["id"], {"gross_annual_income": 220000})
    action(c, "loan_application", loan["id"], "record_assessment")
    # The credit proposal disclosure comes before applying to the lender.
    patch(c, "loan_application", loan["id"], {"stage": "Lodged"}, expect=422)
    patch(c, "loan_application", loan["id"], {"credit_proposal_date": today, "stage": "Lodged"})
    settled = patch(c, "loan_application", loan["id"], {"stage": "Settled", "settlement_date": "2026-01-15"})
    assert float(settled["fields"]["expected_upfront"]) == 5400
    # Refinanced away 14 months later: half the upfront commission is expected back.
    out = action(c, "loan_application", loan["id"], "record_discharge", {"discharged_date": "2027-03-20"})
    assert float(out["amount"]) == 2700
    claw = get(c, "commission", out["clawback"])
    assert claw["fields"]["type"] == "Clawback" and float(claw["fields"]["signed_amount"]) == -2700
    assert get(c, "loan_application", loan["id"])["fields"]["discharged_date"] == "2027-03-20"
    action(c, "loan_application", loan["id"], "record_discharge", expect=422)  # recorded once


def test_trust_records_hold_erasure(admin_client: TestClient, db: Session) -> None:
    """A law firm client with trust records from the last 7 years can't be erased (they must be kept)."""
    from sqlalchemy import update

    from app.models import Record

    c = admin_client
    install(c, "legal_practice")
    person = create(c, "contact", {"last_name": "Kept Client"})
    matter = create(c, "legal_matter", {"title": "Purchase", "client": person["id"], "estimated_costs": 500})
    receipt = create(
        c,
        "trust_transaction",
        {"legal_matter": matter["id"], "type": "Receipt", "amount": 2000, "method": "EFT",
         "payer_payee": "Kept Client", "description": "Deposit"},
    )  # fmt: skip
    url = f"{API}/privacy/contact/{person['id']}/erase"
    r = c.post(url, json={"reason": "Request SAR-9", "confirm": "ERASE"})
    assert r.status_code == 409 and "7 years" in r.text
    # Once the records are older than the retention period, the erasure goes ahead.
    db.execute(
        update(Record)
        .where(Record.id == receipt["id"])
        .values(created_at=local_today() - timedelta(days=round(365.25 * 7) + 2))
    )
    db.commit()
    r = c.post(url, json={"reason": "Request SAR-9", "confirm": "ERASE"})
    assert r.status_code == 200, r.text


def test_reminders_skip_finished_work(admin_client: TestClient, db: Session) -> None:
    """No reminders for a deadline lodged early, a closed matter's limitation date or a declined loan."""
    from datetime import UTC, datetime

    from app.packs.accounting_practice import daily_job as accounting_daily
    from app.packs.legal_practice import daily_reminders as legal_daily
    from app.packs.loan_broker import daily_reminders as lending_daily

    def titles() -> set[str]:
        return set(db.scalars(select(Notification.title)))

    c = admin_client
    in3 = (local_today() + timedelta(days=3)).isoformat()
    in30 = (local_today() + timedelta(days=30)).isoformat()

    install(c, "accounting_practice")
    entity = create(c, "account", {"name": "Early Lodger Pty Ltd"})
    deadline = {"client": entity["id"], "lodgement_type": "BAS", "due_date": in3}
    due = create(c, "lodgement_deadline", {**deadline, "period": "Q1"})
    lodged = create(c, "lodgement_deadline", {**deadline, "period": "Q2", "status": "Lodged"})
    accounting_daily(db)
    assert f"Lodgement due in 3 days: {due['name']}" in titles()
    assert f"Lodgement due in 3 days: {lodged['name']}" not in titles()

    install(c, "legal_practice")
    person = create(c, "contact", {"last_name": "Limitation Client"})
    claim = {"client": person["id"], "limitation_date": in30, "estimated_costs": 500}
    running = create(c, "legal_matter", {**claim, "title": "Claim A"})
    closed = create(c, "legal_matter", {**claim, "title": "Claim B"})
    patch(c, "legal_matter", closed["id"], {"stage": "Closed"})
    legal_daily(db)
    assert f"Limitation date in 30 days: {running['name']}" in titles()
    assert f"Limitation date in 30 days: {closed['name']}" not in titles()

    install(c, "loan_broker")
    borrower = create(c, "contact", {"last_name": "Rate Client"})
    in7 = (local_today() + timedelta(days=7)).isoformat()
    loan = {"primary_borrower": borrower["id"], "purpose": "Refinance", "loan_amount": 400000,
            "fixed_rate_expiry": in30, "settlement_date": in7}  # fmt: skip
    active = create(c, "loan_application", loan)
    declined = create(c, "loan_application", loan)
    patch(c, "loan_application", declined["id"], {"stage": "Declined", "decline_reason": "Client withdrew"})
    lending_daily(db)
    assert f"Fixed rate expires in 30 days: {active['name']}" in titles()
    assert f"Settlement in 7 days: {active['name']}" in titles()
    assert f"Fixed rate expires in 30 days: {declined['name']}" not in titles()
    assert f"Settlement in 7 days: {declined['name']}" not in titles()
    start = datetime.now(UTC) - timedelta(days=1)
    cal = c.get(
        f"{API}/calendar",
        params={"start": start.isoformat(), "end": (start + timedelta(days=40)).isoformat(), "mine": False},
    ).json()
    on_calendar = {k["id"] for k in cal["dates"]}
    assert active["id"] in on_calendar and declined["id"] not in on_calendar


def test_preliminary_assessment_must_be_current(admin_client: TestClient, db: Session) -> None:
    """NCCP s 115: lodging needs an assessment made within 90 days (120 for a residential purchase)."""
    import uuid as _uuid

    from app.models import Record

    c = admin_client
    install(c, "loan_broker")
    lender = create(c, "lender", {"upfront_rate": 0.6}, name="Coastal Bank")
    person = create(c, "contact", {"first_name": "Ari", "last_name": "Stale"})
    today = local_today().isoformat()

    def assessed_loan(purpose: str, days_ago: int) -> dict[str, Any]:
        loan = create(
            c,
            "loan_application",
            {"primary_borrower": person["id"], "purpose": purpose, "loan_amount": 300000, "security_value": 600000,
             "interest_rate": 6.0, "term_years": 30, "credit_guide_date": today, "privacy_consent_date": today,
             "customer_objectives": "Lower repayments", "products_considered": "Coastal", "recommendation_reason": "Rate",
             "lender": lender["id"]},
        )  # fmt: skip
        ff = create(c, "fact_find", {"loan_application": loan["id"], "gross_annual_income": 180000,
                                     "monthly_living_expenses": 3000, "expenses_verified": True})  # fmt: skip
        patch(c, "fact_find", ff["id"], {"status": "Complete"})
        action(c, "loan_application", loan["id"], "record_assessment")
        rec = db.get(Record, _uuid.UUID(loan["id"]))
        assert rec is not None
        made = (local_today() - timedelta(days=days_ago)).isoformat()
        rec.data = {**rec.data, "preliminary_assessment_date": made}
        db.commit()
        return loan

    refinance = assessed_loan("Refinance", 91)
    r = c.patch(
        f"{API}/objects/loan_application/records/{refinance['id']}",
        json={"version": get(c, "loan_application", refinance["id"])["version"],
              "fields": {"credit_proposal_date": today, "stage": "Lodged"}},
    )  # fmt: skip
    assert r.status_code == 422 and "more than 90 days ago" in r.text
    # The expired assessment is made again (the BID record can be brought up to date first), then it lodges.
    patch(c, "loan_application", refinance["id"], {"customer_objectives": "Lower repayments, offset account"})
    action(c, "loan_application", refinance["id"], "record_assessment")
    lodged = patch(c, "loan_application", refinance["id"], {"credit_proposal_date": today, "stage": "Lodged"})
    assert lodged["fields"]["stage"] == "Lodged" and lodged["fields"]["preliminary_assessment_date"] == today

    # A home purchase has 120 days; a current assessment can't be re-recorded or its BID record changed.
    purchase = assessed_loan("Purchase - Owner Occupied", 100)
    action(c, "loan_application", purchase["id"], "record_assessment", expect=422)
    patch(c, "loan_application", purchase["id"], {"customer_objectives": "Changed"}, expect=422)
    done = patch(c, "loan_application", purchase["id"], {"credit_proposal_date": today, "stage": "Lodged"})
    assert done["fields"]["stage"] == "Lodged"


def test_old_product_name_is_renamed(db: Session) -> None:
    """Settings still holding the product's earlier name get the current one; a firm's own name is kept."""
    from app.domains import PRODUCT_NAME, rename_product
    from app.services.settings import get_setting, set_setting

    set_setting(db, "branding", {**(get_setting(db, "branding") or {}), "name": "Meridian CRM"})
    set_setting(db, "marketing", {**(get_setting(db, "marketing") or {}), "from_name": "Harbour Legal"})
    assert rename_product(db) == 1
    assert get_setting(db, "branding")["name"] == PRODUCT_NAME == "Segue CRM"
    assert get_setting(db, "marketing")["from_name"] == "Harbour Legal"
    assert rename_product(db) == 0

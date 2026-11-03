"""Record engine: validation per field type, CRUD, concurrency, history, recycle bin, sharing, FLS,
queries, list views, search and the Object Manager."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.security.seed_v1 import stable_id
from tests.conftest import Outbox, client_as, login, make_user

API = "/api/v1"


def create(c: TestClient, obj: str, fields: dict[str, Any] | None = None, name: str | None = None, **kw: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"fields": fields or {}, **kw}
    if name is not None:
        body["name"] = name
    r = c.post(f"{API}/objects/{obj}/records", json=body)
    assert r.status_code == 201, r.text
    out: dict[str, Any] = r.json()
    return out


def as_user(client: TestClient, db: Session, profile: str, role: str | None = None, email: str | None = None) -> TestClient:
    user = make_user(db, profile=profile, role=role, email=email)
    c = TestClient(client.app)
    login(c, user.email)
    return c


# ------------------------------------------------------------------ metadata


def test_describe_filters_by_profile(admin_client: TestClient, settings: Settings, outbox: Outbox, db: Session, no_mfa: None) -> None:
    objs = {o["api_name"]: o for o in admin_client.get(f"{API}/meta/objects").json()}
    assert {"account", "contact", "lead", "opportunity", "case", "invoice", "campaign"} <= set(objs)
    contact = admin_client.get(f"{API}/meta/objects/contact").json()
    assert contact["fields"]["email"]["type"] == "email"
    assert contact["page_layout"][0]["label"] == "Contact Information"
    assert any(r["object"] == "opportunity" for r in contact["related_lists"])
    assert {a["key"] for a in admin_client.get(f"{API}/meta/apps").json()} >= {"sales", "service", "marketing", "billing", "analytics"}

    agent = client_as(settings, outbox, db, "service_agent")
    account = agent.get(f"{API}/meta/objects/account").json()
    assert "annual_revenue" not in account["fields"]  # hidden by default FLS
    assert agent.get(f"{API}/meta/objects/lead").status_code == 403
    assert "lead" not in {o["api_name"] for o in agent.get(f"{API}/meta/objects").json()}
    opp = agent.get(f"{API}/meta/objects/opportunity").json()
    assert opp["fields"]["amount"]["access"] == "read"
    portal = client_as(settings, outbox, db, "customer_portal")
    assert portal.get(f"{API}/meta/objects").status_code == 403  # portal users never reach staff APIs


# ------------------------------------------------------------------ CRUD and validation


def test_create_validates_each_field_type(admin_client: TestClient) -> None:
    c = admin_client
    account = create(c, "account", {"phone": "02 9999 1234", "website": "example.com", "industry": "Retail",
                                     "annual_revenue": "1250000.5", "billing_address": {"street": "1 George St", "city": "Sydney", "state": "NSW", "postcode": "2000", "country": "Australia"}},
                     name="Acme Pty Ltd")
    f = account["fields"]
    assert f["phone"] == "+61299991234"  # E.164
    assert f["website"] == "https://example.com"
    assert f["annual_revenue"] == 1250000.5
    assert f["billing_address"]["city"] == "Sydney"
    assert account["owner"]["name"] == "Ada Admin"

    contact = create(c, "contact", {"first_name": "Jo", "last_name": "Bloggs", "email": "JO@Example.com", "account": account["id"]})
    assert contact["name"] == "Jo Bloggs"
    assert contact["fields"]["email"] == "jo@example.com"
    assert contact["display"]["account"]["name"] == "Acme Pty Ltd"

    bad = c.post(f"{API}/objects/contact/records", json={"fields": {
        "last_name": "X", "email": "nope", "salutation": "Sir", "birthdate": "31-12-1990", "account": "not-a-uuid", "colour": 1}})
    assert bad.status_code == 422
    errors = bad.json()["error"]["fields"]
    assert set(errors) == {"email", "salutation", "birthdate", "account", "colour"}
    missing = c.post(f"{API}/objects/contact/records", json={"fields": {"first_name": "No"}})
    assert missing.json()["error"]["fields"] == {"last_name": "This field is required."}
    ghost = c.post(f"{API}/objects/contact/records", json={"fields": {"last_name": "G", "account": "00000000-0000-0000-0000-000000000000"}})
    assert ghost.json()["error"]["fields"] == {"account": "Choose a valid record."}
    wrong_type = c.post(f"{API}/objects/contact/records", json={"fields": {"last_name": "G", "account": contact["id"]}})
    assert wrong_type.status_code == 422
    readonly = c.post(f"{API}/objects/contact/records", json={"fields": {"last_name": "G", "email_bounced": True}})
    assert readonly.json()["error"]["fields"] == {"email_bounced": "This field is read-only."}
    assert c.post(f"{API}/objects/nope/records", json={"fields": {}}).status_code == 404


def test_update_concurrency_history_delete_restore(admin_client: TestClient) -> None:
    c = admin_client
    contact = create(c, "contact", {"last_name": "Smith", "email": "a@example.com"})
    url = f"{API}/objects/contact/records/{contact['id']}"
    r = c.patch(url, json={"version": 1, "fields": {"email": "b@example.com", "first_name": "Sam"}})
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 2 and r.json()["name"] == "Sam Smith"
    stale = c.patch(url, json={"version": 1, "fields": {"title": "CEO"}})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_version"
    history = c.get(f"{url}/history").json()
    assert {(h["field"], h["old_value"], h["new_value"]) for h in history} == {
        ("email", "a@example.com", "b@example.com"),
        ("name", "Smith", "Sam Smith"),
    }

    assert c.delete(url).status_code == 204
    assert c.patch(url, json={"version": 3, "fields": {"title": "x"}}).status_code == 404
    listing = c.get(f"{API}/objects/contact/records").json()
    assert listing["total"] == 0
    bin_items = c.get(f"{API}/recycle-bin").json()
    assert [i["id"] for i in bin_items] == [contact["id"]]
    assert c.post(f"{url}/restore").status_code == 200
    assert c.get(f"{API}/objects/contact/records").json()["total"] == 1


def test_master_detail_cascade_and_restrict(admin_client: TestClient) -> None:
    c = admin_client
    account = create(c, "account", name="Globex")
    opp = create(c, "opportunity", {"account": account["id"], "close_date": date.today().isoformat()}, name="Big deal")
    product = create(c, "product", {"product_code": "W-1", "standard_price": 100}, name="Widget")
    line = create(c, "opportunity_product", {"opportunity": opp["id"], "product": product["id"], "quantity": 3, "discount": 20})
    assert line["fields"]["unit_price"] == 100 and line["fields"]["line_total"] == 280
    assert c.get(f"{API}/objects/opportunity/records/{opp['id']}").json()["fields"]["amount"] == 280
    # Account is referenced by the opportunity with delete rule "restrict".
    blocked = c.delete(f"{API}/objects/account/records/{account['id']}")
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "delete_restricted"
    # Deleting the master soft-deletes its details; restoring brings them back.
    assert c.delete(f"{API}/objects/opportunity/records/{opp['id']}").status_code == 204
    assert c.get(f"{API}/objects/opportunity_product/records/{line['id']}").json()["is_deleted"] is True
    assert c.post(f"{API}/objects/opportunity/records/{opp['id']}/restore").status_code == 200
    related = c.get(f"{API}/objects/opportunity/records/{opp['id']}/related/opportunity_product/opportunity").json()
    assert [i["id"] for i in related["items"]] == [line["id"]]


# ------------------------------------------------------------------ sharing


def test_private_sharing_hierarchy_and_manual_shares(client: TestClient, db: Session, no_mfa: None) -> None:
    rep_a = as_user(client, db, "sales_representative", role="sales_representative", email="a@example.com")
    rep_b = as_user(client, db, "sales_representative", role="sales_representative", email="b@example.com")
    manager = as_user(client, db, "sales_manager", role="sales_manager", email="m@example.com")
    auditor = as_user(client, db, "read_only", email="ro@example.com")
    lead = create(rep_a, "lead", {"last_name": "Private", "company": "Initech"})
    url = f"{API}/objects/lead/records/{lead['id']}"

    assert rep_b.get(url).status_code == 404  # private: peers can't see
    assert rep_b.get(f"{API}/objects/lead/records").json()["total"] == 0
    assert manager.get(url).status_code == 200  # role hierarchy
    assert manager.get(url).json()["access"]["edit"] is True
    assert auditor.get(url).status_code == 200  # View All
    assert auditor.patch(url, json={"version": 1, "fields": {"title": "x"}}).status_code == 403

    # Manual share (read), then read/write.
    b_id = str(make_user(db, profile="sales_representative", email="b2@example.com").id)
    _ = b_id
    b_user = rep_b.get(f"{API}/auth/me").json()["user"]["id"]
    share = rep_a.post(f"{url}/shares", json={"principal_type": "user", "principal_id": b_user, "access": "read"})
    assert share.status_code == 201
    assert rep_b.get(url).status_code == 200
    assert rep_b.patch(url, json={"version": 1, "fields": {"title": "x"}}).status_code == 403
    rep_a.delete(f"{url}/shares/{share.json()['id']}")
    rep_a.post(f"{url}/shares", json={"principal_type": "role", "principal_id": str(stable_id("role", "sales_representative")), "access": "read_write"})
    assert rep_b.patch(url, json={"version": 1, "fields": {"title": "Boss"}}).status_code == 200
    # Only the owner (or an admin) manages sharing.
    assert rep_b.post(f"{url}/shares", json={"principal_type": "user", "principal_id": b_user}).status_code == 403
    # Accounts are Public Read Only: peers read, but can't edit.
    acct = create(rep_a, "account", name="Shared Co")
    acct_url = f"{API}/objects/account/records/{acct['id']}"
    assert rep_b.get(acct_url).status_code == 200
    assert rep_b.patch(acct_url, json={"version": 1, "fields": {"phone": "0299999999"}}).status_code == 403


def test_sharing_rules_and_queues(admin_client: TestClient, client: TestClient, db: Session) -> None:
    rep = as_user(client, db, "sales_representative", role="sales_representative", email="rep@example.com")
    agent = as_user(client, db, "service_agent", role="service_agent", email="agent@example.com")
    # Owner-based rule: cases owned by Sales Representatives are shared read-only with Service Agents.
    rule = admin_client.post(f"{API}/setup/sharing-rules", json={
        "object_api_name": "case", "name": "Sales cases to service", "rule_type": "owner",
        "source_type": "role", "source_id": str(stable_id("role", "sales_representative")),
        "target_type": "role", "target_id": str(stable_id("role", "service_agent")), "access": "read",
    })
    assert rule.status_code == 201, rule.text
    admin_rep = admin_client.get(f"{API}/admin/users", params={"q": "rep@example.com"}).json()["items"][0]["id"]
    case = create(admin_client, "case", {"subject": "Printer on fire"}, owner_id=admin_rep)
    assert agent.get(f"{API}/objects/case/records/{case['id']}").status_code == 200
    assert agent.get(f"{API}/objects/case/records/{case['id']}").json()["access"]["edit"] is False
    _ = rep
    # Queue-owned case: members see it, others don't.
    queue = admin_client.post(f"{API}/setup/queues", json={"name": "Support", "object_api_names": ["case"]}).json()
    agent_id = agent.get(f"{API}/auth/me").json()["user"]["id"]
    admin_client.put(f"{API}/setup/queues/{queue['id']}/members", json={"user_ids": [agent_id]})
    queued = create(admin_client, "case", {"subject": "Queued"}, queue_id=queue["id"])
    assert queued["owner"]["type"] == "queue"
    assert agent.get(f"{API}/objects/case/records/{queued['id']}").status_code == 200
    mine = agent.get(f"{API}/objects/case/records", params={"scope": "queue"}).json()
    assert [i["id"] for i in mine["items"]] == [queued["id"]]
    accepted = agent.post(f"{API}/objects/case/records/{queued['id']}/actions/accept")
    assert accepted.status_code == 200 and accepted.json()["owner"]["id"] == agent_id


def test_field_level_security_on_write_and_read(admin_client: TestClient, client: TestClient, db: Session) -> None:
    agent = as_user(client, db, "service_agent", role="service_agent")
    agent_id = agent.get(f"{API}/auth/me").json()["user"]["id"]
    acct = create(admin_client, "account", {"annual_revenue": 5000}, name="Hidden Rev", owner_id=agent_id)
    got = agent.get(f"{API}/objects/account/records/{acct['id']}").json()
    assert "annual_revenue" not in got["fields"]
    r = agent.patch(f"{API}/objects/account/records/{acct['id']}", json={"version": 1, "fields": {"annual_revenue": 1}})
    assert r.status_code == 422 and r.json()["error"]["fields"] == {"annual_revenue": "Unknown field."}
    flt = agent.post(f"{API}/objects/account/records/query", json={"filters": {"logic": "and", "conditions": [
        {"field": "annual_revenue", "op": "gt", "value": 1}]}})
    assert flt.status_code == 422  # hidden fields can't be used to probe values
    # Opportunity amount is read-only for service agents.
    opp = create(admin_client, "opportunity", {"account": acct["id"], "close_date": "2030-01-01", "amount": 10}, name="O", owner_id=agent_id)
    assert agent.get(f"{API}/objects/opportunity/records/{opp['id']}").json()["fields"]["amount"] == 10


# ------------------------------------------------------------------ queries and list views


def test_query_filters_sort_and_keyset_pagination(admin_client: TestClient) -> None:
    c = admin_client
    for i, (industry, revenue) in enumerate([("Retail", 10), ("Retail", 20), ("Finance", 30), ("Finance", None),
                                             ("Technology", 50), ("Retail", 60), ("Education", 70)]):
        fields: dict[str, Any] = {"industry": industry}
        if revenue is not None:
            fields["annual_revenue"] = revenue
        create(c, "account", fields, name=f"Company {chr(ord('G') - i)}")

    def q(body: dict[str, Any]) -> dict[str, Any]:
        r = c.post(f"{API}/objects/account/records/query", json=body)
        assert r.status_code == 200, r.text
        out: dict[str, Any] = r.json()
        return out

    retail = q({"filters": {"logic": "and", "conditions": [{"field": "industry", "op": "equals", "value": "Retail"}]}})
    assert retail["total"] == 3
    either = q({"filters": {"logic": "or", "conditions": [
        {"field": "industry", "op": "equals", "value": "Finance"},
        {"logic": "and", "conditions": [{"field": "annual_revenue", "op": "gte", "value": 60}]}]}})
    assert either["total"] == 4
    blank = q({"filters": {"logic": "and", "conditions": [{"field": "annual_revenue", "op": "is_null"}]}})
    assert [i["name"] for i in blank["items"]] == ["Company D"]
    contains = q({"filters": {"logic": "and", "conditions": [{"field": "name", "op": "contains", "value": "pany a"}]}})
    assert [i["name"] for i in contains["items"]] == ["Company A"]

    seen: list[str] = []
    cursor = None
    while True:
        page = q({"sort": [{"field": "annual_revenue", "direction": "desc"}], "limit": 3, "cursor": cursor})
        seen += [i["name"] for i in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == ["Company A", "Company B", "Company C", "Company E", "Company F", "Company G", "Company D"]

    for bad in (
        {"filters": {"logic": "and", "conditions": [{"field": "nope", "op": "equals", "value": 1}]}},
        {"filters": {"logic": "and", "conditions": [{"field": "annual_revenue", "op": "gt", "value": "lots"}]}},
        {"filters": {"logic": "xor", "conditions": []}},
        {"sort": [{"field": "billing_address"}]},
        {"cursor": "garbage"},
    ):
        r = c.post(f"{API}/objects/account/records/query", json=bad)
        assert r.status_code == 422, bad


def test_relative_dates_list_views_kanban_and_search(admin_client: TestClient) -> None:
    c = admin_client
    acct = create(c, "account", name="Kanban Co")
    create(c, "opportunity", {"account": acct["id"], "close_date": date.today().isoformat(), "amount": 100, "stage": "Proposal"}, name="Now")
    create(c, "opportunity", {"account": acct["id"], "close_date": "2001-01-01", "amount": 50}, name="Old")
    this_q = c.post(f"{API}/objects/opportunity/records/query", json={"filters": {"logic": "and", "conditions": [
        {"field": "close_date", "op": "equals", "value": "THIS_QUARTER"}]}}).json()
    assert [i["name"] for i in this_q["items"]] == ["Now"]
    assert this_q["items"][0]["fields"]["probability"] == 60  # stage mapping

    views = c.get(f"{API}/objects/opportunity/list-views").json()["views"]
    open_view = next(v for v in views if v["key"] == "opportunity_open")
    res = c.get(f"{API}/objects/opportunity/records", params={"view_id": open_view["id"]}).json()
    assert res["total"] == 2
    board = c.get(f"{API}/objects/opportunity/kanban", params={"field": "stage", "view_id": open_view["id"]}).json()
    by_stage = {col["value"]: col for col in board["columns"]}
    assert by_stage["Proposal"]["total"] == 1 and by_stage["Proposal"]["amount"] == 100
    assert by_stage["Prospecting"]["total"] == 1

    mine = c.post(f"{API}/objects/opportunity/list-views", json={
        "name": "Big ones", "columns": ["name", "amount"], "filters": {"logic": "and", "conditions": [
            {"field": "amount", "op": "gte", "value": 75}]}, "sort": [{"field": "amount", "direction": "desc"}]})
    assert mine.status_code == 201, mine.text
    res = c.get(f"{API}/objects/opportunity/records", params={"view_id": mine.json()["id"]}).json()
    assert [i["name"] for i in res["items"]] == ["Now"]
    assert set(res["items"][0]["fields"]) == {"amount"}
    assert c.post(f"{API}/objects/opportunity/list-views/{mine.json()['id']}/pin").status_code == 200
    assert c.get(f"{API}/objects/opportunity/list-views").json()["default_view_id"] == mine.json()["id"]

    create(c, "contact", {"first_name": "Zelda", "last_name": "Searchable", "email": "zelda@hyrule.example"})
    found = c.get(f"{API}/search", params={"q": "hyrule"}).json()
    assert [g["object"] for g in found["groups"]] == ["contact"]
    assert c.get(f"{API}/search", params={"q": "Kanb"}).json()["groups"][0]["object"] == "account"


def test_private_list_views_are_private(admin_client: TestClient, client: TestClient, db: Session) -> None:
    rep = as_user(client, db, "sales_representative")
    v = rep.post(f"{API}/objects/account/list-views", json={"name": "Mine only"}).json()
    other = as_user(client, db, "sales_representative")
    assert other.get(f"{API}/objects/account/list-views/{v['id']}").status_code == 404
    shared = rep.post(f"{API}/objects/account/list-views", json={"name": "Everyone", "visibility": "public"})
    assert shared.status_code == 403  # needs Manage Public Reports & Dashboards


# ------------------------------------------------------------------ Object Manager


def test_custom_objects_and_fields_are_secure_by_default(admin_client: TestClient, client: TestClient, db: Session) -> None:
    c = admin_client
    obj = c.post(f"{API}/setup/objects", json={"label": "Project", "plural_label": "Projects", "name_field_type": "auto_number", "name_format": "PRJ-{0000}"})
    assert obj.status_code == 201, obj.text
    assert obj.json()["api_name"] == "project__c"
    f = c.post(f"{API}/setup/objects/project__c/fields", json={"label": "Budget", "type": "currency", "indexed": True})
    assert f.status_code == 201, f.text
    pick = c.post(f"{API}/setup/objects/project__c/fields", json={"label": "Phase", "type": "picklist", "options": {"values": ["Plan", "Build", "Done"], "is_path": True}})
    assert pick.status_code == 201
    lookup = c.post(f"{API}/setup/objects/project__c/fields", json={"label": "Client", "type": "lookup", "options": {"target": "account"}})
    assert lookup.status_code == 201
    p = create(c, "project__c", {"budget__c": "1234.567", "phase__c": "Plan"})
    assert p["name"] == "PRJ-0001" and p["fields"]["budget__c"] == 1234.57
    assert create(c, "project__c")["name"] == "PRJ-0002"
    # Other profiles: no object access until granted; custom fields hidden until granted.
    rep = as_user(client, db, "sales_representative")
    assert rep.get(f"{API}/objects/project__c/records").status_code == 403
    rep_profile = str(stable_id("profile", "sales_representative"))
    assert c.put(f"{API}/setup/sharing-defaults/project__c", json={"access": "read"}).status_code == 200
    r = c.put(f"{API}/setup/profiles/{rep_profile}/object-permissions", json={"objects": {"project__c": {"read": True, "create": True, "edit": True}}})
    assert r.status_code == 200, r.text
    got = rep.get(f"{API}/objects/project__c/records/{p['id']}")
    assert got.status_code == 200 and "budget__c" not in got.json()["fields"]
    c.put(f"{API}/setup/profiles/{rep_profile}/field-permissions", json={"fields": [{"object_api_name": "project__c", "field_api_name": "budget__c", "access": "read"}]})
    assert rep.get(f"{API}/objects/project__c/records/{p['id']}").json()["fields"]["budget__c"] == 1234.57
    # Field changes: compatible types only; delete -> restorable.
    assert c.patch(f"{API}/setup/objects/project__c/fields/budget__c", json={"type": "text"}).status_code == 422
    assert c.patch(f"{API}/setup/objects/project__c/fields/budget__c", json={"type": "number"}).status_code == 200
    assert c.patch(f"{API}/setup/objects/account/fields/industry", json={"type": "text"}).status_code == 422
    deleted = c.delete(f"{API}/setup/objects/project__c/fields/phase__c").json()
    assert "phase__c" not in {fd["api_name"] for fd in deleted["fields"]}
    assert [d["api_name"] for d in deleted["deleted_fields"]] == ["phase__c"]
    assert c.post(f"{API}/setup/objects/project__c/fields/phase__c/restore").status_code == 200
    # Standard objects can't be deleted; custom objects with records can't either.
    assert c.delete(f"{API}/setup/objects/account").status_code == 422
    assert c.delete(f"{API}/setup/objects/project__c").status_code == 409
    # Only Customize Application may change metadata.
    assert rep.post(f"{API}/setup/objects", json={"label": "Nope"}).status_code == 403
    # Every metadata change is audited.
    log = c.get(f"{API}/admin/audit-logs", params={"entity_type": "field_definition"}).json()
    assert log["total"] >= 5


@pytest.mark.parametrize("bad", [
    {"label": "", "type": "text"},
    {"label": "X", "type": "rocket"},
    {"label": "Id", "type": "text", "api_name": "id"},
    {"label": "P", "type": "picklist", "options": {"values": ["a", "A"]}},
    {"label": "L", "type": "lookup", "options": {"target": "nothing"}},
    {"label": "T", "type": "text", "options": {"max_length": 9999}},
])
def test_field_definition_validation(admin_client: TestClient, bad: dict[str, Any]) -> None:
    assert admin_client.post(f"{API}/setup/objects/account/fields", json=bad).status_code == 422

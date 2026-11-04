"""Query budgets: SQL round trips per request once caches are warm (plan v4, section 2).

Each round trip costs a full network hop to the database, so these numbers are what keep pages fast.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from tests.test_records_engine import as_user, create

API = "/api/v1"


@contextmanager
def count_queries() -> Iterator[list[int]]:
    counter = [0]

    def _count(*_: Any, **__: Any) -> None:
        counter[0] += 1

    event.listen(Engine, "before_cursor_execute", _count)
    try:
        yield counter
    finally:
        event.remove(Engine, "before_cursor_execute", _count)


def budget(c: TestClient, method: str, path: str, limit: int, body: Any = None) -> None:
    c.request(method, path, json=body)  # warm caches
    with count_queries() as n:
        r = c.request(method, path, json=body)
    assert r.status_code == 200, r.text
    assert n[0] <= limit, f"{method} {path}: {n[0]} queries (budget {limit})"


def test_query_budgets(admin_client: TestClient, db: Session, no_mfa: None) -> None:
    account = create(admin_client, "account", name="Budget Pty Ltd")
    for i in range(3):
        create(admin_client, "contact", {"last_name": f"Person {i}", "account": account["id"]})
    rep = as_user(admin_client, db, "sales_representative")
    create(rep, "account", name="Rep Account")

    for c in (admin_client, rep):
        budget(c, "GET", f"{API}/auth/me", 2)
        budget(c, "GET", f"{API}/meta/objects", 2)
        budget(c, "GET", f"{API}/meta/objects/account", 3)
        budget(c, "GET", f"{API}/meta/apps", 3)
        budget(c, "POST", f"{API}/objects/account/records/query", 4, {})
        budget(c, "GET", f"{API}/search?q=a&limit=5", 4)
        budget(c, "GET", f"{API}/reports", 4)
    rid = account["id"]
    budget(admin_client, "GET", f"{API}/objects/account/records/{rid}", 5)
    budget(admin_client, "GET", f"{API}/objects/account/records/{rid}/activities", 4)
    budget(admin_client, "GET", f"{API}/objects/account/records/{rid}/history", 4)
    budget(admin_client, "GET", f"{API}/objects/account/records/{rid}/related/contact/account", 5)


def test_date_field_indexes_build_and_are_used(admin_client: TestClient, db: Session, no_mfa: None) -> None:
    import re

    from sqlalchemy import false, select, text

    from app.engine.filters import field_expr
    from app.engine.indexes import index_name, sync_indexes
    from app.engine.meta import load_registry
    from app.models import Record

    registry = load_registry(db)
    sync_indexes(db.connection(), registry)  # used to fail: "functions in index expression must be IMMUTABLE"
    db.commit()
    name = index_name("opportunity", "close_date", False)
    assert db.execute(text("SELECT 1 FROM pg_indexes WHERE indexname = :n"), {"n": name}).scalar() == 1

    # The query engine's expression is the indexed one, so the planner can use the index.
    close = registry.get("opportunity").field("close_date")
    stmt = (
        select(Record.id)
        .where(Record.object_api_name == "opportunity", Record.is_deleted == false())
        .where(field_expr(close, Record) >= "2026-01-01")
    )
    db.execute(text("SET LOCAL enable_seqscan = off"))
    compiled = stmt.compile(db.get_bind(), compile_kwargs={"literal_binds": True})
    plan = ""
    for _ in range(6):
        plan = "\n".join(row[0] for row in db.execute(text(f"EXPLAIN {compiled}")))
        used = re.findall(r"[Ii]ndex (?:Only )?Scan (?:using|on) (\w+)", plan)
        other = [i for i in used if i != name]
        if name in used or not other:
            break
        # On a near-empty table another index can be cheaper; hide it (rolled back) to prove ours is usable.
        db.execute(text(f"DROP INDEX {other[0]}"))
    assert name in plan, plan
    db.rollback()

    # Filtering on a date still behaves the same.
    account = create(admin_client, "account", name="Dated Pty Ltd")
    create(
        admin_client,
        "opportunity",
        {"account": account["id"], "stage": "Prospecting", "close_date": "2026-12-24", "amount": 10},
        name="Christmas deal",
    )
    body = {"filters": {"field": "close_date", "op": "between", "value": ["2026-12-01", "2026-12-31"]}}
    r = admin_client.post(f"{API}/objects/opportunity/records/query", json=body)
    assert r.status_code == 200, r.text
    assert [i["name"] for i in r.json()["items"]] == ["Christmas deal"]

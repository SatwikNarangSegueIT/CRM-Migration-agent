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

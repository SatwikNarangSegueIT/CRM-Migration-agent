"""Privacy (plan v3 section 14): subject-access export, erasure (anonymise) and per-object retention."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AuditLog, FieldHistory, Record, User
from tests.conftest import Outbox, client_as
from tests.test_records_engine import create

API = "/api/v1"


def test_subject_access_export_and_erasure(admin_client: TestClient, db: Session, outbox: Outbox) -> None:
    c = admin_client
    acct = create(c, "account", name="Privacy Co")
    person = create(
        c,
        "contact",
        {
            "first_name": "Pia",
            "last_name": "Private",
            "email": "pia@private.example",
            "phone": "0400000000",
            "birthdate": "1990-01-01",
            "account": acct["id"],
            "email_opt_in": True,
        },
    )
    url = f"{API}/objects/contact/records/{person['id']}"
    c.patch(url, json={"version": person["version"], "fields": {"email": "pia2@private.example"}})
    case = create(c, "case", {"subject": "Help", "contact": person["id"]})
    create(c, "note", {"related_to": person["id"], "body": "Met Pia at the expo"}, name="Meeting note")
    create(
        c,
        "consent",
        {"contact": person["id"], "channel": "Email", "status": "Opted In", "ip_address": "203.0.113.9"},
    )
    assert c.post(f"{API}/portal-users/invite/{person['id']}").status_code == 201

    export = c.get(f"{API}/privacy/contact/{person['id']}/export")
    assert export.status_code == 200, export.text
    body = export.json()
    assert body["subject"]["fields"]["email"] == "pia2@private.example"
    assert {"case", "note", "consent"} <= set(body["related"])
    assert any(h["field"] == "email" for h in body["field_history"])

    assert (
        c.post(
            f"{API}/privacy/contact/{person['id']}/erase", json={"reason": "SAR-1", "confirm": "nope"}
        ).status_code
        == 422
    )
    erased = c.post(
        f"{API}/privacy/contact/{person['id']}/erase", json={"reason": "Request SAR-1", "confirm": "ERASE"}
    )
    assert erased.status_code == 200, erased.text
    e = erased.json()
    assert e["name"] == "Erased Contact"
    assert "email" not in e["fields"] or e["fields"]["email"] is None
    assert e["fields"].get("phone") is None and e["fields"].get("birthdate") is None
    assert e["fields"]["account"] == acct["id"]  # relationships kept
    db.expire_all()
    assert db.scalar(select(FieldHistory).where(FieldHistory.record_id == uuid.UUID(person["id"]))) is None
    assert c.get(f"{API}/objects/case/records/{case['id']}").status_code == 200  # business records kept
    notes = c.get(f"{API}/objects/contact/records/{person['id']}/related/note/related_to").json()
    assert notes["total"] == 0
    consent = c.get(f"{API}/objects/consent/records").json()["items"][0]
    assert consent["fields"].get("ip_address") is None and consent["fields"]["status"] == "Opted In"
    portal_user = db.scalar(select(User).where(User.contact_id == uuid.UUID(person["id"])))
    assert portal_user is not None and not portal_user.is_active and "pia" not in portal_user.email
    assert c.get(f"{API}/search", params={"q": "pia"}).json()["groups"] == []
    log = db.scalars(select(AuditLog).where(AuditLog.summary.like("Personal data erased%"))).one()
    assert "SAR-1" in log.summary and "pia" not in log.summary.lower()


def test_privacy_needs_manage_users(
    settings: Settings, outbox: Outbox, db: Session, admin_client: TestClient, no_mfa: None
) -> None:
    person = create(admin_client, "contact", {"last_name": "Guarded"})
    rep = client_as(settings, outbox, db, "sales_manager")
    assert rep.get(f"{API}/privacy/contact/{person['id']}/export").status_code == 403
    assert admin_client.get(f"{API}/privacy/account/{person['id']}/export").status_code == 422


def test_retention_policy_moves_old_records_to_recycle_bin(admin_client: TestClient, db: Session) -> None:
    from app.services.privacy import apply_retention

    old = create(admin_client, "lead", {"last_name": "Old", "company": "Old Co"})
    new = create(admin_client, "lead", {"last_name": "New", "company": "New Co"})
    db.execute(
        update(Record)
        .where(Record.id == uuid.UUID(old["id"]))
        .values(updated_at=datetime.now(UTC) - timedelta(days=800))
    )
    db.commit()
    assert (
        admin_client.put(
            f"{API}/setup/settings/retention", json={"value": {"object_years": {"lead": 2}}}
        ).status_code
        == 200
    )
    assert apply_retention(db) == 1
    db.expire_all()
    assert db.get(Record, uuid.UUID(old["id"])).is_deleted  # type: ignore[union-attr]
    assert not db.get(Record, uuid.UUID(new["id"])).is_deleted  # type: ignore[union-attr]

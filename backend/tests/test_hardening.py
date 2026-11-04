"""Phase 11: file purging, upload safety, sample and load data."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Record, StoredFile
from tests.test_records_engine import create

API = "/api/v1"


def test_purging_a_file_removes_its_stored_content(admin_client: TestClient, db: Session) -> None:
    acct = create(admin_client, "account", name="Files Co")
    r = admin_client.post(
        f"{API}/files",
        params={"related_to": acct["id"]},
        content=b"%PDF-1.4 test",
        headers={"X-File-Name": "brief.pdf", "Content-Type": "application/pdf"},
    )
    assert r.status_code == 201, r.text
    stored = db.scalars(select(StoredFile)).one()
    assert stored.storage == "db" and stored.content == b"%PDF-1.4 test"
    assert admin_client.get(f"{API}/files/{r.json()['id']}/content").content == b"%PDF-1.4 test"
    from app.engine.records import RecordService

    rec = db.get(Record, uuid.UUID(r.json()["id"]))
    assert rec is not None
    RecordService.as_system(db).hard_delete(rec)
    db.commit()
    assert db.scalars(select(StoredFile)).first() is None


def test_sample_data_runs_through_business_rules(db: Session, settings: Settings) -> None:
    from app import cli

    assert cli.main(["seed-demo"]) == 0
    counts = {
        o: db.scalar(select(Record.id).where(Record.object_api_name == o).limit(1))
        for o in ("account", "opportunity", "case", "invoice")
    }
    assert all(counts.values())
    invoice = db.scalars(select(Record).where(Record.object_api_name == "invoice")).one()
    assert invoice.data["status"] == "Partially Paid" and invoice.data["invoice_number"].startswith("INV-")
    case = db.scalars(select(Record).where(Record.object_api_name == "case")).first()
    assert case is not None and case.data.get("resolution_due")
    assert cli.main(["seed-load", "--count", "250"]) == 0
    assert db.scalar(select(Record.id).where(Record.name == "Load account 0000249")) is not None


def test_upload_safety_checks(admin_client: TestClient) -> None:
    def upload(name: str, content: bytes) -> int:
        r = admin_client.post(
            f"{API}/files",
            content=content,
            headers={"X-File-Name": name, "Content-Type": "application/octet-stream"},
        )
        return int(r.status_code)

    assert upload("setup.exe", b"MZ...") == 415
    assert (
        upload("eicar.txt", rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*") == 422
    )
    assert upload("empty.txt", b"") == 422
    assert upload("notes.txt", b"hello") == 201

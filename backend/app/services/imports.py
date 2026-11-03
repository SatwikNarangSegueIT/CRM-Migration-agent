"""CSV import (plan v3, section 7): column mapping, duplicate rule, dry run, background job, error file.

Imports run as the user who started them, through the record engine, so validation, field-level
security, sharing and object hooks apply exactly as for manual entry.
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.engine.meta import FieldMeta, ObjectMeta
from app.engine.records import RecordService
from app.models import ImportJob, Record, User
from app.security.catalog import FieldAccess
from app.security.policy import load_policy

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 50_000
INLINE_ROWS = 500
PREVIEW_ROWS = 20


class ImportValidationError(AppError):
    status_code = 422
    code = "invalid_import"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def parse_csv(text: str) -> tuple[list[str], list[dict[str, str]]]:
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ImportValidationError("CSV files can be at most 10 MB.")
    text = text.lstrip("﻿")
    try:
        sample = text[:4096]
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t") if sample.strip() else csv.excel
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = [h.strip() for h in (reader.fieldnames or []) if h is not None]
    if not headers:
        raise ImportValidationError("The file has no header row.")
    rows: list[dict[str, str]] = []
    for i, row in enumerate(reader):
        if i >= MAX_ROWS:
            raise ImportValidationError(f"Import at most {MAX_ROWS} rows at a time.")
        rows.append({(k or "").strip(): (v or "").strip() for k, v in row.items() if k is not None})
    return headers, rows


def importable_fields(svc: RecordService, meta: ObjectMeta) -> list[FieldMeta]:
    out = []
    for f in meta.fields.values():
        if f.api_name == "name" and meta.name_field_type == "text":
            out.append(f)
            continue
        if f.is_system or f.is_readonly or f.type in ("auto_number", "address"):
            continue
        if svc.field_access(meta, f) is FieldAccess.EDIT:
            out.append(f)
    return out


def suggest_mapping(svc: RecordService, meta: ObjectMeta, headers: list[str]) -> dict[str, str]:
    by_key: dict[str, str] = {}
    for f in importable_fields(svc, meta):
        by_key.setdefault(_norm(f.label), f.api_name)
        by_key.setdefault(_norm(f.api_name), f.api_name)
    if meta.name_field_type == "text":
        by_key.setdefault(_norm(meta.name_label), "name")
    return {h: by_key[_norm(h)] for h in headers if _norm(h) in by_key}


def _lookup_value(svc: RecordService, f: FieldMeta, raw: str) -> str:
    try:
        return str(uuid.UUID(raw))
    except ValueError:
        pass
    for target in f.targets:
        res = svc.query(
            target,
            filters={"logic": "and", "conditions": [{"field": "name", "op": "equals", "value": raw}]},
            limit=2,
            count=False,
        )
        if len(res.records) == 1:
            return str(res.records[0].id)
        if len(res.records) > 1:
            raise ImportValidationError(f"{f.label}: more than one record is named {raw!r}.")
    raise ImportValidationError(f"{f.label}: no record named {raw!r}.")


def _picklist_value(f: FieldMeta, raw: str) -> str:
    for v in f.picklist_values:
        if (
            raw == v["value"]
            or raw.lower() == str(v.get("label", "")).lower()
            or raw.lower() == v["value"].lower()
        ):
            return str(v["value"])
    return raw


def row_values(
    svc: RecordService, meta: ObjectMeta, mapping: dict[str, str], row: dict[str, str]
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for column, api in mapping.items():
        if not api:
            continue
        raw = row.get(column, "")
        if raw == "":
            continue
        f = meta.fields[api]
        if f.is_lookup:
            values[api] = _lookup_value(svc, f, raw)
        elif f.type == "picklist":
            values[api] = _picklist_value(f, raw)
        elif f.type == "multi_picklist":
            values[api] = [_picklist_value(f, part.strip()) for part in raw.split(";") if part.strip()]
        else:
            values[api] = raw
    return values


def _find_match(svc: RecordService, meta: ObjectMeta, match_field: str, value: Any) -> Record | None:
    if value in (None, ""):
        return None
    res = svc.query(
        meta.api_name,
        filters={"logic": "and", "conditions": [{"field": match_field, "op": "equals", "value": value}]},
        limit=1,
        count=False,
    )
    return res.records[0] if res.records else None


def validate_job(
    svc: RecordService, meta: ObjectMeta, mapping: dict[str, str], match_field: str | None
) -> None:
    allowed = {f.api_name for f in importable_fields(svc, meta)}
    for column, api in mapping.items():
        if api and api not in allowed:
            raise ImportValidationError(
                f"Column {column!r} can't be imported into {api!r}.", fields={"mapping": column}
            )
    if match_field:
        f = meta.fields.get(match_field)
        if f is None or not (f.api_name == "name" or f.type in ("email", "text", "phone") or f.external_id):
            raise ImportValidationError(
                "Match on name, e-mail, phone or an external ID field.", fields={"match_field": "Invalid"}
            )
        if match_field not in mapping.values():
            raise ImportValidationError(
                "Map a column to the field used to find duplicates.", fields={"match_field": "Not mapped"}
            )


def execute(svc: RecordService, job: ImportJob, *, dry_run: bool) -> dict[str, Any]:
    meta = svc.object(job.object_api_name, need="create")
    _, rows = parse_csv(job.csv_text)
    counts = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}
    errors: list[dict[str, Any]] = []
    preview: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):  # row 1 is the header
        outcome = "created"
        try:
            with svc.db.begin_nested() as nested:
                values = row_values(svc, meta, job.mapping, row)
                existing = (
                    _find_match(svc, meta, job.match_field, values.get(job.match_field))
                    if job.match_field
                    else None
                )
                if existing is not None and job.duplicate_action == "skip":
                    outcome = "skipped"
                elif existing is not None and job.duplicate_action == "update":
                    svc.update(
                        meta.api_name,
                        existing.id,
                        values,
                        record=svc.get(meta.api_name, existing.id, lock=True),
                    )
                    outcome = "updated"
                else:
                    svc.create(meta.api_name, values)
                if dry_run:
                    nested.rollback()
            counts[outcome] += 1
            if dry_run and len(preview) < PREVIEW_ROWS:
                preview.append({"row": index, "outcome": outcome, "values": row})
        except AppError as exc:
            counts["errors"] += 1
            detail = "; ".join(f"{k}: {v}" for k, v in exc.fields.items()) if exc.fields else ""
            message = f"{exc.message} {detail}".strip()
            if len(errors) < 5000:
                errors.append({"row": index, "message": message})
            if dry_run and len(preview) < PREVIEW_ROWS:
                preview.append({"row": index, "outcome": "error", "message": message, "values": row})
    return {"total_rows": len(rows), **counts, "error_rows": errors, "preview": preview}


def create_job(
    svc: RecordService,
    object_api: str,
    file_name: str,
    csv_text: str,
    mapping: dict[str, str],
    match_field: str | None,
    duplicate_action: str,
) -> ImportJob:
    meta = svc.object(object_api, need="create")
    headers, rows = parse_csv(csv_text)
    unknown = [c for c in mapping if c not in headers]
    if unknown:
        raise ImportValidationError(
            f"Column {unknown[0]!r} isn't in the file.", fields={"mapping": unknown[0]}
        )
    validate_job(svc, meta, mapping, match_field)
    if duplicate_action not in ("skip", "update", "create"):
        raise ImportValidationError(
            "Choose skip, update or create for duplicates.", fields={"duplicate_action": "Invalid"}
        )
    job = ImportJob(
        object_api_name=object_api,
        created_by_id=svc.user_id,
        status="pending",
        file_name=file_name[:255],
        csv_text=csv_text,
        mapping=mapping,
        match_field=match_field,
        duplicate_action=duplicate_action,
        total_rows=len(rows),
    )
    svc.db.add(job)
    svc.db.flush()
    return job


def run_import(db: Session, job_id: uuid.UUID) -> None:
    """Worker entry point (also used inline for small files)."""
    import app.apps  # noqa: F401 - hooks

    job = db.scalar(select(ImportJob).where(ImportJob.id == job_id).with_for_update())
    if job is None or job.status not in ("pending",):
        return
    job.status = "running"
    db.commit()
    user = db.get(User, job.created_by_id)
    if user is None or not user.is_active:
        job.status = "failed"
        job.errors = [{"row": 0, "message": "The user who started the import is no longer active."}]
        db.commit()
        return
    svc = RecordService.for_user(db, user, load_policy(db, user))
    try:
        result = execute(svc, job, dry_run=False)
    except AppError as exc:
        db.rollback()
        job = db.get(ImportJob, job_id)
        assert job is not None
        job.status = "failed"
        job.errors = [{"row": 0, "message": exc.message}]
        job.finished_at = datetime.now(UTC)
        db.commit()
        return
    job.status = "completed"
    job.created_count, job.updated_count = result["created"], result["updated"]
    job.skipped_count, job.error_count = result["skipped"], result["errors"]
    job.errors = result["error_rows"]
    job.finished_at = datetime.now(UTC)
    job.csv_text = ""  # don't keep personal data longer than needed
    db.commit()


def errors_csv(job: ImportJob) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Row", "Error"])
    for e in job.errors or []:
        w.writerow([e.get("row"), e.get("message")])
    return buf.getvalue()


def export_csv(
    svc: RecordService,
    object_api: str,
    *,
    columns: list[str],
    filters: dict[str, Any] | None,
    scope: str,
    sort: list[dict[str, str]] | None,
    max_rows: int = 50_000,
) -> tuple[str, int]:
    from app.engine.types import display_text
    from app.services.reports import _csv_safe

    meta = svc.object(object_api)
    readable = {f.api_name: f for f in svc.readable_fields(meta)}
    cols = (
        [c for c in columns if c in readable] or [c for c in meta.list_columns if c in readable] or ["name"]
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Id", *[readable[c].label for c in cols]])
    cursor = None
    count = 0
    while count < max_rows:
        res = svc.query(
            object_api, filters=filters, scope=scope, sort=sort, cursor=cursor, limit=200, count=False
        )
        items = svc.serialize_many(object_api, res.records, columns=cols, with_access=False)
        for item in items:
            row = [item["id"]]
            for c in cols:
                f = readable[c]
                if c == "name":
                    row.append(_csv_safe(item["name"]))
                elif c == "owner_id":
                    row.append(_csv_safe((item["owner"] or {}).get("name", "")))
                elif c in ("created_at", "updated_at"):
                    row.append(str(item[c]))
                elif c in ("created_by_id", "updated_by_id"):
                    row.append(_csv_safe((item[c.replace("_id", "")] or {}).get("name", "")))
                elif f.is_lookup:
                    row.append(_csv_safe((item["display"].get(c) or {}).get("name", "")))
                else:
                    row.append(
                        _csv_safe(
                            display_text(f, item["fields"].get(c))
                            if f.type != "encrypted_text"
                            else item["fields"].get(c) or ""
                        )
                    )
            w.writerow(row)
            count += 1
        cursor = res.next_cursor
        if cursor is None:
            break
    return buf.getvalue(), count


def recent_jobs(db: Session, user_id: uuid.UUID, all_users: bool) -> list[ImportJob]:
    stmt = select(ImportJob).order_by(ImportJob.created_at.desc()).limit(50)
    if not all_users:
        stmt = stmt.where(ImportJob.created_by_id == user_id)
    return list(db.scalars(stmt))


__all__ = ["func"]

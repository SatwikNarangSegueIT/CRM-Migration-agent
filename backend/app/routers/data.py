"""Imports, exports and document PDFs (plan v3, sections 7 and 8)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from app.core.errors import NotFoundError, PermissionDeniedError
from app.engine.deps import Records
from app.engine.describe import visible_list_views
from app.models import ImportJob
from app.security.catalog import SystemPermission
from app.services import audit, imports
from app.services.audit import AuditAction
from app.services.pdf import render_document

router = APIRouter(tags=["data"])


class AnalyzeIn(BaseModel):
    object_api_name: str = Field(max_length=80)
    csv: str


class ImportIn(BaseModel):
    object_api_name: str = Field(max_length=80)
    file_name: str = Field(default="import.csv", max_length=255)
    csv: str
    mapping: dict[str, str]
    match_field: str | None = Field(default=None, max_length=80)
    duplicate_action: Literal["skip", "update", "create"] = "skip"
    dry_run: bool = False


class ExportIn(BaseModel):
    object_api_name: str = Field(max_length=80)
    view_id: uuid.UUID | None = None
    columns: list[str] = Field(default_factory=list, max_length=60)
    filters: dict[str, Any] | None = None
    scope: Literal["all", "mine", "team", "queue"] = "all"


def _require(svc: Any, perm: SystemPermission, label: str) -> None:
    if not svc.policy.has(perm):
        raise PermissionDeniedError(f"This needs the {label} permission.")


def _job_out(job: ImportJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "object_api_name": job.object_api_name,
        "status": job.status,
        "file_name": job.file_name,
        "total_rows": job.total_rows,
        "created": job.created_count,
        "updated": job.updated_count,
        "skipped": job.skipped_count,
        "errors": job.error_count,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "duplicate_action": job.duplicate_action,
        "match_field": job.match_field,
    }


@router.post("/imports/analyze")
def analyze(body: AnalyzeIn, svc: Records) -> dict[str, Any]:
    _require(svc, SystemPermission.IMPORT_DATA, "Import Data")
    meta = svc.object(body.object_api_name, need="create")
    headers, rows = imports.parse_csv(body.csv)
    fields = imports.importable_fields(svc, meta)
    return {
        "headers": headers,
        "row_count": len(rows),
        "sample": rows[:5],
        "suggested_mapping": imports.suggest_mapping(svc, meta, headers),
        "fields": [
            {"api_name": f.api_name, "label": f.label, "type": f.type, "required": f.required} for f in fields
        ],
        "match_fields": [
            f.api_name
            for f in fields
            if f.api_name == "name" or f.type in ("email", "phone") or f.external_id
        ],
    }


@router.post("/imports", status_code=status.HTTP_201_CREATED)
def start_import(body: ImportIn, svc: Records) -> dict[str, Any]:
    _require(svc, SystemPermission.IMPORT_DATA, "Import Data")
    job = imports.create_job(
        svc,
        body.object_api_name,
        body.file_name,
        body.csv,
        body.mapping,
        body.match_field,
        body.duplicate_action,
    )
    if body.dry_run:
        result = imports.execute(svc, job, dry_run=True)
        svc.db.rollback()
        return {"dry_run": True, **result, "error_rows": result["error_rows"][:100]}
    audit.record(
        svc.db,
        action=AuditAction.CREATE,
        entity_type="import_job",
        entity_id=job.id,
        summary=f"Started import of {job.total_rows} {body.object_api_name} row(s)",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    svc.db.commit()
    if job.total_rows <= imports.INLINE_ROWS:
        imports.run_import(svc.db, job.id)
    else:
        from app.tenancy import tenant_schema
        from app.worker.tasks import run_import_task

        run_import_task.delay(str(job.id), tenant_schema(svc.db))
    svc.db.refresh(job)
    return _job_out(job)


@router.get("/imports")
def list_imports(svc: Records) -> list[dict[str, Any]]:
    _require(svc, SystemPermission.IMPORT_DATA, "Import Data")
    assert svc.user_id is not None
    return [_job_out(j) for j in imports.recent_jobs(svc.db, svc.user_id, svc.policy.is_system_admin)]


def _job(svc: Any, job_id: uuid.UUID) -> ImportJob:
    job: ImportJob | None = svc.db.get(ImportJob, job_id)
    if job is None or (job.created_by_id != svc.user_id and not svc.policy.is_system_admin):
        raise NotFoundError("Import not found.")
    return job


@router.get("/imports/{job_id}")
def get_import(job_id: uuid.UUID, svc: Records) -> dict[str, Any]:
    job = _job(svc, job_id)
    return {**_job_out(job), "error_rows": (job.errors or [])[:200]}


@router.get("/imports/{job_id}/errors.csv")
def import_errors(job_id: uuid.UUID, svc: Records) -> Response:
    job = _job(svc, job_id)
    return Response(
        imports.errors_csv(job),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="import-errors-{job.id}.csv"'},
    )


@router.post("/exports")
def export(body: ExportIn, svc: Records) -> Response:
    _require(svc, SystemPermission.EXPORT_DATA, "Export Data")
    meta = svc.object(body.object_api_name)
    filters = body.filters
    scope: str = body.scope
    sort: list[dict[str, str]] | None = None
    columns = body.columns
    if body.view_id is not None:
        view = next((v for v in visible_list_views(svc, meta.api_name) if v.id == body.view_id), None)
        if view is None:
            raise NotFoundError("List view not found.")
        if view.filters:
            filters = {"logic": "and", "conditions": [view.filters, filters]} if filters else view.filters
        scope = view.scope if body.scope == "all" else body.scope
        sort = view.sort or None
        columns = columns or view.columns
    text, count = imports.export_csv(
        svc, meta.api_name, columns=columns, filters=filters, scope=scope, sort=sort
    )
    audit.record(
        svc.db,
        action=AuditAction.EXPORT,
        entity_type=f"record:{meta.api_name}",
        summary=f"Exported {count} {meta.plural_label}",
        actor_id=svc.user_id,
        changes={"filters": {"from": None, "to": filters}, "rows": {"from": None, "to": count}},
        meta=svc.request_meta,
    )
    svc.db.commit()
    return Response(
        "﻿" + text,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{meta.api_name}-export.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/objects/{api_name}/records/{record_id}/pdf")
def document_pdf(api_name: str, record_id: uuid.UUID, svc: Records) -> Response:
    if api_name not in ("invoice", "quote"):
        raise NotFoundError("PDFs are available for invoices and quotes.")
    record = svc.get(api_name, record_id)
    content = render_document(svc, record)
    audit.record(
        svc.db,
        action=AuditAction.DOWNLOAD,
        entity_type=f"record:{api_name}",
        entity_id=record.id,
        summary=f"Downloaded PDF of {record.name}",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    svc.db.commit()
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{record.name}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )

"""/reports, /dashboards, /report-folders (plan v3, section 12)."""

from __future__ import annotations

import contextvars
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select

from app.core.errors import NotFoundError, PermissionDeniedError
from app.db.session import sibling_session
from app.engine.deps import Records
from app.engine.records import RecordService
from app.models import Dashboard, Report, ReportFolder, ReportSchedule, User
from app.security.catalog import SystemPermission
from app.security.policy import load_policy
from app.services import audit
from app.services import reports as svc_reports
from app.services.audit import AuditAction

# Components of one dashboard run concurrently (each holds one pooled connection while it runs).
DASHBOARD_PARALLELISM = 6

router = APIRouter(tags=["analytics"])


class FolderIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    visibility: Literal["private", "public", "shared"] = "private"
    shared_profile_ids: list[uuid.UUID] = Field(default_factory=list)
    shared_role_ids: list[uuid.UUID] = Field(default_factory=list)


class ReportIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    folder_id: uuid.UUID | None = None
    object_api_name: str = Field(max_length=80)
    definition: dict[str, Any] = Field(default_factory=dict)


class RunIn(BaseModel):
    filters: dict[str, Any] | None = None
    scope: Literal["all", "mine", "team"] | None = None


class DashboardIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    folder_id: uuid.UUID | None = None
    running_user_id: uuid.UUID | None = None
    components: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


class ScheduleIn(BaseModel):
    frequency: Literal["daily", "weekly", "monthly"]
    recipients: list[EmailStr] = Field(default_factory=list, max_length=20)
    first_run_at: datetime | None = None


def _folder_out(f: ReportFolder, svc: RecordService) -> dict[str, Any]:
    return {
        "id": str(f.id),
        "name": f.name,
        "key": f.key,
        "visibility": f.visibility,
        "shared_profile_ids": f.shared_profile_ids,
        "shared_role_ids": f.shared_role_ids,
        "is_mine": f.owner_id == svc.user_id,
        "can_edit": svc.policy.is_system_admin
        or f.owner_id == svc.user_id
        or (f.visibility != "private" and svc.policy.has(SystemPermission.MANAGE_PUBLIC_REPORTS)),
    }


def _report_out(r: Report, svc: RecordService, folders: dict[uuid.UUID, ReportFolder]) -> dict[str, Any]:
    folder = folders.get(r.folder_id) if r.folder_id else None
    meta = svc.registry.objects.get(r.object_api_name)
    return {
        "id": str(r.id),
        "name": r.name,
        "key": r.key,
        "description": r.description,
        "folder_id": str(r.folder_id) if r.folder_id else None,
        "folder_name": folder.name if folder else "Private Reports",
        "object_api_name": r.object_api_name,
        "object_label": meta.plural_label if meta else r.object_api_name,
        "definition": r.definition,
        "owner_id": str(r.owner_id) if r.owner_id else None,
        "updated_at": r.updated_at,
        "last_run_at": r.last_run_at,
        "can_edit": svc_reports.can_manage(svc, folder, r.owner_id),
    }


def _folder(svc: RecordService, folder_id: uuid.UUID | None) -> ReportFolder | None:
    if folder_id is None:
        return None
    folder = svc.db.get(ReportFolder, folder_id)
    if folder is None or not svc_reports.folder_visible(svc, folder, folder.owner_id):
        raise NotFoundError("Folder not found.")
    return folder


def _visible_folders(svc: RecordService) -> dict[uuid.UUID, ReportFolder]:
    return {
        f.id: f
        for f in svc.db.scalars(select(ReportFolder).order_by(ReportFolder.name))
        if svc_reports.folder_visible(svc, f, f.owner_id)
    }


# ---------------------------------------------------------------- folders


@router.get("/report-folders")
def list_folders(svc: Records) -> list[dict[str, Any]]:
    if not svc.policy.object("report").read:
        raise PermissionDeniedError("You don't have access to reports.")
    return [_folder_out(f, svc) for f in _visible_folders(svc).values()]


@router.post("/report-folders", status_code=status.HTTP_201_CREATED)
def create_folder(body: FolderIn, svc: Records) -> dict[str, Any]:
    if not svc.policy.object("report").create:
        raise PermissionDeniedError("You can't create report folders.")
    if body.visibility != "private" and not svc.policy.has(SystemPermission.MANAGE_PUBLIC_REPORTS):
        raise PermissionDeniedError("Public folders need the Manage Public Reports & Dashboards permission.")
    folder = ReportFolder(
        name=body.name.strip(),
        owner_id=svc.user_id,
        visibility=body.visibility,
        shared_profile_ids=[str(i) for i in body.shared_profile_ids],
        shared_role_ids=[str(i) for i in body.shared_role_ids],
    )
    svc.db.add(folder)
    svc.db.flush()
    audit.record(
        svc.db,
        action=AuditAction.CREATE,
        entity_type="report_folder",
        entity_id=folder.id,
        summary=f"Created report folder {folder.name}",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    svc.db.commit()
    return _folder_out(folder, svc)


@router.put("/report-folders/{folder_id}")
def update_folder(folder_id: uuid.UUID, body: FolderIn, svc: Records) -> dict[str, Any]:
    folder = _folder(svc, folder_id)
    assert folder is not None
    if not _folder_out(folder, svc)["can_edit"]:
        raise PermissionDeniedError("You can't change this folder.")
    if body.visibility != "private" and not svc.policy.has(SystemPermission.MANAGE_PUBLIC_REPORTS):
        raise PermissionDeniedError("Public folders need the Manage Public Reports & Dashboards permission.")
    folder.name, folder.visibility = body.name.strip(), body.visibility
    folder.shared_profile_ids = [str(i) for i in body.shared_profile_ids]
    folder.shared_role_ids = [str(i) for i in body.shared_role_ids]
    audit.record(
        svc.db,
        action=AuditAction.UPDATE,
        entity_type="report_folder",
        entity_id=folder.id,
        summary=f"Updated report folder {folder.name}",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    svc.db.commit()
    return _folder_out(folder, svc)


@router.delete("/report-folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(folder_id: uuid.UUID, svc: Records) -> Response:
    folder = _folder(svc, folder_id)
    assert folder is not None
    if not _folder_out(folder, svc)["can_edit"] or folder.key:
        raise PermissionDeniedError("You can't delete this folder.")
    if svc.db.scalar(select(Report.id).where(Report.folder_id == folder.id).limit(1)) or svc.db.scalar(
        select(Dashboard.id).where(Dashboard.folder_id == folder.id).limit(1)
    ):
        raise PermissionDeniedError("Move or delete the folder's reports and dashboards first.")
    svc.db.delete(folder)
    svc.db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- reports


# Objects only the generic apps use. Their reports and dashboards are listed while an app showing them is
# switched on (a law firm with the Sales app hidden doesn't see pipeline and win-rate reports).
_APP_ONLY_OBJECTS = frozenset(
    {
        "opportunity",
        "opportunity_product",
        "quote",
        "quote_line",
        "case",
        "campaign",
        "campaign_member",
        "email_send",
        "invoice",
        "invoice_line",
        "payment",
    }
)

# Shown only while a visible app has a tab for its object (a broker paid by commission has no invoices).
_DASHBOARD_OBJECT = {"billing_dashboard": "invoice"}


# The standard dashboards that belong to one generic app.
_DASHBOARD_APP = {
    "sales_dashboard": "sales",
    "service_dashboard": "service",
    "marketing_dashboard": "marketing",
}


def _unused_objects(svc: Records) -> set[str]:
    from app.models import App

    tabs = [t for app in svc.db.scalars(select(App).where(App.is_active.is_(True))) for t in (app.tabs or [])]
    shown = {str(t.get("object")) for t in tabs if t.get("kind") == "object"}
    if any(t.get("kind") == "queues" for t in tabs):
        shown.add("case")
    return set(_APP_ONLY_OBJECTS - shown)


@router.get("/reports")
def list_reports(
    svc: Records, q: Annotated[str | None, Query(max_length=100)] = None, folder_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    if not svc.policy.object("report").read:
        raise PermissionDeniedError("You don't have access to reports.")
    folders = _visible_folders(svc)
    stmt = select(Report).where(
        or_(Report.folder_id.in_(list(folders)), Report.owner_id == svc.user_id)
        if not svc.policy.is_system_admin
        else Report.id.is_not(None)
    )
    if folder_id:
        stmt = stmt.where(Report.folder_id == folder_id)
    if q:
        stmt = stmt.where(Report.name.ilike(f"%{q.strip()}%"))
    rows = svc.db.scalars(stmt.order_by(Report.name)).all()
    enabled = svc.enabled_packs
    unused = _unused_objects(svc)
    out = []
    for r in rows:
        meta = svc.registry.objects.get(r.object_api_name)
        if (
            meta is None
            or (r.owner_id is None and r.object_api_name in unused)
            or (meta.pack_key and meta.pack_key not in enabled)
            or not svc.policy.object(r.object_api_name).read
        ):
            continue
        out.append(_report_out(r, svc, folders))
    return out


@router.get("/reports/columns/{object_api_name}")
def report_columns(object_api_name: str, svc: Records) -> list[dict[str, Any]]:
    return svc_reports.available_columns(svc, object_api_name)


@router.post("/reports", status_code=status.HTTP_201_CREATED)
def create_report(body: ReportIn, svc: Records) -> dict[str, Any]:
    if not svc.policy.object("report").create:
        raise PermissionDeniedError("You can't create reports.")
    folder = _folder(svc, body.folder_id)
    if not svc_reports.can_manage(svc, folder, svc.user_id) and folder is not None:
        raise PermissionDeniedError("You can't save reports in this folder.")
    svc_reports.validate_definition(svc, body.object_api_name, body.definition)
    report = Report(
        name=body.name.strip(),
        description=body.description,
        folder_id=folder.id if folder else None,
        owner_id=svc.user_id,
        object_api_name=body.object_api_name,
        definition=body.definition,
    )
    svc.db.add(report)
    svc.db.flush()
    audit.record(
        svc.db,
        action=AuditAction.CREATE,
        entity_type="report",
        entity_id=report.id,
        summary=f"Created report {report.name}",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    svc.db.commit()
    return _report_out(report, svc, _visible_folders(svc))


@router.get("/reports/{report_id}")
def get_report(report_id: uuid.UUID, svc: Records) -> dict[str, Any]:
    return _report_out(svc_reports.get_report(svc, report_id), svc, _visible_folders(svc))


@router.put("/reports/{report_id}")
def update_report(report_id: uuid.UUID, body: ReportIn, svc: Records) -> dict[str, Any]:
    report = svc_reports.get_report(svc, report_id)
    old_folder = _folder(svc, report.folder_id)
    new_folder = _folder(svc, body.folder_id)
    if not svc_reports.can_manage(svc, old_folder, report.owner_id) or (
        new_folder is not None and not svc_reports.can_manage(svc, new_folder, report.owner_id)
    ):
        raise PermissionDeniedError("You can't change this report.")
    svc_reports.validate_definition(svc, body.object_api_name, body.definition)
    report.name, report.description = body.name.strip(), body.description
    report.folder_id = new_folder.id if new_folder else None
    report.object_api_name, report.definition = body.object_api_name, body.definition
    audit.record(
        svc.db,
        action=AuditAction.UPDATE,
        entity_type="report",
        entity_id=report.id,
        summary=f"Updated report {report.name}",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    svc.db.commit()
    return _report_out(report, svc, _visible_folders(svc))


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(report_id: uuid.UUID, svc: Records) -> Response:
    report = svc_reports.get_report(svc, report_id)
    if (
        not svc.policy.object("report").delete
        or not svc_reports.can_manage(svc, _folder(svc, report.folder_id), report.owner_id)
        or report.key
    ):
        raise PermissionDeniedError("You can't delete this report.")
    svc.db.delete(report)
    audit.record(
        svc.db,
        action=AuditAction.DELETE,
        entity_type="report",
        entity_id=report.id,
        summary=f"Deleted report {report.name}",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    svc.db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reports/run")
def run_unsaved(body: ReportIn, svc: Records) -> dict[str, Any]:
    """Preview a definition in the builder without saving it."""
    if not svc.policy.object("report").read:
        raise PermissionDeniedError("You don't have access to reports.")
    result = svc_reports.Runner(svc, body.object_api_name, body.definition).run()
    return {
        "report": {"id": None, "name": body.name, "object": body.object_api_name},
        "run_at": datetime.now(UTC),
        **result,
    }


@router.post("/reports/{report_id}/run")
def run_report(report_id: uuid.UUID, svc: Records, body: RunIn | None = None) -> dict[str, Any]:
    report = svc_reports.get_report(svc, report_id)
    overrides: dict[str, Any] = {}
    if body is not None and body.filters:
        base = report.definition.get("filters")
        overrides["filters"] = {"logic": "and", "conditions": [base, body.filters]} if base else body.filters
    if body is not None and body.scope:
        overrides["scope"] = body.scope
    result = svc_reports.run_report(svc, report, overrides)
    svc.db.commit()
    return result


@router.get("/reports/{report_id}/export.csv")
def export_report(report_id: uuid.UUID, svc: Records) -> Response:
    if not svc.policy.has(SystemPermission.EXPORT_DATA):
        raise PermissionDeniedError("Exporting needs the Export Data permission.")
    report = svc_reports.get_report(svc, report_id)
    result = svc_reports.run_report(svc, report)
    audit.record(
        svc.db,
        action=AuditAction.EXPORT,
        entity_type="report",
        entity_id=report.id,
        summary=f"Exported report {report.name}",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    svc.db.commit()
    name = "".join(ch for ch in report.name if ch.isalnum() or ch in " -_").strip() or "report"
    return Response(
        svc_reports.to_csv(result),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}.csv"', "Cache-Control": "no-store"},
    )


@router.get("/reports/{report_id}/schedules")
def list_schedules(report_id: uuid.UUID, svc: Records) -> list[dict[str, Any]]:
    svc_reports.get_report(svc, report_id)
    rows = svc.db.scalars(select(ReportSchedule).where(ReportSchedule.report_id == report_id)).all()
    return [
        {
            "id": str(s.id),
            "frequency": s.frequency,
            "recipients": s.recipients,
            "next_run_at": s.next_run_at,
            "last_run_at": s.last_run_at,
            "is_mine": s.owner_id == svc.user_id,
        }
        for s in rows
    ]


@router.post("/reports/{report_id}/schedules", status_code=status.HTTP_201_CREATED)
def create_schedule(report_id: uuid.UUID, body: ScheduleIn, svc: Records) -> dict[str, Any]:
    svc_reports.get_report(svc, report_id)
    if body.recipients and not svc.policy.has(SystemPermission.MANAGE_PUBLIC_REPORTS):
        raise PermissionDeniedError(
            "E-mailing reports to others needs the Manage Public Reports & Dashboards permission."
        )
    first = body.first_run_at or svc_reports.next_run(body.frequency, datetime.now(UTC))
    sched = ReportSchedule(
        report_id=report_id,
        owner_id=svc.user_id,
        frequency=body.frequency,
        recipients=[str(r) for r in body.recipients],
        next_run_at=first,
    )
    svc.db.add(sched)
    svc.db.flush()
    audit.record(
        svc.db,
        action=AuditAction.CREATE,
        entity_type="report_schedule",
        entity_id=sched.id,
        summary=f"Scheduled report ({body.frequency})",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    svc.db.commit()
    return {
        "id": str(sched.id),
        "frequency": sched.frequency,
        "recipients": sched.recipients,
        "next_run_at": sched.next_run_at,
    }


@router.delete("/reports/{report_id}/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(report_id: uuid.UUID, schedule_id: uuid.UUID, svc: Records) -> Response:
    sched = svc.db.get(ReportSchedule, schedule_id)
    if sched is None or sched.report_id != report_id:
        raise NotFoundError("Schedule not found.")
    if sched.owner_id != svc.user_id and not svc.policy.is_system_admin:
        raise PermissionDeniedError("You can't delete this schedule.")
    svc.db.delete(sched)
    svc.db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- dashboards


def _dash_out(d: Dashboard, svc: RecordService, folders: dict[uuid.UUID, ReportFolder]) -> dict[str, Any]:
    folder = folders.get(d.folder_id) if d.folder_id else None
    return {
        "id": str(d.id),
        "name": d.name,
        "key": d.key,
        "description": d.description,
        "folder_id": str(d.folder_id) if d.folder_id else None,
        "folder_name": folder.name if folder else "Private",
        "running_user_id": str(d.running_user_id) if d.running_user_id else None,
        "components": d.components,
        "updated_at": d.updated_at,
        "can_edit": svc_reports.can_manage(svc, folder, d.owner_id, "dashboard"),
    }


def _check_components(svc: RecordService, components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for c in components:
        rid = uuid.UUID(str(c.get("report_id")))
        svc_reports.get_report(svc, rid)
        chart = c.get("chart") or "bar"
        if chart not in ("bar", "column", "line", "donut", "funnel", "kpi", "table"):
            raise svc_reports.ReportError("Unknown chart type.")
        out.append(
            {
                "report_id": str(rid),
                "title": str(c.get("title") or "")[:120],
                "chart": chart,
                "width": max(1, min(3, int(c.get("width") or 1))),
            }
        )
    return out


@router.get("/dashboards")
def list_dashboards(svc: Records) -> list[dict[str, Any]]:
    if not svc.policy.object("dashboard").read:
        raise PermissionDeniedError("You don't have access to dashboards.")
    folders = _visible_folders(svc)
    rows = svc.db.scalars(select(Dashboard).order_by(Dashboard.name)).all()
    unused = _unused_objects(svc)
    hidden_reports = {
        str(r.id) for r in svc.db.scalars(select(Report).where(Report.object_api_name.in_(unused)))
    } | {
        str(r.key) for r in svc.db.scalars(select(Report).where(Report.object_api_name.in_(unused))) if r.key
    }

    from app.models import App

    inactive = {a.key for a in svc.db.scalars(select(App).where(App.is_active.is_(False)))}

    def about_unused(d: Dashboard) -> bool:
        if d.owner_id is None and _DASHBOARD_APP.get(str(d.key)) in inactive:
            return True
        if d.owner_id is None and _DASHBOARD_OBJECT.get(str(d.key)) in unused:
            return True
        refs = [str(c.get("report_id") or c.get("report") or "") for c in d.components or []]
        return d.owner_id is None and bool(refs) and all(ref in hidden_reports for ref in refs)

    return [
        _dash_out(d, svc, folders)
        for d in rows
        if svc_reports.folder_visible(svc, folders.get(d.folder_id) if d.folder_id else None, d.owner_id)
        and not about_unused(d)
    ]


@router.post("/dashboards", status_code=status.HTTP_201_CREATED)
def create_dashboard(body: DashboardIn, svc: Records) -> dict[str, Any]:
    if not svc.policy.object("dashboard").create:
        raise PermissionDeniedError("You can't create dashboards.")
    folder = _folder(svc, body.folder_id)
    if folder is not None and not svc_reports.can_manage(svc, folder, svc.user_id, "dashboard"):
        raise PermissionDeniedError("You can't save dashboards in this folder.")
    if (
        body.running_user_id
        and body.running_user_id != svc.user_id
        and not svc.policy.has(SystemPermission.MANAGE_PUBLIC_REPORTS)
    ):
        raise PermissionDeniedError(
            "Running a dashboard as another user needs Manage Public Reports & Dashboards."
        )
    dash = Dashboard(
        name=body.name.strip(),
        description=body.description,
        folder_id=folder.id if folder else None,
        owner_id=svc.user_id,
        running_user_id=body.running_user_id,
        components=_check_components(svc, body.components),
    )
    svc.db.add(dash)
    svc.db.flush()
    audit.record(
        svc.db,
        action=AuditAction.CREATE,
        entity_type="dashboard",
        entity_id=dash.id,
        summary=f"Created dashboard {dash.name}",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    svc.db.commit()
    return _dash_out(dash, svc, _visible_folders(svc))


@router.put("/dashboards/{dashboard_id}")
def update_dashboard(dashboard_id: uuid.UUID, body: DashboardIn, svc: Records) -> dict[str, Any]:
    dash = svc_reports.get_dashboard(svc, dashboard_id)
    if not svc_reports.can_manage(svc, _folder(svc, dash.folder_id), dash.owner_id, "dashboard"):
        raise PermissionDeniedError("You can't change this dashboard.")
    folder = _folder(svc, body.folder_id)
    if (
        body.running_user_id
        and body.running_user_id != dash.running_user_id
        and not svc.policy.has(SystemPermission.MANAGE_PUBLIC_REPORTS)
    ):
        raise PermissionDeniedError(
            "Running a dashboard as another user needs Manage Public Reports & Dashboards."
        )
    dash.name, dash.description = body.name.strip(), body.description
    dash.folder_id = folder.id if folder else None
    dash.running_user_id = body.running_user_id
    dash.components = _check_components(svc, body.components)
    audit.record(
        svc.db,
        action=AuditAction.UPDATE,
        entity_type="dashboard",
        entity_id=dash.id,
        summary=f"Updated dashboard {dash.name}",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    svc.db.commit()
    return _dash_out(dash, svc, _visible_folders(svc))


@router.delete("/dashboards/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dashboard(dashboard_id: uuid.UUID, svc: Records) -> Response:
    dash = svc_reports.get_dashboard(svc, dashboard_id)
    if (
        not svc.policy.object("dashboard").delete
        or not svc_reports.can_manage(svc, _folder(svc, dash.folder_id), dash.owner_id, "dashboard")
        or dash.key
    ):
        raise PermissionDeniedError("You can't delete this dashboard.")
    svc.db.delete(dash)
    svc.db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/dashboards/{dashboard_id}")
def get_dashboard(dashboard_id: uuid.UUID, svc: Records) -> dict[str, Any]:
    return _dash_out(svc_reports.get_dashboard(svc, dashboard_id), svc, _visible_folders(svc))


def _dashboard_reports(runner: RecordService, parts: list[dict[str, Any]]) -> dict[str, Report]:
    """The components' reports the running user may see, in two queries (reports, then their folders).

    Detached from the session: running a report stamps ``last_run_at``, which a dashboard view does not save.
    """
    if not runner.policy.object("report").read:
        return {}
    ids: list[uuid.UUID] = []
    for c in parts:
        try:
            ids.append(uuid.UUID(str(c.get("report_id"))))
        except ValueError:
            continue
    if not ids:
        return {}
    found = list(runner.db.scalars(select(Report).where(Report.id.in_(ids))))
    folder_ids = {r.folder_id for r in found if r.folder_id}
    folders = (
        {f.id: f for f in runner.db.scalars(select(ReportFolder).where(ReportFolder.id.in_(folder_ids)))}
        if folder_ids
        else {}
    )
    visible = {
        str(r.id): r
        for r in found
        if svc_reports.folder_visible(runner, folders.get(r.folder_id) if r.folder_id else None, r.owner_id)
    }
    for r in found:
        runner.db.expunge(r)
    return visible


@router.post("/dashboards/key/{key}/run")
def run_dashboard_by_key(key: str, svc: Records, body: RunIn | None = None) -> dict[str, Any]:
    """Run a dashboard by its stable key (e.g. a pack's home dashboard): one call instead of listing the
    dashboards to find its id first."""
    dashboard_id = svc.db.scalar(select(Dashboard.id).where(Dashboard.key == key))
    if dashboard_id is None:
        raise NotFoundError("Dashboard not found.")
    return run_dashboard(dashboard_id, svc, body)


@router.post("/dashboards/{dashboard_id}/run")
def run_dashboard(dashboard_id: uuid.UUID, svc: Records, body: RunIn | None = None) -> dict[str, Any]:
    """Run every component, as the dashboard's running user when one is set ("view as")."""
    dash = svc_reports.get_dashboard(svc, dashboard_id)
    runner = svc
    viewing_as = None
    if dash.running_user_id and dash.running_user_id != svc.user_id:
        user = svc.db.get(User, dash.running_user_id)
        if user is not None and user.is_active:
            runner = RecordService.for_user(svc.db, user, load_policy(svc.db, user), svc.request_meta)
            viewing_as = user.name
    extra_filters = body.filters if body is not None else None
    parts = list(dash.components)
    reports = _dashboard_reports(runner, parts)

    def run_component(c: dict[str, Any]) -> dict[str, Any]:
        # Each component runs on its own read-only session so components run in parallel: the dashboard
        # takes about as long as its slowest component instead of the sum of all of them. The reports and
        # the running user's access were loaded up front, so a component only runs its own queries.
        if not runner.policy.object("report").read:
            return {**c, "result": None, "error": "You don't have access to reports."}
        report = reports.get(str(c.get("report_id")))
        if report is None:
            return {**c, "result": None, "error": "Report not found."}
        overrides: dict[str, Any] = {}
        if extra_filters:
            base = report.definition.get("filters")
            overrides["filters"] = (
                {"logic": "and", "conditions": [base, extra_filters]} if base else extra_filters
            )
        with sibling_session(svc.db) as db:
            try:
                worker = RecordService(db, runner.policy, meta=svc.request_meta)
                worker.time_zone = runner.time_zone
                return {
                    **c,
                    "result": svc_reports.run_report(worker, report, overrides, reset_timeout=False),
                    "error": None,
                }
            except Exception as exc:
                db.rollback()
                return {
                    **c,
                    "result": None,
                    "error": getattr(exc, "message", "This component can't be shown."),
                }

    if len(parts) <= 1:
        components = [run_component(c) for c in parts]
    else:
        # Each worker gets a copy of this request's context (taken here, on the request's thread) so its
        # queries count towards the request's Server-Timing.
        contexts = [contextvars.copy_context() for _ in parts]
        with ThreadPoolExecutor(max_workers=min(DASHBOARD_PARALLELISM, len(parts))) as pool:
            components = list(pool.map(lambda ctx, c: ctx.run(run_component, c), contexts, parts))
    svc.db.commit()
    return {
        "dashboard": _dash_out(dash, svc, _visible_folders(svc)),
        "viewing_as": viewing_as,
        "run_at": datetime.now(UTC),
        "components": components,
    }

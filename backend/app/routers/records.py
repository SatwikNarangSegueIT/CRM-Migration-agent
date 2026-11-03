"""/objects/{api}/...: records of any object (plan v3, sections 7 and 13).

All endpoints go through the record engine, so profile permissions, field-level security and record
sharing apply uniformly to standard, custom and pack objects.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import Numeric, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.engine import hooks
from app.engine.describe import visible_list_views
from app.engine.deps import Records
from app.engine.filters import FilterError, compile_filter
from app.engine.records import QueryResult, RecordService
from app.models import ListView, RecentItem, Record, UserPreference
from app.security.catalog import SystemPermission
from app.services import audit
from app.services.audit import AuditAction

router = APIRouter(prefix="/objects/{api_name}", tags=["records"])

Scope = Literal["mine", "all", "team", "queue"]


class SortSpec(BaseModel):
    field: str = Field(max_length=80)
    direction: Literal["asc", "desc"] = "asc"


class QueryIn(BaseModel):
    filters: dict[str, Any] | None = None
    columns: list[str] | None = None
    sort: list[SortSpec] | None = None
    scope: Scope = "all"
    search: str | None = Field(default=None, max_length=100)
    cursor: str | None = Field(default=None, max_length=500)
    limit: int = Field(default=50, ge=1, le=200)
    view_id: uuid.UUID | None = None
    deleted: bool = False


class RecordIn(BaseModel):
    name: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    owner_id: uuid.UUID | None = None
    queue_id: uuid.UUID | None = None


class RecordUpdate(BaseModel):
    version: int
    name: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)


class OwnerIn(BaseModel):
    owner_id: uuid.UUID | None = None
    queue_id: uuid.UUID | None = None


class BulkIn(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    operation: Literal["update", "change_owner", "delete"]
    values: dict[str, Any] | None = None
    owner_id: uuid.UUID | None = None
    queue_id: uuid.UUID | None = None


class ShareIn(BaseModel):
    principal_type: Literal["user", "group", "role", "role_and_subordinates"]
    principal_id: uuid.UUID
    access: Literal["read", "read_write"] = "read"


class ListViewIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    visibility: Literal["private", "public", "shared"] = "private"
    shared_profile_ids: list[uuid.UUID] = Field(default_factory=list)
    shared_role_ids: list[uuid.UUID] = Field(default_factory=list)
    scope: Scope = "all"
    columns: list[str] = Field(default_factory=list, max_length=30)
    filters: dict[str, Any] = Field(default_factory=dict)
    sort: list[SortSpec] = Field(default_factory=list)
    kanban_field: str | None = None


def _page(svc: RecordService, api_name: str, result: QueryResult, columns: list[str] | None) -> dict[str, Any]:
    return {
        "items": svc.serialize_many(api_name, result.records, columns=columns),
        "next_cursor": result.next_cursor,
        "total": result.total,
        "total_capped": result.total_capped,
    }


def _view(svc: RecordService, api_name: str, view_id: uuid.UUID) -> ListView:
    for view in visible_list_views(svc, api_name):
        if view.id == view_id:
            return view
    raise NotFoundError("List view not found.")


def _run_query(svc: RecordService, api_name: str, body: QueryIn) -> dict[str, Any]:
    filters = body.filters
    scope: str = body.scope
    sort = [s.model_dump() for s in body.sort] if body.sort else None
    columns = body.columns
    if body.view_id is not None:
        view = _view(svc, api_name, body.view_id)
        view_filters = view.filters or None
        if filters and view_filters:
            filters = {"logic": "and", "conditions": [view_filters, filters]}
        else:
            filters = filters or view_filters
        if body.scope == "all":
            scope = view.scope
        sort = sort or (view.sort or None)
        columns = columns or (view.columns or None)
    if body.deleted:
        # Recycle bin for this object: only records the user deleted, unless they have Modify All.
        result = svc.query(api_name, filters=filters, search=body.search, sort=sort, cursor=body.cursor,
                           limit=body.limit, deleted=True,
                           extra=[] if svc.policy.object(api_name).modify_all else [Record.deleted_by_id == svc.user_id])
    else:
        result = svc.query(api_name, filters=filters, scope=scope, search=body.search, sort=sort,
                           cursor=body.cursor, limit=body.limit)
    return _page(svc, api_name, result, columns)


@router.get("/records")
def list_records(
    api_name: str,
    svc: Records,
    view_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    sort: Annotated[str | None, Query(max_length=80)] = None,
    direction: Literal["asc", "desc"] = "asc",
    scope: Scope = "all",
) -> dict[str, Any]:
    body = QueryIn(
        view_id=view_id, search=q, cursor=cursor, limit=limit, scope=scope,
        sort=[SortSpec(field=sort, direction=direction)] if sort else None,
    )
    return _run_query(svc, api_name, body)


@router.post("/records/query")
def query_records(api_name: str, body: QueryIn, svc: Records) -> dict[str, Any]:
    return _run_query(svc, api_name, body)


@router.post("/records", status_code=status.HTTP_201_CREATED)
def create_record(api_name: str, body: RecordIn, svc: Records) -> dict[str, Any]:
    values = dict(body.fields)
    if body.name is not None:
        values["name"] = body.name
    record = svc.create(api_name, values, owner_id=body.owner_id, queue_id=body.queue_id)
    svc.db.commit()
    return svc.serialize(record)


@router.get("/records/{record_id}")
def get_record(api_name: str, record_id: uuid.UUID, svc: Records, track: bool = True) -> dict[str, Any]:
    record = svc.get(api_name, record_id, include_deleted=True)
    if record.is_deleted and not (svc.policy.object(api_name).modify_all or record.deleted_by_id == svc.user_id):
        raise NotFoundError("Record not found.")
    if track and svc.user_id is not None and not record.is_deleted:
        stmt = pg_insert(RecentItem).values(user_id=svc.user_id, record_id=record.id, viewed_at=datetime.now(UTC))
        svc.db.execute(stmt.on_conflict_do_update(index_elements=["user_id", "record_id"], set_={"viewed_at": stmt.excluded.viewed_at}))
        svc.db.commit()
    out = svc.serialize(record)
    out["actions"] = [
        {"name": a.name, "label": a.label}
        for a in hooks.actions_for(api_name, svc.enabled_packs)
        if (a.visible is None or a.visible(record)) and (not a.requires_edit or out["access"]["edit"])
    ]
    return out


@router.patch("/records/{record_id}")
def update_record(api_name: str, record_id: uuid.UUID, body: RecordUpdate, svc: Records) -> dict[str, Any]:
    values = dict(body.fields)
    if body.name is not None:
        values["name"] = body.name
    record = svc.update(api_name, record_id, values, version=body.version)
    svc.db.commit()
    return svc.serialize(record)


@router.delete("/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(api_name: str, record_id: uuid.UUID, svc: Records) -> Response:
    svc.delete(api_name, record_id)
    svc.db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/records/{record_id}/restore")
def restore_record(api_name: str, record_id: uuid.UUID, svc: Records) -> dict[str, Any]:
    record = svc.restore(api_name, record_id)
    svc.db.commit()
    return svc.serialize(record)


@router.post("/records/{record_id}/change-owner")
def change_owner(api_name: str, record_id: uuid.UUID, body: OwnerIn, svc: Records) -> dict[str, Any]:
    record = svc.change_owner(api_name, record_id, body.owner_id, body.queue_id)
    svc.db.commit()
    return svc.serialize(record)


@router.post("/records/bulk")
def bulk(api_name: str, body: BulkIn, svc: Records) -> dict[str, Any]:
    payload: dict[str, Any] = {"values": body.values or {}, "owner_id": body.owner_id, "queue_id": body.queue_id}
    result = svc.bulk(api_name, body.ids, body.operation, payload)
    svc.db.commit()
    return result


@router.get("/records/{record_id}/related/{child_object}/{field_name}")
def related(
    api_name: str,
    record_id: uuid.UUID,
    child_object: str,
    field_name: str,
    svc: Records,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 10,
) -> dict[str, Any]:
    result = svc.related(api_name, record_id, child_object, field_name, limit=limit, cursor=cursor)
    return _page(svc, child_object, result, None)


@router.get("/records/{record_id}/activities")
def activities(api_name: str, record_id: uuid.UUID, svc: Records) -> dict[str, Any]:
    """Activity timeline: tasks, events, notes and files related to the record (newest first)."""
    svc.get(api_name, record_id)
    out: dict[str, Any] = {}
    for child in ("task", "event", "note", "file"):
        meta = svc.registry.objects.get(child)
        if meta is None or "related_to" not in meta.fields or api_name not in meta.fields["related_to"].targets:
            continue
        if not svc.policy.object(child).read:
            continue
        sort = {"task": "due_date", "event": "start_at"}.get(child, "created_at")
        result = svc.related(api_name, record_id, child, "related_to", limit=50, sort=[{"field": sort, "direction": "desc"}])
        out[child] = svc.serialize_many(child, result.records)
    return out


@router.get("/records/{record_id}/history")
def history(api_name: str, record_id: uuid.UUID, svc: Records) -> list[dict[str, Any]]:
    return svc.history(api_name, record_id)


@router.get("/records/{record_id}/shares")
def list_shares(api_name: str, record_id: uuid.UUID, svc: Records) -> list[dict[str, Any]]:
    return [
        {"id": str(s.id), "principal_type": s.principal_type, "principal_id": str(s.principal_id), "access": s.access, "created_at": s.created_at}
        for s in svc.shares(api_name, record_id)
    ]


@router.post("/records/{record_id}/shares", status_code=status.HTTP_201_CREATED)
def add_share(api_name: str, record_id: uuid.UUID, body: ShareIn, svc: Records) -> dict[str, Any]:
    share = svc.add_share(api_name, record_id, body.principal_type, body.principal_id, body.access)
    svc.db.commit()
    return {"id": str(share.id), "principal_type": share.principal_type, "principal_id": str(share.principal_id), "access": share.access}


@router.delete("/records/{record_id}/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_share(api_name: str, record_id: uuid.UUID, share_id: uuid.UUID, svc: Records) -> Response:
    svc.remove_share(api_name, record_id, share_id)
    svc.db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/records/{record_id}/actions/{action_name}")
def run_action(api_name: str, record_id: uuid.UUID, action_name: str, svc: Records, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    action = hooks.get_action(api_name, action_name)
    if action is None or (action.pack_key and action.pack_key not in svc.enabled_packs):
        raise NotFoundError("Action not found.")
    record = svc.get(api_name, record_id, lock=True)
    if action.requires_edit and not svc.can_edit(record):
        raise PermissionDeniedError("You don't have permission to edit this record.")
    if action.guard is not None:
        message = action.guard(svc, record)
        if message:
            raise PermissionDeniedError(message)
    result = action.handler(svc, record, payload or {})
    svc.db.commit()
    return result


@router.get("/lookup")
def lookup(
    api_name: str,
    svc: Records,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[dict[str, Any]]:
    """Lookup picker: readable records whose name matches `q` (recently viewed first when empty)."""
    meta = svc.object(api_name)
    if q:
        result = svc.query(api_name, search=q, limit=limit, count=False)
        records = result.records
    else:
        recent = (
            select(Record)
            .join(RecentItem, RecentItem.record_id == Record.id)
            .where(RecentItem.user_id == svc.user_id, Record.object_api_name == api_name, Record.is_deleted.is_(False),
                   svc.sharing.where_readable(api_name))
            .order_by(RecentItem.viewed_at.desc())
            .limit(limit)
        )
        records = list(svc.db.scalars(recent))
        if len(records) < limit:
            more = svc.query(api_name, limit=limit, count=False, sort=[{"field": "updated_at", "direction": "desc"}]).records
            seen = {r.id for r in records}
            records += [r for r in more if r.id not in seen][: limit - len(records)]
    sub = meta.compact_layout[:1]
    out = []
    for item in svc.serialize_many(api_name, records, columns=sub, with_access=False):
        detail = None
        if sub:
            f = sub[0]
            detail = (item["display"].get(f) or {}).get("name") if f in item["display"] else item["fields"].get(f)
        out.append({"id": item["id"], "name": item["name"], "detail": detail})
    return out


@router.get("/kanban")
def kanban(
    api_name: str,
    svc: Records,
    field: Annotated[str, Query(max_length=80)],
    view_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    per_column: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, Any]:
    meta = svc.object(api_name)
    f = meta.fields.get(field)
    if f is None or f.type != "picklist":
        raise FilterError("Kanban needs a picklist field.")
    svc.check_readable_fields(meta, {field})
    filters: dict[str, Any] | None = None
    scope = "all"
    if view_id is not None:
        view = _view(svc, api_name, view_id)
        filters = view.filters or None
        scope = view.scope
    columns = []
    amount_field = "amount" if "amount" in meta.fields else None
    for value in f.picklist_values:
        if not value.get("active", True):
            continue
        cond: dict[str, Any] = {"field": field, "op": "equals", "value": value["value"]}
        combined = {"logic": "and", "conditions": [filters, cond]} if filters else {"logic": "and", "conditions": [cond]}
        result = svc.query(api_name, filters=combined, scope=scope, search=q, limit=per_column,
                           sort=[{"field": "updated_at", "direction": "desc"}])
        total_amount = None
        if amount_field and svc.field_access(meta, meta.fields[amount_field]).value != "hidden":
            stmt = svc.base_query(meta, scope=scope).where(compile_filter(meta, combined, Record, None, user_id=svc.user_id))
            if q:
                stmt = stmt.where(svc.search_clause(meta, q))
            sub = stmt.subquery()
            total_amount = svc.db.scalar(select(func.coalesce(func.sum(sub.c.data[amount_field].astext.cast(Numeric)), 0)))
        columns.append({
            "value": value["value"], "label": value.get("label", value["value"]), "color": value.get("color"),
            "total": result.total, "amount": float(total_amount) if total_amount is not None else None,
            "items": svc.serialize_many(api_name, result.records),
        })
    return {"field": field, "columns": columns}


# ---------------------------------------------------------------- list views


def _check_view(svc: RecordService, api_name: str, body: ListViewIn) -> None:
    meta = svc.object(api_name)
    names = set(body.columns) | {s.field for s in body.sort}
    if body.kanban_field:
        names.add(body.kanban_field)
        if meta.fields.get(body.kanban_field) is None or meta.fields[body.kanban_field].type != "picklist":
            raise FilterError("Kanban needs a picklist field.")
    svc.check_readable_fields(meta, names)
    if body.filters:
        from app.engine.filters import filter_fields

        svc.check_readable_fields(meta, filter_fields(body.filters))
        compile_filter(meta, body.filters, Record, None, user_id=svc.user_id)
    if body.visibility != "private" and not (
        svc.policy.has(SystemPermission.MANAGE_PUBLIC_REPORTS) or svc.policy.has(SystemPermission.CUSTOMIZE_APPLICATION)
    ):
        raise PermissionDeniedError("Sharing list views needs the Manage Public Reports & Dashboards permission.")


def _view_out(view: ListView, svc: RecordService) -> dict[str, Any]:
    return {
        "id": str(view.id), "object_api_name": view.object_api_name, "name": view.name, "key": view.key,
        "visibility": view.visibility, "shared_profile_ids": view.shared_profile_ids, "shared_role_ids": view.shared_role_ids,
        "scope": view.scope, "columns": view.columns, "filters": view.filters, "sort": view.sort,
        "kanban_field": view.kanban_field, "is_mine": view.owner_id == svc.user_id,
        "can_edit": view.owner_id == svc.user_id or (view.owner_id is None and svc.policy.has(SystemPermission.CUSTOMIZE_APPLICATION)),
    }


@router.get("/list-views")
def list_views(api_name: str, svc: Records) -> dict[str, Any]:
    svc.object(api_name)
    pref = svc.db.get(UserPreference, svc.user_id)
    default = ((pref.data if pref else {}).get("default_views") or {}).get(api_name)
    return {"default_view_id": default, "views": [_view_out(v, svc) for v in visible_list_views(svc, api_name)]}


@router.get("/list-views/{view_id}")
def get_list_view(api_name: str, view_id: uuid.UUID, svc: Records) -> dict[str, Any]:
    return _view_out(_view(svc, api_name, view_id), svc)


@router.post("/list-views", status_code=status.HTTP_201_CREATED)
def create_list_view(api_name: str, body: ListViewIn, svc: Records) -> dict[str, Any]:
    _check_view(svc, api_name, body)
    view = ListView(
        object_api_name=api_name, name=body.name.strip(), owner_id=svc.user_id, visibility=body.visibility,
        shared_profile_ids=[str(i) for i in body.shared_profile_ids], shared_role_ids=[str(i) for i in body.shared_role_ids],
        scope=body.scope, columns=body.columns, filters=body.filters, sort=[s.model_dump() for s in body.sort],
        kanban_field=body.kanban_field,
    )
    svc.db.add(view)
    svc.db.flush()
    audit.record(svc.db, action=AuditAction.CREATE, entity_type="list_view", entity_id=view.id,
                 summary=f"Created list view {view.name}", actor_id=svc.user_id, meta=svc.request_meta)
    svc.db.commit()
    return _view_out(view, svc)


def _editable_view(svc: RecordService, api_name: str, view_id: uuid.UUID) -> ListView:
    view = _view(svc, api_name, view_id)
    if not (view.owner_id == svc.user_id or (view.owner_id is None and svc.policy.has(SystemPermission.CUSTOMIZE_APPLICATION))
            or svc.policy.is_system_admin):
        raise PermissionDeniedError("You can't change this list view.")
    return view


@router.put("/list-views/{view_id}")
def update_list_view(api_name: str, view_id: uuid.UUID, body: ListViewIn, svc: Records) -> dict[str, Any]:
    view = _editable_view(svc, api_name, view_id)
    _check_view(svc, api_name, body)
    view.name = body.name.strip()
    view.visibility = body.visibility if view.owner_id is not None else "public"
    view.shared_profile_ids = [str(i) for i in body.shared_profile_ids]
    view.shared_role_ids = [str(i) for i in body.shared_role_ids]
    view.scope = body.scope
    view.columns = body.columns
    view.filters = body.filters
    view.sort = [s.model_dump() for s in body.sort]
    view.kanban_field = body.kanban_field
    audit.record(svc.db, action=AuditAction.UPDATE, entity_type="list_view", entity_id=view.id,
                 summary=f"Updated list view {view.name}", actor_id=svc.user_id, meta=svc.request_meta)
    svc.db.commit()
    return _view_out(view, svc)


@router.delete("/list-views/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_list_view(api_name: str, view_id: uuid.UUID, svc: Records) -> Response:
    view = _editable_view(svc, api_name, view_id)
    if view.key is not None:
        raise AppError("Standard list views can't be deleted.", status_code=422)
    svc.db.execute(delete(ListView).where(ListView.id == view.id))
    audit.record(svc.db, action=AuditAction.DELETE, entity_type="list_view", entity_id=view.id,
                 summary=f"Deleted list view {view.name}", actor_id=svc.user_id, meta=svc.request_meta)
    svc.db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/list-views/{view_id}/pin")
def pin_list_view(api_name: str, view_id: uuid.UUID, svc: Records) -> dict[str, Any]:
    _view(svc, api_name, view_id)
    pref = svc.db.get(UserPreference, svc.user_id)
    if pref is None:
        pref = UserPreference(user_id=svc.user_id, data={})
        svc.db.add(pref)
    data = dict(pref.data or {})
    defaults = dict(data.get("default_views") or {})
    defaults[api_name] = str(view_id)
    data["default_views"] = defaults
    pref.data = data
    svc.db.commit()
    return {"default_view_id": str(view_id)}


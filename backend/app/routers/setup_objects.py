"""/setup/objects, /setup/apps: the Object Manager and app configuration (plan v3, sections 4 and 6).

Read: View Setup or Customize Application. Changes: Customize Application.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.deps import AuthContext, DbSession, require
from app.engine import admin
from app.engine.describe import describe_field
from app.engine.indexes import index_statements, schedule_index_ddl
from app.engine.meta import load_registry
from app.engine.records import RecordService
from app.models import App, ObjectDefinition
from app.models.metadata import FIELD_TYPES
from app.security.catalog import SystemPermission
from app.services.audit import RequestMeta

router = APIRouter(prefix="/setup", tags=["setup: objects"])
P = SystemPermission
Reader = Annotated[AuthContext, Depends(require(P.VIEW_SETUP, P.CUSTOMIZE_APPLICATION))]
Customizer = Annotated[AuthContext, Depends(require(P.CUSTOMIZE_APPLICATION))]


class ObjectIn(BaseModel):
    label: str | None = Field(default=None, max_length=80)
    plural_label: str | None = Field(default=None, max_length=80)
    api_name: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    icon: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    name_field_type: str | None = None
    name_label: str | None = Field(default=None, max_length=80)
    name_format: str | None = Field(default=None, max_length=60)
    sharing: str | None = None
    track_history: bool | None = None
    allow_activities: bool | None = None
    allow_files: bool | None = None
    allow_notes: bool | None = None
    searchable: bool | None = None
    allow_reports: bool | None = None
    show_in_portal: bool | None = None
    allow_queues: bool | None = None
    page_layout: list[dict[str, Any]] | None = None
    compact_layout: list[str] | None = None
    related_lists: list[dict[str, Any]] | None = None
    list_columns: list[str] | None = None


class FieldIn(BaseModel):
    label: str | None = Field(default=None, max_length=80)
    api_name: str | None = Field(default=None, max_length=80)
    type: str | None = None
    help_text: str | None = Field(default=None, max_length=1000)
    required: bool | None = None
    is_unique: bool | None = None
    external_id: bool | None = None
    indexed: bool | None = None
    searchable: bool | None = None
    track_history: bool | None = None
    default_access: str | None = None
    default_value: Any = None
    options: dict[str, Any] | None = None


class AppIn(BaseModel):
    key: str | None = Field(default=None, max_length=60)
    label: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    icon: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    sort_order: int | None = None
    is_active: bool | None = None
    tabs: list[dict[str, Any]] = Field(default_factory=list)
    profile_ids: list[uuid.UUID] = Field(default_factory=list)


def _meta(request: Request) -> RequestMeta:
    return RequestMeta.from_request(request)


def _object_out(db: DbSession, auth: AuthContext, api_name: str) -> dict[str, Any]:
    obj = admin.get_object(db, api_name)
    registry = load_registry(db)
    meta = registry.get(api_name)
    svc = RecordService.as_system(db, auth.user.id)
    fields = [describe_field(svc, meta, f) for f in meta.fields.values()]
    deleted = [
        {"api_name": f.api_name, "label": f.label, "type": f.type, "deleted_at": f.deleted_at}
        for f in obj.fields
        if f.deleted_at is not None
    ]
    return {
        "id": str(obj.id),
        "api_name": obj.api_name,
        "label": obj.label,
        "plural_label": obj.plural_label,
        "description": obj.description,
        "icon": obj.icon,
        "color": obj.color,
        "is_custom": obj.is_custom,
        "pack_key": obj.pack_key,
        "name_field_type": obj.name_field_type,
        "name_label": obj.name_label,
        "name_format": obj.name_format,
        **{
            f: getattr(obj, f)
            for f in (
                "track_history",
                "allow_activities",
                "allow_files",
                "allow_notes",
                "searchable",
                "allow_reports",
                "show_in_portal",
                "allow_queues",
                "is_detail_only",
            )
        },
        "page_layout": obj.page_layout,
        "compact_layout": obj.compact_layout,
        "related_lists": obj.related_lists,
        "list_columns": obj.list_columns,
        "fields": fields,
        "deleted_fields": deleted,
        "field_types": list(FIELD_TYPES),
        "updated_at": obj.updated_at,
    }


@router.get("/objects")
def list_objects(db: DbSession, _: Reader) -> list[dict[str, Any]]:
    rows = db.scalars(select(ObjectDefinition).order_by(ObjectDefinition.label)).all()
    out = []
    for o in rows:
        out.append(
            {
                "api_name": o.api_name,
                "label": o.label,
                "plural_label": o.plural_label,
                "icon": o.icon,
                "color": o.color,
                "is_custom": o.is_custom,
                "pack_key": o.pack_key,
                "description": o.description,
                "field_count": sum(1 for f in o.fields if f.deleted_at is None),
                "updated_at": o.updated_at,
            }
        )
    return out


@router.post("/objects", status_code=status.HTTP_201_CREATED)
def create_object(body: ObjectIn, request: Request, db: DbSession, auth: Customizer) -> dict[str, Any]:
    obj = admin.create_object(db, auth.user.id, body.model_dump(exclude_none=True), _meta(request))
    db.commit()
    return _object_out(db, auth, obj.api_name)


@router.get("/objects/{api_name}")
def get_object(api_name: str, db: DbSession, auth: Reader) -> dict[str, Any]:
    return _object_out(db, auth, api_name)


@router.patch("/objects/{api_name}")
def update_object(
    api_name: str, body: ObjectIn, request: Request, db: DbSession, auth: Customizer
) -> dict[str, Any]:
    admin.update_object(db, auth.user.id, api_name, body.model_dump(exclude_none=True), _meta(request))
    db.commit()
    return _object_out(db, auth, api_name)


@router.delete("/objects/{api_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_object(api_name: str, request: Request, db: DbSession, auth: Customizer) -> Response:
    admin.delete_object(db, auth.user.id, api_name, _meta(request))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/objects/{api_name}/fields", status_code=status.HTTP_201_CREATED)
def create_field(
    api_name: str, body: FieldIn, request: Request, db: DbSession, auth: Customizer
) -> dict[str, Any]:
    field = admin.create_field(
        db, auth.user.id, api_name, body.model_dump(exclude_unset=True), _meta(request)
    )
    db.commit()
    meta = load_registry(db).get(api_name)
    schedule_index_ddl(index_statements(meta, meta.field(field.api_name), concurrently=True))
    return _object_out(db, auth, api_name)


@router.patch("/objects/{api_name}/fields/{field_api}")
def update_field(
    api_name: str, field_api: str, body: FieldIn, request: Request, db: DbSession, auth: Customizer
) -> dict[str, Any]:
    _, ddl = admin.update_field(
        db, auth.user.id, api_name, field_api, body.model_dump(exclude_unset=True), _meta(request)
    )
    db.commit()
    schedule_index_ddl(ddl)
    return _object_out(db, auth, api_name)


@router.delete("/objects/{api_name}/fields/{field_api}")
def delete_field(
    api_name: str, field_api: str, request: Request, db: DbSession, auth: Customizer
) -> dict[str, Any]:
    ddl = admin.delete_field(db, auth.user.id, api_name, field_api, _meta(request))
    db.commit()
    schedule_index_ddl(ddl)
    return _object_out(db, auth, api_name)


@router.post("/objects/{api_name}/fields/{field_api}/restore")
def restore_field(
    api_name: str, field_api: str, request: Request, db: DbSession, auth: Customizer
) -> dict[str, Any]:
    admin.restore_field(db, auth.user.id, api_name, field_api, _meta(request))
    db.commit()
    return _object_out(db, auth, api_name)


def _app_out(app: App) -> dict[str, Any]:
    return {
        "id": str(app.id),
        "key": app.key,
        "label": app.label,
        "description": app.description,
        "icon": app.icon,
        "color": app.color,
        "sort_order": app.sort_order,
        "is_active": app.is_active,
        "tabs": app.tabs,
        "profile_ids": app.profile_ids,
        "pack_key": app.pack_key,
    }


@router.get("/apps")
def list_apps(db: DbSession, _: Reader) -> list[dict[str, Any]]:
    return [_app_out(a) for a in db.scalars(select(App).order_by(App.sort_order, App.label))]


@router.post("/apps", status_code=status.HTTP_201_CREATED)
def create_app(body: AppIn, request: Request, db: DbSession, auth: Customizer) -> dict[str, Any]:
    app = admin.save_app(db, auth.user.id, body.model_dump(exclude_none=True), _meta(request))
    db.commit()
    return _app_out(app)


@router.put("/apps/{app_id}")
def update_app(
    app_id: uuid.UUID, body: AppIn, request: Request, db: DbSession, auth: Customizer
) -> dict[str, Any]:
    app = admin.save_app(db, auth.user.id, body.model_dump(exclude_none=True), _meta(request), app_id)
    db.commit()
    return _app_out(app)


@router.delete("/apps/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_app(app_id: uuid.UUID, request: Request, db: DbSession, auth: Customizer) -> Response:
    admin.delete_app(db, auth.user.id, app_id, _meta(request))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

"""Cross-object workspace endpoints: global search, recent items, recycle bin, notifications,
preferences, calendar and files."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from app.core.errors import AppError, NotFoundError
from app.engine.deps import Records
from app.engine.describe import readable_objects
from app.engine.records import RecordService
from app.models import Notification, RecentItem, Record, StoredFile, UserPreference
from app.services import audit
from app.services.audit import AuditAction

router = APIRouter(tags=["workspace"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".com", ".scr", ".js", ".vbs", ".msi", ".ps1", ".jar", ".dll"}


@router.get("/search")
def search(
    svc: Records,
    q: Annotated[str, Query(min_length=1, max_length=100)],
    objects: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=25)] = 5,
) -> dict[str, Any]:
    """Global search over every searchable object the user can read, grouped by object."""
    wanted = {o.strip() for o in objects.split(",")} if objects else None
    groups = []
    for meta in readable_objects(svc):
        if not meta.searchable or meta.is_detail_only or (wanted and meta.api_name not in wanted):
            continue
        result = svc.query(
            meta.api_name, search=q, limit=limit, sort=[{"field": "updated_at", "direction": "desc"}]
        )
        if not result.records:
            continue
        cols = meta.compact_layout[:3]
        groups.append(
            {
                "object": meta.api_name,
                "label": meta.plural_label,
                "icon": meta.icon,
                "color": meta.color,
                "total": result.total,
                "columns": cols,
                "items": svc.serialize_many(meta.api_name, result.records, columns=cols, with_access=False),
            }
        )
    return {"query": q, "groups": groups}


@router.get("/me/recent")
def recent(
    svc: Records, limit: Annotated[int, Query(ge=1, le=50)] = 15, object_api_name: str | None = None
) -> list[dict[str, Any]]:
    stmt = (
        select(Record, RecentItem.viewed_at)
        .join(RecentItem, RecentItem.record_id == Record.id)
        .where(RecentItem.user_id == svc.user_id, Record.is_deleted.is_(False))
        .order_by(RecentItem.viewed_at.desc())
        .limit(limit * 3)
    )
    if object_api_name:
        stmt = stmt.where(Record.object_api_name == object_api_name)
    out = []
    for record, viewed_at in svc.db.execute(stmt).all():
        meta = svc.registry.objects.get(record.object_api_name)
        if meta is None or not svc.policy.object(meta.api_name).read:
            continue
        if not svc.visible_ids(meta.api_name, [record.id]):
            continue
        out.append(
            {
                "id": str(record.id),
                "name": record.name,
                "object": meta.api_name,
                "object_label": meta.label,
                "icon": meta.icon,
                "color": meta.color,
                "viewed_at": viewed_at,
            }
        )
        if len(out) >= limit:
            break
    return out


@router.get("/recycle-bin")
def recycle_bin(svc: Records, limit: Annotated[int, Query(ge=1, le=200)] = 100) -> list[dict[str, Any]]:
    """Records the user deleted (all deleted records for objects where they have Modify All)."""
    out: list[dict[str, Any]] = []
    for meta in readable_objects(svc):
        access = svc.policy.object(meta.api_name)
        if not access.delete:
            continue
        stmt = select(Record).where(Record.object_api_name == meta.api_name, Record.is_deleted.is_(True))
        if not access.modify_all:
            stmt = stmt.where(Record.deleted_by_id == svc.user_id)
        for r in svc.db.scalars(stmt.order_by(Record.deleted_at.desc()).limit(limit)):
            out.append(
                {
                    "id": str(r.id),
                    "name": r.name,
                    "object": meta.api_name,
                    "object_label": meta.label,
                    "deleted_at": r.deleted_at,
                    "purge_at": (r.deleted_at or datetime.now(UTC)) + timedelta(days=30),
                }
            )
    out.sort(key=lambda x: x["deleted_at"], reverse=True)
    return out[:limit]


@router.get("/me/notifications")
def notifications(svc: Records, unread_only: bool = False) -> dict[str, Any]:
    stmt = select(Notification).where(Notification.user_id == svc.user_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    rows = svc.db.scalars(stmt.order_by(Notification.created_at.desc()).limit(50)).all()
    unread = int(
        svc.db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == svc.user_id, Notification.read_at.is_(None))
        )
        or 0
    )
    return {
        "unread": unread,
        "items": [
            {
                "id": str(n.id),
                "title": n.title,
                "body": n.body,
                "link": n.link,
                "read": n.read_at is not None,
                "created_at": n.created_at,
            }
            for n in rows
        ],
    }


@router.post("/me/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
def read_all(svc: Records) -> Response:
    svc.db.execute(
        update(Notification)
        .where(Notification.user_id == svc.user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    svc.db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def read_one(notification_id: uuid.UUID, svc: Records) -> Response:
    svc.db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == svc.user_id)
        .values(read_at=datetime.now(UTC))
    )
    svc.db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class PreferencesIn(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


@router.get("/me/preferences")
def get_preferences(svc: Records) -> dict[str, Any]:
    pref = svc.db.get(UserPreference, svc.user_id)
    return dict(pref.data) if pref else {}


@router.patch("/me/preferences")
def patch_preferences(body: PreferencesIn, svc: Records) -> dict[str, Any]:
    allowed = {"default_views", "pinned", "rail_collapsed", "home_app", "list_density", "recent_apps"}
    unknown = set(body.data) - allowed
    if unknown:
        raise AppError(f"Unknown preference {sorted(unknown)[0]!r}.", status_code=422)
    pref = svc.db.get(UserPreference, svc.user_id)
    if pref is None:
        pref = UserPreference(user_id=svc.user_id, data={})
        svc.db.add(pref)
    pref.data = {**(pref.data or {}), **body.data}
    svc.db.commit()
    return dict(pref.data)


@router.get("/calendar")
def calendar(
    svc: Records,
    start: datetime,
    end: datetime,
    mine: bool = True,
) -> dict[str, Any]:
    """Events overlapping [start, end) and tasks due in the range."""
    if end <= start or end - start > timedelta(days=62):
        raise AppError("Choose a range of at most 62 days.", status_code=422)
    events_filter = {
        "logic": "and",
        "conditions": [
            {"field": "start_at", "op": "lt", "value": end.isoformat()},
            {"field": "end_at", "op": "gte", "value": start.isoformat()},
        ],
    }
    scope = "mine" if mine else "all"
    out: dict[str, Any] = {"events": [], "tasks": []}
    if svc.policy.object("event").read:
        res = svc.query(
            "event",
            filters=events_filter,
            scope=scope,
            limit=200,
            sort=[{"field": "start_at", "direction": "asc"}],
        )
        out["events"] = svc.serialize_many("event", res.records)
    if svc.policy.object("task").read:
        tasks_filter = {
            "logic": "and",
            "conditions": [
                {"field": "due_date", "op": "gte", "value": start.date().isoformat()},
                {"field": "due_date", "op": "lt", "value": end.date().isoformat()},
            ],
        }
        res = svc.query(
            "task",
            filters=tasks_filter,
            scope=scope,
            limit=200,
            sort=[{"field": "due_date", "direction": "asc"}],
        )
        out["tasks"] = svc.serialize_many("task", res.records)
    return out


# ---------------------------------------------------------------- files


def _scan(content: bytes) -> str:
    """Malware-scan hook (plan v3, section 14). Replace with a ClamAV/provider call in production.
    The EICAR test signature is always rejected so the hook can be tested end-to-end."""
    if b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in content:
        return "infected"
    return "clean"


def store_file(
    svc: RecordService,
    content: bytes,
    *,
    file_name: str,
    content_type: str,
    related_to: uuid.UUID | None,
    is_public: bool = False,
    description: str | None = None,
) -> Record:
    if not content:
        raise AppError("The file is empty.", status_code=422)
    if len(content) > MAX_UPLOAD_BYTES:
        raise AppError("Files can be at most 25 MB.", code="payload_too_large", status_code=413)
    name = file_name.strip().replace("\\", "/").split("/")[-1][:200] or "file"
    if any(name.lower().endswith(ext) for ext in BLOCKED_EXTENSIONS):
        raise AppError("This file type isn't allowed.", code="file_type_blocked", status_code=415)
    if _scan(content) != "clean":
        raise AppError("The file failed the malware scan.", code="malware_detected", status_code=422)
    stored = StoredFile(
        storage="db",
        content=content,
        content_type=content_type[:120] or "application/octet-stream",
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        created_by_id=svc.user_id,
    )
    svc.db.add(stored)
    svc.db.flush()
    values: dict[str, Any] = {"name": name, "is_public": is_public}
    if related_to is not None:
        values["related_to"] = str(related_to)
    if description:
        values["description"] = description
    record = svc.create("file", values)
    sys_svc = svc.elevated()
    record.data = {
        **record.data,
        "stored_file_id": str(stored.id),
        "content_type": stored.content_type,
        "size": stored.size,
    }
    sys_svc.db.flush()
    return record


@router.post("/files", status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    svc: Records,
    x_file_name: Annotated[str, Header(max_length=255)],
    related_to: uuid.UUID | None = None,
    is_public: bool = False,
    content_type: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Upload raw bytes (body) with the file name in the X-File-Name header."""
    content = await request.body()
    record = store_file(
        svc,
        content,
        file_name=x_file_name,
        content_type=content_type or "application/octet-stream",
        related_to=related_to,
        is_public=is_public,
    )
    svc.db.commit()
    return svc.serialize(record)


def file_response(svc: RecordService, record_id: uuid.UUID, *, inline: bool) -> Response:
    record = svc.get("file", record_id)
    stored_id = record.data.get("stored_file_id")
    stored = svc.db.get(StoredFile, uuid.UUID(str(stored_id))) if stored_id else None
    if stored is None or stored.content is None:
        raise NotFoundError("File content not found.")
    audit.record(
        svc.db,
        action=AuditAction.DOWNLOAD,
        entity_type="record:file",
        entity_id=record.id,
        summary=f"Downloaded {record.name}",
        actor_id=svc.user_id,
        meta=svc.request_meta,
    )
    svc.db.commit()
    safe = record.name.replace('"', "").replace("\r", "").replace("\n", "")
    disposition = (
        "inline"
        if inline and stored.content_type in ("application/pdf", "image/png", "image/jpeg", "image/gif")
        else "attachment"
    )
    return Response(
        content=stored.content,
        media_type=stored.content_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{safe}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/files/{record_id}/content")
def download_file(record_id: uuid.UUID, svc: Records, inline: bool = False) -> Response:
    return file_response(svc, record_id, inline=inline)

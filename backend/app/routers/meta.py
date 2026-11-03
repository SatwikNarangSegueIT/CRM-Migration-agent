"""/meta: what the signed-in user may see (objects, fields, apps), plus pickers for users and queues."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from app.db.session import escape_like
from app.engine.deps import Records
from app.engine.describe import describe_object, object_summary, readable_objects, visible_apps
from app.models import Profile, Queue, Setting, User

router = APIRouter(prefix="/meta", tags=["metadata"])


@router.get("/objects")
def list_objects(svc: Records) -> list[dict[str, Any]]:
    return [object_summary(svc, m) for m in readable_objects(svc)]


@router.get("/objects/{api_name}")
def get_object(api_name: str, svc: Records) -> dict[str, Any]:
    return describe_object(svc, svc.object(api_name))


@router.get("/apps")
def apps(svc: Records) -> list[dict[str, Any]]:
    return visible_apps(svc)


@router.get("/users")
def users(
    svc: Records,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[dict[str, Any]]:
    """Active staff users, for owner pickers and assignment."""
    stmt = (
        select(User.id, User.name, User.email, User.title)
        .join(Profile, Profile.id == User.profile_id)
        .where(User.is_active.is_(True), Profile.is_portal.is_(False))
    )
    if q:
        pattern = f"%{escape_like(q.strip().lower())}%"
        stmt = stmt.where(
            or_(func.lower(User.name).like(pattern, escape="\\"), User.email.like(pattern, escape="\\"))
        )
    rows = svc.db.execute(stmt.order_by(func.lower(User.name)).limit(limit)).all()
    return [{"id": str(r.id), "name": r.name, "email": r.email, "title": r.title} for r in rows]


@router.get("/queues")
def queues(svc: Records, object_api_name: str | None = None) -> list[dict[str, Any]]:
    rows = svc.db.scalars(select(Queue).order_by(Queue.name)).all()
    return [
        {"id": str(q.id), "name": q.name, "object_api_names": q.object_api_names}
        for q in rows
        if object_api_name is None or object_api_name in (q.object_api_names or [])
    ]


@router.get("/settings")
def settings(svc: Records) -> dict[str, Any]:
    """Organisation settings that every staff user needs (branding, locale, currency)."""
    rows = svc.db.scalars(select(Setting).where(Setting.key.in_(("branding", "locale", "company")))).all()
    return {r.key: r.value for r in rows}

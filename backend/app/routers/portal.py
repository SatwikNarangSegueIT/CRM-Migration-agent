"""/portal: the customer portal (plan v3, section 8) and portal-user administration for staff.

Portal users only reach these endpoints, and the record engine limits them to records tied to their
own contact or account; staff never use portal APIs.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.auth.deps import AuthContext, DbSession, require
from app.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.engine import hooks
from app.engine.deps import PortalRecords, Records
from app.engine.describe import describe_object
from app.engine.records import RecordService
from app.models import Profile, Record, User
from app.routers.workspace import file_response, store_file
from app.security.catalog import SystemPermission
from app.services import audit
from app.services.audit import AuditAction, RequestMeta
from app.services.auth import issue_invitation, revoke_sessions
from app.services.email import app_link, queue_email
from app.services.pdf import render_document
from app.services.settings import get_setting
from app.tenancy import qualify_token

router = APIRouter(prefix="/portal", tags=["portal"])
staff_router = APIRouter(prefix="/portal-users", tags=["portal users"])

# What a client follows in each profession's portal (the invitation e-mail says so).
PORTAL_WORK = {
    "legal": "your matters and court dates",
    "migration": "your visa matters and document checklist",
    "accounting": "your engagements and document requests",
    "lending": "your loan applications",
}
PortalAdmin = Annotated[AuthContext, Depends(require(SystemPermission.MANAGE_PORTAL_USERS))]


class CaseIn(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=32000)
    priority: str | None = None
    type: str | None = None


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=32000)


def _portal_objects(svc: RecordService) -> list[dict[str, Any]]:
    out = []
    for meta in svc.registry.objects.values():
        if not meta.show_in_portal or meta.is_detail_only or meta.api_name in ("note", "file", "payment"):
            continue
        if meta.pack_key and meta.pack_key not in svc.enabled_packs:
            continue
        if svc.policy.object(meta.api_name).read:
            out.append(
                {
                    "api_name": meta.api_name,
                    "label": meta.label,
                    "plural_label": meta.plural_label,
                    "icon": meta.icon,
                    "can_create": svc.policy.object(meta.api_name).create,
                }
            )
    return sorted(out, key=lambda o: o["plural_label"])


@router.get("/me")
def me(svc: PortalRecords) -> dict[str, Any]:
    contact = account = None
    if svc.sharing.contact_id:
        c = svc.db.get(Record, svc.sharing.contact_id)
        if c is not None:
            contact = {
                "id": str(c.id),
                "name": c.name,
                "email": c.data.get("email"),
                "phone": c.data.get("phone"),
            }
    if svc.sharing.account_id:
        a = svc.db.get(Record, svc.sharing.account_id)
        if a is not None:
            account = {"id": str(a.id), "name": a.name}
    objects = _portal_objects(svc)
    # Every card on the portal home shows how many records it holds (each is one indexed count).
    counts = {o["api_name"]: svc.query(o["api_name"], limit=1).total for o in objects}
    branding = get_setting(svc.db, "branding") or {}
    return {
        "contact": contact,
        "account": account,
        "objects": objects,
        "counts": counts,
        "branding": branding,
    }


@router.get("/objects/{api_name}/describe")
def describe(api_name: str, svc: PortalRecords) -> dict[str, Any]:
    """Field labels, types and layout for rendering portal records. Field-level security applies;
    staff-only details (list views, actions, related-list configuration) are left out."""
    meta = svc.object(api_name)
    if not meta.show_in_portal or not svc.policy.object(api_name).read:
        raise NotFoundError("Not found.")
    full = describe_object(svc, meta)
    keep = (
        "api_name",
        "label",
        "plural_label",
        "icon",
        "color",
        "name_label",
        "fields",
        "page_layout",
        "compact_layout",
        "list_columns",
        "path_field",
    )
    return {k: full[k] for k in keep if k in full}


@router.get("/objects/{api_name}/records")
def list_records(
    api_name: str,
    svc: PortalRecords,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> dict[str, Any]:
    meta = svc.object(api_name)
    if not meta.show_in_portal:
        raise NotFoundError("Not found.")
    res = svc.query(
        api_name, search=q, cursor=cursor, limit=50, sort=[{"field": "created_at", "direction": "desc"}]
    )
    return {
        "items": svc.serialize_many(api_name, res.records),
        "next_cursor": res.next_cursor,
        "total": res.total,
    }


@router.get("/objects/{api_name}/records/{record_id}")
def get_record(api_name: str, record_id: uuid.UUID, svc: PortalRecords) -> dict[str, Any]:
    meta = svc.object(api_name)
    if not meta.show_in_portal:
        raise NotFoundError("Not found.")
    record = svc.get(api_name, record_id)
    out = svc.serialize(record)
    out["actions"] = [
        {"name": a.name, "label": a.label}
        for a in hooks.actions_for(api_name, svc.enabled_packs)
        if a.portal and (a.visible is None or a.visible(record))
    ]
    timeline: dict[str, Any] = {}
    for child in ("note", "file"):
        child_meta = svc.registry.objects.get(child)
        if (
            child_meta is None
            or api_name not in child_meta.fields["related_to"].targets
            or not svc.policy.object(child).read
        ):
            continue
        res = svc.related(
            api_name,
            record_id,
            child,
            "related_to",
            limit=100,
            sort=[{"field": "created_at", "direction": "asc"}],
        )
        timeline[child] = svc.serialize_many(child, res.records)
    out["timeline"] = timeline
    related = []
    for rl in meta.related_lists:
        child_meta = svc.registry.objects.get(rl["object"])
        if (
            child_meta is None
            or not child_meta.show_in_portal
            or not svc.policy.object(child_meta.api_name).read
        ):
            continue
        res = svc.related(
            api_name,
            record_id,
            child_meta.api_name,
            rl["field"],
            limit=100,
            sort=[{"field": "created_at", "direction": "asc"}],
        )
        related.append(
            {
                "object": child_meta.api_name,
                "label": rl.get("label") or child_meta.plural_label,
                "columns": rl.get("columns", ["name"]),
                "items": svc.serialize_many(child_meta.api_name, res.records),
            }
        )
    out["related"] = related
    return out


@router.post("/objects/{api_name}/records/{record_id}/actions/{action_name}")
def run_action(
    api_name: str,
    record_id: uuid.UUID,
    action_name: str,
    svc: PortalRecords,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    action = hooks.get_action(api_name, action_name)
    if action is None or not action.portal or (action.pack_key and action.pack_key not in svc.enabled_packs):
        raise NotFoundError("Action not found.")
    record = svc.get(api_name, record_id, lock=True)
    hooks.check_available(action, record)
    if action.guard is not None:
        message = action.guard(svc, record)
        if message:
            raise PermissionDeniedError(message)
    result = action.handler(svc, record, payload or {})
    svc.db.commit()
    return result


@router.post("/cases", status_code=status.HTTP_201_CREATED)
def create_case(body: CaseIn, svc: PortalRecords) -> dict[str, Any]:
    values: dict[str, Any] = {"subject": body.subject, "description": body.description}
    if body.priority in ("Low", "Medium", "High"):
        values["priority"] = body.priority
    if body.type:
        values["type"] = body.type
    created = svc.create("case", {k: v for k, v in values.items() if v is not None})
    svc.db.commit()
    return svc.serialize(created)


@router.post("/objects/{api_name}/records/{record_id}/comments", status_code=status.HTTP_201_CREATED)
def add_comment(api_name: str, record_id: uuid.UUID, body: CommentIn, svc: PortalRecords) -> dict[str, Any]:
    record = svc.get(api_name, record_id)
    note = svc.create(
        "note",
        {
            "name": f"Comment from {svc.db.get(User, svc.user_id).name if svc.user_id else 'customer'}"[:255],  # type: ignore[union-attr]
            "body": body.body,
            "related_to": str(record.id),
            "is_public": True,
        },
    )
    if api_name == "case" and record.data.get("status") in ("Waiting on Customer", "Closed"):
        svc.elevated().update("case", record.id, {"status": "Working"}, record=record)
    svc.db.commit()
    return svc.serialize(note)


@router.post("/objects/{api_name}/records/{record_id}/files", status_code=status.HTTP_201_CREATED)
async def upload(
    api_name: str,
    record_id: uuid.UUID,
    request: Request,
    svc: PortalRecords,
    x_file_name: Annotated[str, Header(max_length=255)],
    content_type: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    record = svc.get(api_name, record_id)
    content = await request.body()
    file = store_file(
        svc,
        content,
        file_name=x_file_name,
        content_type=content_type or "application/octet-stream",
        related_to=record.id,
        is_public=True,
    )
    svc.db.commit()
    return svc.serialize(file)


@router.get("/files/{record_id}/content")
def download(record_id: uuid.UUID, svc: PortalRecords, inline: bool = False) -> Response:
    return file_response(svc, record_id, inline=inline)


@router.get("/objects/{api_name}/records/{record_id}/pdf")
def pdf(api_name: str, record_id: uuid.UUID, svc: PortalRecords) -> Response:
    if api_name not in ("invoice", "quote"):
        raise NotFoundError("Not found.")
    record = svc.get(api_name, record_id)
    if record.data.get("status") == "Draft":
        raise NotFoundError("Not found.")
    return Response(
        render_document(svc, record),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{record.name}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )


# ---------------------------------------------------------------- staff: portal users


def _portal_profile(db: DbSession) -> Profile:
    profile = db.scalar(select(Profile).where(Profile.key == "customer_portal"))
    if profile is None:
        raise AppError("The Customer Portal User profile is missing.", status_code=500)
    return profile


def _portal_user_out(u: User) -> dict[str, Any]:
    return {
        "id": str(u.id),
        "name": u.name,
        "email": u.email,
        "is_active": u.is_active,
        "contact_id": str(u.contact_id) if u.contact_id else None,
        "last_login_at": u.last_login_at,
        "has_password": u.has_password,
        "created_at": u.created_at,
    }


@staff_router.get("")
def list_portal_users(db: DbSession, _: PortalAdmin) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(User)
        .join(Profile, Profile.id == User.profile_id)
        .where(Profile.is_portal.is_(True))
        .order_by(func.lower(User.name))
    ).all()
    return [_portal_user_out(u) for u in rows]


@staff_router.post("/invite/{contact_id}", status_code=status.HTTP_201_CREATED)
def invite(contact_id: uuid.UUID, request: Request, svc: Records, auth: PortalAdmin) -> dict[str, Any]:
    contact = svc.get("contact", contact_id)
    email = (contact.data.get("email") or "").strip().lower()
    if not email:
        raise AppError(
            "Add an e-mail address to the contact first.", status_code=422, fields={"email": "Required"}
        )
    if svc.db.scalar(select(User.id).where(User.email == email)) is not None:
        raise ConflictError("A user with this e-mail already exists.", fields={"email": "Already in use"})
    user = User(
        email=email,
        name=contact.name,
        profile_id=_portal_profile(svc.db).id,
        contact_id=contact.id,
        is_active=True,
    )
    svc.db.add(user)
    svc.db.flush()
    token = issue_invitation(svc.db, user)
    audit.record(
        svc.db,
        action=AuditAction.INVITATION_SENT,
        entity_type="user",
        entity_id=user.id,
        summary=f"Invited {contact.name} to the customer portal",
        actor_id=auth.user.id,
        meta=RequestMeta.from_request(request),
    )
    svc.db.commit()
    brand = (get_setting(svc.db, "branding") or {}).get("name", "our customer portal")
    domain = (get_setting(svc.db, "workspace") or {}).get("domain")
    work = PORTAL_WORK.get(str(domain), "your cases")
    portal = "client portal" if domain in PORTAL_WORK else "customer portal"
    queue_email(
        user.email,
        f"Your {brand} portal access",
        f"Hello {user.name},\n\n{auth.user.name} has invited you to the {brand} {portal}, where you can "
        f"follow {work}, read and sign documents, upload what we ask for and see your invoices.\n"
        "Set your password with this link (single use):\n\n"
        f"{app_link('/accept-invitation#token=' + qualify_token(svc.db, token))}\n",
    )
    return _portal_user_out(user)


@staff_router.post("/{user_id}/deactivate")
def deactivate(user_id: uuid.UUID, request: Request, db: DbSession, auth: PortalAdmin) -> dict[str, Any]:
    user = db.get(User, user_id)
    if user is None or not user.profile.is_portal:
        raise NotFoundError("Portal user not found.")
    user.is_active = False
    user.updated_at = func.now()
    revoke_sessions(db, user.id)
    audit.record(
        db,
        action=AuditAction.UPDATE,
        entity_type="user",
        entity_id=user.id,
        summary=f"Deactivated portal user {user.email}",
        actor_id=auth.user.id,
        changes={"is_active": {"from": True, "to": False}},
        meta=RequestMeta.from_request(request),
    )
    db.commit()
    return _portal_user_out(user)


@staff_router.post("/{user_id}/activate")
def activate(user_id: uuid.UUID, request: Request, db: DbSession, auth: PortalAdmin) -> dict[str, Any]:
    user = db.get(User, user_id)
    if user is None or not user.profile.is_portal:
        raise NotFoundError("Portal user not found.")
    user.is_active = True
    user.updated_at = func.now()
    audit.record(
        db,
        action=AuditAction.UPDATE,
        entity_type="user",
        entity_id=user.id,
        summary=f"Reactivated portal user {user.email}",
        actor_id=auth.user.id,
        changes={"is_active": {"from": False, "to": True}},
        meta=RequestMeta.from_request(request),
    )
    db.commit()
    return _portal_user_out(user)

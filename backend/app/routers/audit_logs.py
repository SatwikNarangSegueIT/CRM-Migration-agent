"""/admin/audit-logs: read-only audit trail (audit.read)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.deps import AuthContext, DbSession, require
from app.schemas.audit import AuditActor, AuditLogOut
from app.schemas.common import Page, PageParams
from app.security.catalog import SystemPermission
from app.services.audit_query import list_audit_logs

router = APIRouter(prefix="/admin/audit-logs", tags=["admin: audit"])


@router.get("", response_model=Page[AuditLogOut])
def audit_logs(
    db: DbSession,
    _: Annotated[AuthContext, Depends(require(SystemPermission.VIEW_AUDIT_LOG))],
    params: Annotated[PageParams, Depends()],
    user_id: uuid.UUID | None = None,
    action: Annotated[str | None, Query(max_length=40)] = None,
    entity_type: Annotated[str | None, Query(max_length=40)] = None,
    entity_id: Annotated[str | None, Query(max_length=64)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Page[AuditLogOut]:
    rows, total = list_audit_logs(
        db,
        params,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
    )
    items = [
        AuditLogOut(
            id=r.id,
            created_at=r.created_at,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            summary=r.summary,
            changes=r.changes,
            ip_address=r.ip_address,
            user_agent=r.user_agent,
            request_id=r.request_id,
            actor=AuditActor(id=r.user.id, name=r.user.name, email=r.user.email) if r.user else None,
        )
        for r in rows
    ]
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)

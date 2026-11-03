"""FastAPI dependencies that bind the record engine to the signed-in user."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.auth.deps import Auth, StaffAuth
from app.core.errors import PermissionDeniedError
from app.db.session import get_db
from app.engine.records import RecordService
from app.services.audit import RequestMeta
from sqlalchemy.orm import Session


def get_record_service(request: Request, auth: StaffAuth, db: Annotated[Session, Depends(get_db)]) -> RecordService:
    return RecordService.for_user(db, auth.user, auth.policy, RequestMeta.from_request(request))


def get_portal_record_service(request: Request, auth: Auth, db: Annotated[Session, Depends(get_db)]) -> RecordService:
    if auth.is_staff:
        raise PermissionDeniedError("The customer portal is for customers only.")
    return RecordService.for_user(db, auth.user, auth.policy, RequestMeta.from_request(request))


Records = Annotated[RecordService, Depends(get_record_service)]
PortalRecords = Annotated[RecordService, Depends(get_portal_record_service)]

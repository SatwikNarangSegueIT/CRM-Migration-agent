"""/privacy: subject-access export and erasure of a person (plan v3, section 14).

Both need Manage Users: they reveal or remove every field, including ones hidden by field-level security.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.deps import AuthContext, require
from app.engine.deps import Records
from app.security.catalog import SystemPermission
from app.services import privacy

router = APIRouter(prefix="/privacy", tags=["privacy"])
Officer = Annotated[AuthContext, Depends(require(SystemPermission.MANAGE_USERS))]


class EraseIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    confirm: str = Field(description="Type ERASE to confirm.")


@router.get("/{object_api_name}/{record_id}/export")
def export(object_api_name: str, record_id: uuid.UUID, svc: Records, _: Officer) -> dict[str, Any]:
    out = privacy.export_person(svc, object_api_name, record_id)
    svc.db.commit()
    return out


@router.post("/{object_api_name}/{record_id}/erase")
def erase(
    object_api_name: str, record_id: uuid.UUID, body: EraseIn, svc: Records, _: Officer
) -> dict[str, Any]:
    if body.confirm != "ERASE":
        raise privacy.PrivacyError("Type ERASE to confirm.", fields={"confirm": "Type ERASE"})
    record = privacy.erase_person(svc, object_api_name, record_id, body.reason)
    svc.db.commit()
    return svc.serialize(record)

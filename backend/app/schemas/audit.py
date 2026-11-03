from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditActor(BaseModel):
    id: uuid.UUID
    name: str
    email: str


class AuditLogOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    action: str
    entity_type: str
    entity_id: str | None
    summary: str
    changes: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    request_id: str | None
    actor: AuditActor | None

"""Audit trail helpers. Entries are written in the same transaction as the change they describe."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.request_context import get_request_id
from app.models import AuditLog

# Never written into audit "changes".
SENSITIVE_FIELDS = frozenset({"password_hash", "mfa_secret_encrypted", "mfa_last_used_step", "token_hash"})


class AuditAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    MFA_ENABLED = "MFA_ENABLED"
    MFA_FAILED = "MFA_FAILED"
    MFA_RESET = "MFA_RESET"
    RECOVERY_CODE_USED = "RECOVERY_CODE_USED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"  # noqa: S105 - action name
    PASSWORD_RESET_REQUESTED = "PASSWORD_RESET_REQUESTED"  # noqa: S105 - action name
    PASSWORD_RESET = "PASSWORD_RESET"  # noqa: S105 - action name
    INVITATION_SENT = "INVITATION_SENT"
    INVITATION_ACCEPTED = "INVITATION_ACCEPTED"
    SESSIONS_REVOKED = "SESSIONS_REVOKED"
    UNLOCK = "UNLOCK"
    EXPORT = "EXPORT"
    DOWNLOAD = "DOWNLOAD"


@dataclass(frozen=True)
class RequestMeta:
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None

    @classmethod
    def from_request(cls, request: Request) -> RequestMeta:
        ua = request.headers.get("user-agent")
        return cls(
            ip_address=request.client.host if request.client else None,
            user_agent=ua[:255] if ua else None,
            request_id=get_request_id(),
        )


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Field-level changes {"field": {"from": x, "to": y}}, excluding sensitive fields."""
    changes: dict[str, Any] = {}
    for key in sorted(set(before) | set(after)):
        if key in SENSITIVE_FIELDS:
            continue
        old, new = before.get(key), after.get(key)
        if old != new:
            changes[key] = {"from": _jsonable(old), "to": _jsonable(new)}
    return changes


def record(
    db: Session,
    *,
    action: AuditAction,
    entity_type: str,
    summary: str,
    actor_id: uuid.UUID | None,
    entity_id: uuid.UUID | str | None = None,
    changes: dict[str, Any] | None = None,
    meta: RequestMeta | None = None,
) -> AuditLog:
    meta = meta or RequestMeta(request_id=get_request_id())
    entry = AuditLog(
        user_id=actor_id,
        action=action.value,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        summary=summary,
        changes={k: v for k, v in changes.items() if k not in SENSITIVE_FIELDS} if changes else None,
        ip_address=meta.ip_address,
        user_agent=meta.user_agent,
        request_id=meta.request_id,
    )
    db.add(entry)
    return entry

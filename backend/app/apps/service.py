"""Service app business logic (plan v3, section 8): cases, SLAs, escalation, closing, web-to-case."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.apps.sales import BusinessRuleError, rule, stamp_now
from app.engine.hooks import Change, Event, action, on, ref
from app.engine.records import RecordService
from app.engine.types import format_datetime, parse_datetime
from app.models import Notification, QueueMember, Record
from app.services.settings import get_setting

CLOSED = "Closed"


def _sla(svc: RecordService, priority: str | None) -> dict[str, float]:
    table = get_setting(svc.db, "case_sla") or {}
    return (
        table.get(priority or "Medium")
        or table.get("Medium")
        or {"first_response_hours": 8, "resolution_hours": 72}
    )


def _due(start: datetime, hours: float) -> str:
    return format_datetime(start + timedelta(hours=float(hours)))


@on("case", Event.BEFORE_CREATE)
def case_defaults(change: Change) -> None:
    data = change.data
    svc = change.svc
    data.setdefault("status", "New")
    if not data.get("account") and data.get("contact"):
        contact = svc.db.get(Record, ref(data["contact"]))
        if contact is not None and contact.data.get("account"):
            data["account"] = contact.data["account"]
    sla = _sla(svc, data.get("priority"))
    now = datetime.now(UTC)
    data["first_response_due"] = _due(now, sla["first_response_hours"])
    data["resolution_due"] = _due(now, sla["resolution_hours"])
    if svc.policy.is_portal:
        # Customers never own records: portal cases go to the support queue.
        change.system["owner_id"] = None
        change.system["queue_id"] = support_queue_id(svc.db)
        data["origin"] = "Portal"
        user_contact = svc.sharing.contact_id
        if user_contact is not None:
            data["contact"] = str(user_contact)
            if svc.sharing.account_id is not None:
                data["account"] = str(svc.sharing.account_id)


@on("case", Event.BEFORE_UPDATE)
def case_rules(change: Change) -> None:
    data, old = change.data, change.old
    record = change.record
    assert record is not None
    if change.is_changed("priority") and data.get("status") != CLOSED:
        sla = _sla(change.svc, data.get("priority"))
        data["resolution_due"] = _due(record.created_at, sla["resolution_hours"])
        if not data.get("first_responded_at"):
            data["first_response_due"] = _due(record.created_at, sla["first_response_hours"])
    if change.is_changed("status"):
        if old.get("status") == "New" and not data.get("first_responded_at") and not change.svc.system:
            data["first_responded_at"] = stamp_now()
        if data.get("status") == CLOSED:
            if not data.get("resolution"):
                raise BusinessRuleError(
                    "Enter a resolution to close the case.", fields={"resolution": "Required to close"}
                )
            data["closed_at"] = stamp_now()
        elif old.get("status") == CLOSED:
            data["closed_at"] = None
            data["is_escalated"] = False
        if (
            data.get("status") != "Escalated"
            and old.get("status") == "Escalated"
            and data.get("status") != CLOSED
        ):
            data["is_escalated"] = bool(data.get("is_escalated"))


@action("case", "close", "Close Case", visible=lambda r: r.data.get("status") != CLOSED)
def close_case(svc: RecordService, case: Record, payload: dict[str, Any]) -> dict[str, Any]:
    resolution = str(payload.get("resolution") or case.data.get("resolution") or "").strip()
    if not resolution:
        raise BusinessRuleError(
            "Enter a resolution to close the case.", fields={"resolution": "Required to close"}
        )
    svc.update("case", case.id, {"status": CLOSED, "resolution": resolution}, record=case)
    return svc.serialize(case)


@action("case", "reopen", "Reopen", visible=lambda r: r.data.get("status") == CLOSED)
def reopen_case(svc: RecordService, case: Record, payload: dict[str, Any]) -> dict[str, Any]:
    if case.data.get("status") != CLOSED:
        raise rule("Only closed cases can be reopened.")
    svc.update("case", case.id, {"status": "Working"}, record=case)
    return svc.serialize(case)


@action("case", "accept", "Accept", requires_edit=True, visible=lambda r: r.queue_id is not None)
def accept_case(svc: RecordService, case: Record, payload: dict[str, Any]) -> dict[str, Any]:
    """Take a queue-owned case (queue members only)."""
    if case.queue_id is None:
        raise rule("This case isn't in a queue.")
    svc.change_owner("case", case.id, owner_id=svc.user_id)
    return svc.serialize(case)


def support_queue_id(db: Session) -> uuid.UUID | None:
    configured = (get_setting(db, "service") or {}).get("web_queue_id")
    if configured:
        return uuid.UUID(str(configured))
    from app.engine.standard_v1 import SUPPORT_QUEUE_ID
    from app.models import Queue

    return SUPPORT_QUEUE_ID if db.get(Queue, SUPPORT_QUEUE_ID) is not None else None


def notify(
    db: Session,
    user_id: uuid.UUID,
    title: str,
    body: str | None,
    link: str | None,
    record_id: uuid.UUID | None,
) -> None:
    db.add(Notification(user_id=user_id, title=title[:200], body=body, link=link, record_id=record_id))


def escalate_overdue_cases(db: Session, now: datetime | None = None) -> int:
    """Scheduled job: flag open cases past their resolution due date and notify the owner / queue."""
    now = now or datetime.now(UTC)
    svc = RecordService.as_system(db)
    rows = db.scalars(
        select(Record)
        .where(
            Record.object_api_name == "case",
            Record.is_deleted.is_(False),
            Record.data["status"].astext != CLOSED,
            Record.data["is_escalated"].astext.is_distinct_from("true"),
            Record.data["resolution_due"].astext.is_not(None),
        )
        .with_for_update(skip_locked=True)
    ).all()
    count = 0
    for case in rows:
        due = case.data.get("resolution_due")
        if not due or parse_datetime(due) > now:
            continue
        svc.update("case", case.id, {"is_escalated": True, "status": "Escalated"}, record=case)
        recipients: list[uuid.UUID] = []
        if case.owner_id:
            recipients.append(case.owner_id)
        elif case.queue_id:
            recipients += list(
                db.scalars(select(QueueMember.user_id).where(QueueMember.queue_id == case.queue_id))
            )
        for uid in recipients:
            notify(
                db,
                uid,
                f"Case {case.name} is overdue",
                case.data.get("subject"),
                f"/o/case/{case.id}",
                case.id,
            )
        count += 1
    db.commit()
    return count


def web_to_case(db: Session, payload: dict[str, Any]) -> Record:
    """Public web form: create a case (origin Web), matched to a contact by e-mail when possible."""
    svc = RecordService.as_system(db)
    email = str(payload.get("email") or "").strip().lower()
    values: dict[str, Any] = {
        "subject": payload.get("subject"),
        "description": payload.get("description"),
        "origin": "Web",
        "supplied_name": payload.get("name"),
        "supplied_email": email or None,
        "type": payload.get("type")
        if payload.get("type") in ("Question", "Problem", "Feature Request", "Billing", "Other")
        else None,
    }
    if email:
        contact = db.scalar(
            select(Record)
            .where(
                Record.object_api_name == "contact",
                Record.is_deleted.is_(False),
                Record.data["email"].astext == email,
            )
            .limit(1)
        )
        if contact is not None:
            values["contact"] = str(contact.id)
    record = svc.create(
        "case", {k: v for k, v in values.items() if v is not None}, queue_id=support_queue_id(db)
    )
    db.commit()
    return record

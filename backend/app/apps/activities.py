"""Tasks and events (plan v3, section 8, "Activities"): completion, validation and reminders."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime

from sqlalchemy import false, select
from sqlalchemy.orm import Session

from app.apps.sales import rule, stamp_now
from app.apps.service import notify
from app.engine.hooks import Change, Event, on
from app.engine.records import RecordService
from app.engine.types import parse_datetime
from app.models import Record, User
from app.services.email import app_link


@on("task", Event.BEFORE_CREATE, Event.BEFORE_UPDATE)
def task_completion(change: Change) -> None:
    status = change.data.get("status")
    if status == "Completed" and not change.data.get("completed_at"):
        change.data["completed_at"] = stamp_now()
    elif status != "Completed":
        change.data["completed_at"] = None
    if change.is_changed("reminder_at"):
        change.data["reminder_sent"] = False


@on("event", Event.BEFORE_CREATE, Event.BEFORE_UPDATE)
def event_times(change: Change) -> None:
    start, end = change.data.get("start_at"), change.data.get("end_at")
    if start and end and parse_datetime(end) < parse_datetime(start):
        raise rule("The end must be after the start.", "end_at")
    if change.is_changed("reminder_at"):
        change.data["reminder_sent"] = False


def send_due_reminders(db: Session, now: datetime | None = None) -> int:
    """Scheduled job: notification (and e-mail) for tasks and events whose reminder time has passed."""
    from app.services.email import queue_email

    now = now or datetime.now(UTC)
    svc = RecordService.as_system(db)
    rows = db.scalars(
        select(Record)
        .where(
            Record.object_api_name.in_(("task", "event")),
            Record.is_deleted == false(),
            Record.data["reminder_at"].astext.is_not(None),
            Record.data["reminder_sent"].astext.is_distinct_from("true"),
        )
        .with_for_update(skip_locked=True)
    ).all()
    emails: list[tuple[str, str, str]] = []
    count = 0
    for r in rows:
        if parse_datetime(r.data["reminder_at"]) > now or r.owner_id is None:
            continue
        if r.object_api_name == "task" and r.data.get("status") == "Completed":
            continue
        link = f"/o/{r.object_api_name}/{r.id}"
        when = r.data.get("due_date") or r.data.get("start_at") or ""
        notify(db, r.owner_id, f"Reminder: {r.name}", f"Due {when}".strip(), link, r.id)
        owner = db.get(User, r.owner_id)
        if owner is not None and owner.is_active:
            emails.append(
                (owner.email, f"Reminder: {r.name}", f"{r.name}\nDue: {when}\n\n{app_link(link)}\n")
            )
        svc.update(r.object_api_name, r.id, {"reminder_sent": True}, record=r)
        count += 1
    db.commit()
    for to, subject, body in emails:
        # The in-app notification is already stored; a broker outage must not fail the job.
        with contextlib.suppress(Exception):
            queue_email(to, subject, body)
    return count

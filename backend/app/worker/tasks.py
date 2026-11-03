"""Celery tasks: e-mail, marketing sends, imports and the scheduled jobs (plan v3, sections 7, 8, 12, 14)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from typing import Any

from app.services.email import deliver_email
from app.worker.celery_app import celery_app

logger = logging.getLogger("app.worker")


def _with_db(fn: Callable[..., Any], *args: Any) -> Any:
    import app.apps  # noqa: F401 - registers object hooks
    from app.db.session import get_sessionmaker

    with get_sessionmaker()() as db:
        try:
            return fn(db, *args)
        except Exception:
            db.rollback()
            raise


@celery_app.task(name="system.ping")
def ping() -> str:
    """Used by health checks and smoke tests to confirm the worker is processing jobs."""
    return "pong"


@celery_app.task(
    name="email.send",
    autoretry_for=(OSError,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=8,
)
def send_email_task(to: str, subject: str, body: str) -> None:
    deliver_email(to, subject, body)


@celery_app.task(name="engine.index_ddl")
def apply_index_ddl(statements: list[str]) -> None:
    from app.db.session import get_engine
    from app.engine.indexes import apply_concurrently

    apply_concurrently(get_engine(), statements)


@celery_app.task(name="marketing.process_send", acks_late=True)
def process_email_send_task(send_id: str) -> dict[str, int]:
    from app.apps.marketing import process_send

    result: dict[str, int] = _with_db(process_send, uuid.UUID(send_id))
    return result


def enqueue_email_send(send_id: uuid.UUID) -> None:
    """Called after the scheduling transaction; the beat job also picks up anything missed."""
    try:
        process_email_send_task.apply_async((str(send_id),), countdown=2)
    except Exception:  # noqa: BLE001 - broker down: the every-minute job will send it
        logger.warning("Could not enqueue e-mail send; the scheduler will retry", extra={"send_id": str(send_id)})


@celery_app.task(name="marketing.dispatch_due")
def dispatch_due_sends() -> int:
    from app.apps.marketing import due_sends

    ids: list[uuid.UUID] = _with_db(due_sends)
    for sid in ids:
        process_email_send_task.delay(str(sid))
    return len(ids)


@celery_app.task(name="imports.run")
def run_import_task(job_id: str) -> None:
    from app.services.imports import run_import

    _with_db(run_import, uuid.UUID(job_id))


@celery_app.task(name="service.escalate_cases")
def escalate_cases() -> int:
    from app.apps.service import escalate_overdue_cases

    count: int = _with_db(escalate_overdue_cases)
    return count


@celery_app.task(name="activities.reminders")
def activity_reminders() -> int:
    from app.apps.activities import send_due_reminders

    count: int = _with_db(send_due_reminders)
    return count


@celery_app.task(name="reports.scheduled")
def scheduled_reports() -> int:
    from app.services.reports import run_due_schedules

    count: int = _with_db(run_due_schedules)
    return count


@celery_app.task(name="maintenance.purge")
def purge() -> dict[str, int]:
    """Recycle bin (30 days) and deleted custom fields (15 days)."""

    def job(db: Any) -> dict[str, int]:
        from app.engine.admin import purge_deleted_fields
        from app.engine.records import RecordService
        from app.services.settings import get_setting

        retention = get_setting(db, "retention") or {}
        records = RecordService.as_system(db).purge_deleted(int(retention.get("recycle_bin_days") or 30))
        fields = purge_deleted_fields(db, int(retention.get("deleted_field_days") or 15))
        db.commit()
        return {"records": records, "fields": fields}

    result: dict[str, int] = _with_db(job)
    return result


@celery_app.task(name="packs.daily")
def pack_daily_jobs() -> int:
    from app.packs import run_daily_jobs

    count: int = _with_db(run_daily_jobs)
    return count

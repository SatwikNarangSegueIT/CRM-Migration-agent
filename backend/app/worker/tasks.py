"""Celery tasks: e-mail, marketing sends, imports and the scheduled jobs (plan v3, sections 7, 8, 12, 14)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from typing import Any

from app.services.email import deliver_email
from app.worker.celery_app import celery_app

logger = logging.getLogger("app.worker")


def _with_db(fn: Callable[..., Any], *args: Any, tenant: str | None = None) -> Any:
    """Run ``fn(db, *args)`` in the tenant schema ``tenant`` (default: public, the first tenant)."""
    import app.apps  # noqa: F401 - registers object hooks
    from app import packs

    packs.available()
    from app.db.session import get_sessionmaker
    from app.tenancy import IMPLICIT_PUBLIC, bind_tenant, by_schema

    with get_sessionmaker()() as db:
        bind_tenant(db, by_schema(tenant) if tenant else (by_schema("public") or IMPLICIT_PUBLIC))
        try:
            return fn(db, *args)
        except Exception:
            db.rollback()
            raise


def _each_tenant(fn: Callable[..., Any]) -> dict[str, Any]:
    """Scheduled jobs run once per active tenant; one firm's failure does not stop the others."""
    from app.tenancy import active_tenants

    results: dict[str, Any] = {}
    for tenant in active_tenants():
        try:
            results[tenant.schema] = _with_db(fn, tenant=tenant.schema)
        except Exception:
            logger.exception("Scheduled job failed for tenant", extra={"tenant": tenant.schema})
    return results


def _total(results: dict[str, Any]) -> int:
    return sum(int(v) for v in results.values() if isinstance(v, int))


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
def apply_index_ddl(statements: list[str], tenant: str = "public") -> None:
    from app.db.session import get_engine
    from app.engine.indexes import apply_concurrently

    apply_concurrently(get_engine(), statements, tenant)


@celery_app.task(name="marketing.process_send", acks_late=True)
def process_email_send_task(send_id: str, tenant: str | None = None) -> dict[str, int]:
    from app.apps.marketing import process_send

    result: dict[str, int] = _with_db(process_send, uuid.UUID(send_id), tenant=tenant)
    return result


def enqueue_email_send(send_id: uuid.UUID, tenant: str | None = None) -> None:
    """Called after the scheduling transaction; the beat job also picks up anything missed."""
    from app.worker.dispatch import forget_worker_check, run_in_thread, worker_available

    if worker_available():
        try:
            process_email_send_task.apply_async((str(send_id), tenant), countdown=2)
            return
        except Exception:
            logger.warning("Task queue unavailable; sending from the API", extra={"send_id": str(send_id)})
            forget_worker_check()
    run_in_thread(process_email_send_task, str(send_id), tenant)


@celery_app.task(name="marketing.dispatch_due")
def dispatch_due_sends() -> int:
    from app.apps.marketing import due_sends

    count = 0
    for schema, ids in _each_tenant(due_sends).items():
        for sid in ids:
            process_email_send_task.delay(str(sid), schema)
            count += 1
    return count


@celery_app.task(name="imports.run")
def run_import_task(job_id: str, tenant: str | None = None) -> None:
    from app.services.imports import run_import

    _with_db(run_import, uuid.UUID(job_id), tenant=tenant)


@celery_app.task(name="service.escalate_cases")
def escalate_cases() -> int:
    from app.apps.service import escalate_overdue_cases

    return _total(_each_tenant(escalate_overdue_cases))


@celery_app.task(name="activities.reminders")
def activity_reminders() -> int:
    from app.apps.activities import send_due_reminders

    return _total(_each_tenant(send_due_reminders))


@celery_app.task(name="reports.scheduled")
def scheduled_reports() -> int:
    from app.services.reports import run_due_schedules

    return _total(_each_tenant(run_due_schedules))


@celery_app.task(name="maintenance.purge")
def purge() -> dict[str, int]:
    """Recycle bin (30 days), deleted custom fields (15 days) and per-object retention policies."""

    def job(db: Any) -> dict[str, int]:
        from app.engine.admin import purge_deleted_fields
        from app.engine.records import RecordService
        from app.services.settings import get_setting

        retention = get_setting(db, "retention") or {}
        records = RecordService.as_system(db).purge_deleted(int(retention.get("recycle_bin_days") or 30))
        fields = purge_deleted_fields(db, int(retention.get("deleted_field_days") or 15))
        db.commit()
        from app.services.privacy import apply_retention

        retained = apply_retention(db)
        return {"records": records, "fields": fields, "retention": retained}

    totals: dict[str, int] = {"records": 0, "fields": 0, "retention": 0}
    for result in _each_tenant(job).values():
        for key in totals:
            totals[key] += int(result.get(key, 0))
    return totals


@celery_app.task(name="packs.daily")
def pack_daily_jobs() -> int:
    from app.packs import run_daily_jobs

    return _total(_each_tenant(run_daily_jobs))


@celery_app.task(name="platform.maintain")
def platform_maintenance() -> dict[str, int]:
    """Remove stale sign-ups and keep the warm pool of pre-built workspaces topped up."""
    from app.core.config import get_settings
    from app.db.migrate import fill_warm_pool
    from app.db.session import get_sessionmaker
    from app.services.signup import purge_unverified
    from app.tenancy import bind_tenant

    with get_sessionmaker()() as db:
        bind_tenant(db, None)
        purged = purge_unverified(db)
    built = fill_warm_pool(get_settings().signup_warm_pool_size)
    return {"signups_purged": purged, "schemas_built": built}

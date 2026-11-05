"""/cron/<job>: the scheduled jobs Celery beat runs, for hosts without a worker (e.g. Vercel Cron).

Vercel Cron calls each path with ``Authorization: Bearer <CRON_SECRET>``. Without CRON_SECRET configured the
endpoints answer 404, so they are never open by accident. Each call runs the job in the request and
returns its result.
"""

from __future__ import annotations

import hmac
import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Header

from app.core.config import get_settings
from app.core.errors import AppError

router = APIRouter(prefix="/cron", tags=["cron"])
logger = logging.getLogger("app.cron")


def _maintain() -> dict[str, Any]:
    """Pack upgrades for existing workspaces, stale sign-ups, and the ready-made workspace pools."""
    from app.domains import upgrade_all_domain_workspaces
    from app.worker.tasks import platform_maintenance

    upgraded = upgrade_all_domain_workspaces()
    return {"workspaces_upgraded": sum(upgraded.values()), **platform_maintenance.run()}


def _task(name: str) -> Callable[[], Any]:
    def run() -> Any:
        from app.worker import tasks

        task = {t.name: t for t in vars(tasks).values() if hasattr(t, "name") and hasattr(t, "run")}[name]
        return task.run()

    return run


# Path name -> job. Schedules (vercel.json "crons") mirror app.worker.celery_app's beat_schedule.
JOBS: dict[str, Callable[[], Any]] = {
    "email-sends": _task("marketing.dispatch_due"),
    "activity-reminders": _task("activities.reminders"),
    "escalate-cases": _task("service.escalate_cases"),
    "scheduled-reports": _task("reports.scheduled"),
    "purge": _task("maintenance.purge"),
    "packs-daily": _task("packs.daily"),
    "maintain": _maintain,
}


@router.get("/{job}")
def run_job(job: str, authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    secret = get_settings().cron_secret
    expected = f"Bearer {secret.get_secret_value()}" if secret and secret.get_secret_value() else None
    if expected is None or job not in JOBS:
        raise AppError("Not found.", status_code=404, code="not_found")
    if not hmac.compare_digest((authorization or "").encode(), expected.encode()):
        raise AppError("Not authorised.", status_code=401, code="unauthorised")
    result = JOBS[job]()
    logger.info("Scheduled job ran", extra={"job": job})
    return {"job": job, "result": result}

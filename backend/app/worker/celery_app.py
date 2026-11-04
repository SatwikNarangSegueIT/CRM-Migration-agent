"""Celery application (background jobs and scheduled reminders)."""

from __future__ import annotations

import logging
import socket
import threading

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level, settings.log_json)

celery_app = Celery(
    "migratecrm",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=settings.timezone,
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=300,
    task_soft_time_limit=240,
    result_expires=86_400,
    # Nothing reads task results. Recording them made every .delay() wait on the result store: with Redis
    # unreachable that is 20 one-second retries, then an error that leaves the process unable to queue.
    task_ignore_result=True,
    result_backend_transport_options={
        "retry_policy": {"max_retries": 1, "interval_start": 0, "interval_step": 0.5, "interval_max": 0.5}
    },
    broker_connection_retry_on_startup=True,
    # Publishing from a web request must fail fast when Redis is down; callers fall back (app.services.email).
    broker_connection_timeout=3,
    broker_transport_options={"socket_connect_timeout": 3, "socket_timeout": 5, "max_retries": 1},
    task_publish_retry_policy={"max_retries": 1, "interval_start": 0, "interval_step": 0.5},
    beat_schedule={
        "dispatch-due-email-sends": {"task": "marketing.dispatch_due", "schedule": 60.0},
        "activity-reminders": {"task": "activities.reminders", "schedule": 60.0},
        "escalate-overdue-cases": {"task": "service.escalate_cases", "schedule": 300.0},
        "scheduled-reports": {"task": "reports.scheduled", "schedule": 900.0},
        "purge-recycle-bin": {"task": "maintenance.purge", "schedule": crontab(hour=3, minute=0)},
        "industry-pack-daily-jobs": {"task": "packs.daily", "schedule": crontab(hour=6, minute=0)},
        "platform-maintenance": {"task": "platform.maintain", "schedule": 600.0},
    },
)


@worker_ready.connect
def _start_heartbeat(**_: object) -> None:
    """Tell the API a worker is running (app.worker.dispatch): refresh a Redis key every 30 seconds."""
    from app.core.redis_client import get_redis
    from app.worker.dispatch import HEARTBEAT_KEY, HEARTBEAT_SECONDS, HEARTBEAT_TTL

    stop = threading.Event()

    def beat() -> None:
        while not stop.is_set():
            try:
                get_redis().set(HEARTBEAT_KEY, socket.gethostname(), ex=HEARTBEAT_TTL)
            except Exception:
                logging.getLogger("app.worker").warning("Worker heartbeat failed", exc_info=True)
            stop.wait(HEARTBEAT_SECONDS)

    threading.Thread(target=beat, name="worker-heartbeat", daemon=True).start()

"""Celery application (background jobs and scheduled reminders)."""

from __future__ import annotations

from celery import Celery

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
    broker_connection_retry_on_startup=True,
    # Scheduled jobs (deadline / visa-expiry reminders) are added in later phases.
    beat_schedule={},
)

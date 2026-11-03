"""Celery tasks."""

from __future__ import annotations

from app.services.email import deliver_email
from app.worker.celery_app import celery_app


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

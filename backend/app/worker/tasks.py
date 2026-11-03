"""Celery tasks."""

from __future__ import annotations

from app.worker.celery_app import celery_app


@celery_app.task(name="system.ping")
def ping() -> str:
    """Used by health checks and smoke tests to confirm the worker is processing jobs."""
    return "pong"

"""Hand background work to the Celery worker when one is running, otherwise run it in the API process.

A running worker refreshes a heartbeat key in Redis every 30 seconds (``app.worker.celery_app``). Without a
fresh heartbeat (no worker deployed, worker down, Redis unreachable) a task would sit in the queue unseen,
so it runs in a background thread of the API instead: sign-up e-mails, password resets, imports and index
builds keep working on a single-process deployment.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger("app.worker")

HEARTBEAT_KEY = "crm:worker:heartbeat"
HEARTBEAT_SECONDS = 30
HEARTBEAT_TTL = 90
_CHECK_SECONDS = 15.0

_lock = threading.Lock()
_checked: tuple[float, bool] | None = None


def worker_available() -> bool:
    """True when a worker has sent a heartbeat in the last 90 seconds (checked at most every 15 s)."""
    global _checked
    with _lock:
        if _checked is not None and time.monotonic() - _checked[0] < _CHECK_SECONDS:
            return _checked[1]
    try:
        from app.core.redis_client import get_redis

        alive = bool(get_redis().exists(HEARTBEAT_KEY))
    except Exception:
        alive = False
    with _lock:
        _checked = (time.monotonic(), alive)
    return alive


def forget_worker_check() -> None:
    global _checked
    with _lock:
        _checked = None


def run_in_thread(task: Any, *args: Any) -> None:
    def run() -> None:
        try:
            task.run(*args)
        except Exception:
            logger.exception("Background job failed", extra={"task": getattr(task, "name", str(task))})

    threading.Thread(target=run, name=f"job-{getattr(task, 'name', 'task')}", daemon=True).start()


def dispatch(task: Any, *args: Any) -> str:
    """Queue ``task`` for the worker, or run it in a thread here. Returns "queued" or "inline"."""
    if worker_available():
        try:
            task.delay(*args)
            return "queued"
        except Exception:
            logger.warning("Task queue unavailable; running the job in the API", exc_info=True)
            forget_worker_check()
    run_in_thread(task, *args)
    return "inline"

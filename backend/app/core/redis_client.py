"""Shared Redis client (rate limiting). Celery manages its own connections."""

from __future__ import annotations

from functools import lru_cache

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from app.core.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    # No retries: callers fail open (rate limits) or fall back (task dispatch) rather than wait.
    return redis.Redis.from_url(
        get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2, retry=Retry(NoBackoff(), 0)
    )

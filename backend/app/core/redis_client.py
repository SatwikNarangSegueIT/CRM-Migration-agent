"""Shared Redis client (rate limiting). Celery manages its own connections."""

from __future__ import annotations

from functools import lru_cache

import redis

from app.core.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2)

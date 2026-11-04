"""Fixed-window rate limiting backed by Redis.

Fails open (allows the request and logs) if Redis is unreachable, so an outage of the cache does not
lock everyone out; account lockout in the database still protects logins.
"""

from __future__ import annotations

import hashlib
import logging
import time

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.redis_client import get_redis

logger = logging.getLogger("app.rate_limit")


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


def _key(bucket: str, identity: str) -> str:
    digest = hashlib.sha256(identity.lower().encode()).hexdigest()[:32]
    return f"rl:{bucket}:{digest}"


_last_warning = 0.0


def _warn_unavailable(exc: Exception) -> None:
    """One line a minute while Redis is down, not a traceback per request."""
    global _last_warning
    now = time.monotonic()
    if now - _last_warning >= 60:
        _last_warning = now
        logger.warning("Rate limiter unavailable (Redis: %s); allowing requests", exc)


def check_rate_limit(bucket: str, identity: str, *, limit: int, window_seconds: int) -> None:
    """Count one hit for (bucket, identity); raise RateLimitedError when over the limit."""
    if not get_settings().rate_limit_enabled:
        return
    key = _key(bucket, identity)
    try:
        client = get_redis()
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        count, _ = pipe.execute()
    except Exception as exc:
        _warn_unavailable(exc)
        return
    if int(count) > limit:
        raise RateLimitedError("Too many attempts. Please wait a few minutes and try again.")

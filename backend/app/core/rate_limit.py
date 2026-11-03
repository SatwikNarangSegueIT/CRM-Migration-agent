"""Fixed-window rate limiting backed by Redis.

Fails open (allows the request and logs) if Redis is unreachable, so an outage of the cache does not
lock everyone out; account lockout in the database still protects logins.
"""

from __future__ import annotations

import hashlib
import logging

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
    except Exception:
        logger.warning("Rate limiter unavailable; allowing request", exc_info=True, extra={"bucket": bucket})
        return
    if int(count) > limit:
        raise RateLimitedError("Too many attempts. Please wait a few minutes and try again.")

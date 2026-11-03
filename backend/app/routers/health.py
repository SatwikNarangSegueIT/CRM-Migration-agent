"""Liveness and readiness probes."""

from __future__ import annotations

import logging
from typing import Literal

import redis
from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import get_engine

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger("app.health")

CheckStatus = Literal["ok", "error"]


class LiveResponse(BaseModel):
    status: Literal["ok"]
    app: str
    environment: str


class ReadyResponse(BaseModel):
    status: CheckStatus
    checks: dict[str, CheckStatus]


@router.get("/live", response_model=LiveResponse)
def live() -> LiveResponse:
    settings = get_settings()
    return LiveResponse(status="ok", app=settings.app_name, environment=settings.app_env)


def _check_database() -> CheckStatus:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        logger.exception("Database readiness check failed")
        return "error"


def _check_redis() -> CheckStatus:
    try:
        client = redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2)
        try:
            client.ping()
        finally:
            client.close()
        return "ok"
    except Exception:
        logger.exception("Redis readiness check failed")
        return "error"


@router.get("/ready", response_model=ReadyResponse, responses={503: {"model": ReadyResponse}})
def ready(response: Response) -> ReadyResponse:
    checks: dict[str, CheckStatus] = {"database": _check_database(), "redis": _check_redis()}
    overall: CheckStatus = "ok" if all(v == "ok" for v in checks.values()) else "error"
    if overall != "ok":
        response.status_code = 503
    return ReadyResponse(status=overall, checks=checks)

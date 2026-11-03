"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI

from app import apps as _apps  # noqa: F401 - registers the standard apps' object hooks
from app import packs
from app.auth.deps import verify_origin
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.routers import (
    admin_users,
    audit_logs,
    auth,
    data,
    health,
    meta,
    org_settings,
    portal,
    public,
    records,
    reports,
    setup,
    setup_objects,
    workspace,
)
from app.routers import packs as packs_router

packs.available()  # registers industry packs and their hooks

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)
    logger = logging.getLogger("app")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info("Starting %s", settings.app_name, extra={"environment": settings.app_env})
        yield
        logger.info("Shutting down %s", settings.app_name)

    docs_enabled = not settings.is_production
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json" if docs_enabled else None,
    )
    app.add_middleware(RequestContextMiddleware, hsts=settings.app_env in ("staging", "production"))
    register_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX, dependencies=[Depends(verify_origin)])
    api.include_router(health.router)
    api.include_router(auth.router)
    api.include_router(setup.router)
    api.include_router(admin_users.router)
    api.include_router(audit_logs.router)
    api.include_router(meta.router)
    api.include_router(records.router)
    api.include_router(workspace.router)
    api.include_router(setup_objects.router)
    api.include_router(reports.router)
    api.include_router(data.router)
    api.include_router(org_settings.router)
    api.include_router(portal.router)
    api.include_router(portal.staff_router)
    api.include_router(public.router)
    api.include_router(packs_router.router)
    app.include_router(api)
    return app


app = create_app()

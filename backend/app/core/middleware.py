"""Pure ASGI middleware: request ids, access logging and security headers."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_body
from app.core.request_context import db_stats_var, request_id_var

access_logger = logging.getLogger("app.access")
error_logger = logging.getLogger("app.errors")

_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")

SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class RequestContextMiddleware:
    """Assigns a request id (honouring a well-formed inbound X-Request-ID), logs each request,
    and adds security headers to every response."""

    def __init__(self, app: ASGIApp, *, hsts: bool = False, server_timing: bool = False) -> None:
        self.app = app
        self.hsts = hsts
        self.server_timing = server_timing

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        inbound = None
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                inbound = value.decode("latin-1")
                break
        request_id = inbound if inbound and _VALID_REQUEST_ID.match(inbound) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        stats: list[float] = [0, 0.0]
        stats_token = db_stats_var.set(stats) if self.server_timing else None
        start = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                for key, value in SECURITY_HEADERS.items():
                    headers.setdefault(key, value)
                if scope["path"].startswith("/api/"):
                    headers.setdefault("Cache-Control", "no-store")
                if self.hsts:
                    headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
                if self.server_timing:
                    total = (time.perf_counter() - start) * 1000
                    headers["Server-Timing"] = (
                        f'db;desc="{int(stats[0])} queries";dur={stats[1] * 1000:.1f}, app;dur={total:.1f}'
                    )
            await send(message)

        try:
            try:
                await self.app(scope, receive, send_wrapper)
            except Exception:
                error_logger.exception(
                    "Unhandled error", extra={"method": scope["method"], "path": scope["path"]}
                )
                if response_started:
                    raise
                body = json.dumps(error_body("internal_error", "An unexpected error occurred.")).encode()
                await send_wrapper(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode()),
                        ],
                    }
                )
                await send_wrapper({"type": "http.response.body", "body": body})
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            if not scope["path"].startswith("/api/v1/health"):
                access_logger.info(
                    "request",
                    extra={
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": status_code,
                        "duration_ms": duration_ms,
                    },
                )
            request_id_var.reset(token)
            if stats_token is not None:
                db_stats_var.reset(stats_token)

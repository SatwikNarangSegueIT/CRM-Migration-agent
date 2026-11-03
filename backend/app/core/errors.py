"""Uniform error format: {"error": {"code", "message", "fields", "request_id"}}."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import get_request_id

_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "service_unavailable",
}


class AppError(Exception):
    """Raise from services/routers for expected, user-facing errors."""

    status_code = 400
    code = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        fields: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.fields = fields or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "forbidden"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


def error_body(code: str, message: str, fields: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "fields": fields or {},
            "request_id": get_request_id(),
        }
    }


def _field_path(loc: tuple[Any, ...] | list[Any]) -> str:
    # Drop the location prefix ("body", "query", "path", ...) for a client-friendly key.
    parts = [str(p) for p in loc]
    if parts and parts[0] in {"body", "query", "path", "header", "cookie"}:
        parts = parts[1:]
    return ".".join(parts) or "__root__"


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(error_body(exc.code, exc.message, exc.fields), status_code=exc.status_code)


async def _validation_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields: dict[str, str] = {}
    for err in exc.errors():
        key = _field_path(err.get("loc", ()))
        fields.setdefault(key, str(err.get("msg", "Invalid value")))
    return JSONResponse(error_body("validation_error", "Some fields are invalid.", fields), status_code=422)


async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _STATUS_CODES.get(exc.status_code, "error")
    message = exc.detail if isinstance(exc.detail, str) else code.replace("_", " ").capitalize()
    return JSONResponse(error_body(code, message), status_code=exc.status_code, headers=exc.headers)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    # Unhandled exceptions are converted to a 500 by RequestContextMiddleware, which runs inside
    # Starlette's ServerErrorMiddleware and therefore still has the request id in context.

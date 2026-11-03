"""/public: unauthenticated endpoints (plan v3, section 13).

Web-to-lead and web-to-case are rate limited per IP and protected by a honeypot field (a CAPTCHA
provider can be added in `_verify_human`). Tracking and unsubscribe links use random per-recipient
tokens; click redirects only go to URLs signed when the e-mail was rendered (no open redirect).
"""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from app.apps import marketing
from app.apps.service import web_to_case as create_web_case
from app.core.errors import AppError, NotFoundError
from app.core.rate_limit import check_rate_limit
from app.db.session import get_sessionmaker
from app.services.settings import get_setting

router = APIRouter(prefix="/public", tags=["public"])
PIXEL = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


class WebLeadIn(BaseModel):
    first_name: str | None = Field(default=None, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    company: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    title: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=4000)
    email_opt_in: bool = False
    # Honeypot: real visitors never fill this hidden field.
    website_url: str | None = Field(default=None, max_length=500)


class WebCaseIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    subject: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=32000)
    type: str | None = Field(default=None, max_length=40)
    website_url: str | None = Field(default=None, max_length=500)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _verify_human(request: Request, honeypot: str | None) -> bool:
    return not honeypot


@router.get("/branding")
def branding() -> dict[str, Any]:
    with get_sessionmaker()() as db:
        b = get_setting(db, "branding") or {}
    return {
        "name": b.get("name") or "Meridian CRM",
        "primary_color": b.get("primary_color") or "#0176d3",
        "logo_url": b.get("logo_url"),
    }


@router.post("/web-to-lead", status_code=202)
def web_to_lead(body: WebLeadIn, request: Request) -> dict[str, str]:
    check_rate_limit("web-to-lead", _ip(request), limit=10, window_seconds=3600)
    with get_sessionmaker()() as db:
        if not (get_setting(db, "service") or {}).get("web_to_lead_enabled", True):
            raise NotFoundError("Not found.")
        if _verify_human(request, body.website_url):
            marketing.web_to_lead(db, body.model_dump(exclude={"website_url"}), _ip(request))
    return {"message": "Thank you. We'll be in touch soon."}


@router.post("/web-to-case", status_code=202)
def web_to_case(body: WebCaseIn, request: Request) -> dict[str, str]:
    check_rate_limit("web-to-case", _ip(request), limit=10, window_seconds=3600)
    with get_sessionmaker()() as db:
        if not (get_setting(db, "service") or {}).get("web_to_case_enabled", True):
            raise NotFoundError("Not found.")
        if _verify_human(request, body.website_url):
            case = create_web_case(db, body.model_dump(exclude={"website_url"}))
            return {"message": f"Thanks - your reference is {case.name}."}
    return {"message": "Thanks - we've received your request."}


@router.get("/unsubscribe/{token}")
def unsubscribe_info(token: str) -> dict[str, Any]:
    with get_sessionmaker()() as db:
        d = marketing.delivery_by_token(db, token)
        if d is None:
            raise NotFoundError("This link is invalid.")
        brand = (get_setting(db, "branding") or {}).get("name", "")
        return {"email": d.email, "unsubscribed": d.unsubscribed_at is not None, "sender": brand}


@router.post("/unsubscribe/{token}")
def unsubscribe(token: str, request: Request) -> dict[str, Any]:
    check_rate_limit("unsubscribe", _ip(request), limit=60, window_seconds=3600)
    with get_sessionmaker()() as db:
        if not marketing.unsubscribe(db, token, _ip(request)):
            raise NotFoundError("This link is invalid.")
    return {"unsubscribed": True}


@router.get("/e/{token}/open.gif")
def open_pixel(token: str) -> Response:
    with get_sessionmaker()() as db:
        marketing.track_open(db, token)
    return Response(PIXEL, media_type="image/gif", headers={"Cache-Control": "no-store, max-age=0"})


@router.get("/e/{token}/click")
def click(token: str, u: str = Query(max_length=2000), s: str = Query(max_length=64)) -> RedirectResponse:
    if not u.lower().startswith(("http://", "https://")) or not marketing.verify_click(token, u, s):
        raise AppError("This link is invalid.", status_code=400)
    with get_sessionmaker()() as db:
        marketing.track_click(db, token)
    return RedirectResponse(u, status_code=302)

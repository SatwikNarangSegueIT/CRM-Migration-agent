"""/signup: public sign-up with a choice of profession (plan v4, section 4)."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, StringConstraints
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.rate_limit import check_rate_limit
from app.db.session import get_sessionmaker
from app.domains import DOMAINS
from app.routers.auth import _set_auth_cookies
from app.services import signup as svc
from app.services.audit import RequestMeta
from app.services.email import MailDeliveryError, app_link, queue_email
from app.tenancy import bind_tenant

router = APIRouter(prefix="/signup", tags=["signup"])
logger = logging.getLogger("app.signup")

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class SignupIn(BaseModel):
    domain: str = Field(max_length=40)
    firm_name: Text
    name: Text
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    abn: str | None = Field(default=None, max_length=20)
    accept_terms: bool
    # Honeypot: real visitors never fill this hidden field.
    website_url: str | None = Field(default=None, max_length=500)


class VerifyIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _verify_human(request: Request, honeypot: str | None) -> bool:
    """CAPTCHA providers plug in here; the honeypot catches simple bots."""
    return not honeypot


def _platform_session() -> Session:
    db = get_sessionmaker()()
    bind_tenant(db, None)  # platform tables are schema-qualified; no tenant data is reachable
    return db


@router.get("/domains")
def domains() -> list[dict[str, Any]]:
    return [
        {
            "key": d.key,
            "label": d.label,
            "profession": d.profession,
            "description": d.description,
            "includes": list(d.includes),
            "color": d.color,
        }
        for d in DOMAINS.values()
    ]


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def start(body: SignupIn, request: Request, response: Response) -> dict[str, Any]:
    """Start a sign-up. Normally e-mails a confirmation link (202). When this install can't send e-mail and
    verification isn't required (development, staging), the workspace is created at once (201) and the
    person is signed in, exactly as after confirming."""
    check_rate_limit("signup-ip", _ip(request), limit=10, window_seconds=3600)
    check_rate_limit("signup-email", str(body.email).lower(), limit=5, window_seconds=3600)
    if not body.accept_terms:
        raise AppError(
            "Accept the terms and privacy policy to continue.",
            status_code=422,
            code="validation_error",
            fields={"accept_terms": "Required."},
        )
    message = {"message": "Check your e-mail for a link to finish setting up your workspace."}
    if not _verify_human(request, body.website_url):
        logger.warning("Sign-up ignored: the hidden bot-check field was filled", extra={"ip": _ip(request)})
        return message
    with _platform_session() as db:
        token = svc.start_signup(
            db,
            domain=body.domain,
            firm_name=body.firm_name,
            name=body.name,
            email=str(body.email),
            password=body.password,
            abn=body.abn,
        )
    if not svc.verification_required():
        with _platform_session() as platform, get_sessionmaker()() as tenant_db:
            result = svc.verify_and_provision(platform, tenant_db, token, RequestMeta.from_request(request))
            _set_auth_cookies(response, result.issued, tenant_db)
        response.status_code = status.HTTP_201_CREATED
        return {"state": result.state.value, "workspace": {"slug": result.slug, "name": result.name}}
    hours = get_settings().signup_verification_hours
    try:
        # Sent before answering (unless a worker takes it), so a broken mail set-up is reported, not hidden.
        queue_email(
            str(body.email),
            f"Confirm your e-mail to create {body.firm_name}'s workspace",
            f"Hello {body.name},\n\nConfirm your e-mail address to create your Segue CRM workspace for "
            f"{body.firm_name}. The link works once and expires in {hours} hours:\n\n"
            f"{app_link('/verify-signup#token=' + token)}\n\n"
            "If you did not sign up, ignore this e-mail and nothing will be created.\n",
            wait=True,
        )
    except MailDeliveryError as exc:
        logger.error("Sign-up confirmation e-mail failed: %s", exc)
        raise AppError(
            "We couldn't send the confirmation e-mail just now. Please try again in a few minutes.",
            status_code=503,
            code="email_failed",
        ) from exc
    return message


@router.post("/verify")
def verify(body: VerifyIn, request: Request, response: Response) -> dict[str, Any]:
    check_rate_limit("token-ip", _ip(request), limit=20, window_seconds=900)
    with _platform_session() as platform, get_sessionmaker()() as tenant_db:
        result = svc.verify_and_provision(platform, tenant_db, body.token, RequestMeta.from_request(request))
        _set_auth_cookies(response, result.issued, tenant_db)
    return {"state": result.state.value, "workspace": {"slug": result.slug, "name": result.name}}

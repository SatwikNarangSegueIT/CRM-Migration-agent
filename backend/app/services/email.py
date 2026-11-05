"""Outgoing e-mail: SMTP (e.g. Zoho Mail on 465 or 587), Zoho ZeptoMail's HTTP API, or the log.

What to send with comes from ``app.services.mail_settings`` (environment defaults, overridden in Setup).
Who sends it comes from ``app.worker.dispatch``: the Celery worker when one is running, otherwise the API.
Failures are raised as ``MailDeliveryError`` with a message an administrator can act on.
"""

from __future__ import annotations

import contextlib
import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.mail_settings import MailConfig, mail_config

logger = logging.getLogger("app.email")
TIMEOUT_SECONDS = 20


class MailDeliveryError(Exception):
    """The e-mail could not be sent; the message says why in plain language."""


# ------------------------------------------------------------------ sending


def _smtp_error(exc: Exception, config: MailConfig) -> MailDeliveryError:
    where = f"{config.smtp_host}:{config.smtp_port}"
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return MailDeliveryError(
            f"The mail server rejected the username or password ({exc.smtp_code}). With Zoho, use the full "
            "mailbox address as the username and, if two-factor sign-in is on, an application-specific "
            "password."
        )
    if isinstance(exc, smtplib.SMTPSenderRefused) or (
        isinstance(exc, smtplib.SMTPResponseException) and exc.smtp_code in (550, 553, 554)
    ):
        return MailDeliveryError(
            f"The mail server won't send from {config.from_email} ({getattr(exc, 'smtp_code', '')}). "
            "With Zoho, the From address must be the mailbox you sign in with or one of its aliases."
        )
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return MailDeliveryError(f"The mail server refused the recipient: {exc.recipients}")
    if isinstance(exc, ssl.SSLError | smtplib.SMTPNotSupportedError):
        return MailDeliveryError(
            f"Secure connection to {where} failed. Use SSL with port 465, or STARTTLS with port 587."
        )
    if isinstance(exc, TimeoutError):
        return MailDeliveryError(
            f"Timed out connecting to {where}. Check the host and port, and that your host allows "
            "outbound SMTP (some block ports 25, 465 and 587; ZeptoMail's API works over HTTPS instead)."
        )
    if isinstance(exc, OSError):
        return MailDeliveryError(f"Couldn't connect to {where}: {exc}. Check the host and port.")
    return MailDeliveryError(f"The mail server returned an error: {exc}")


def _send_smtp(config: MailConfig, message: EmailMessage) -> None:
    if not config.smtp_host:
        raise MailDeliveryError("Enter the SMTP server (for Zoho Mail, e.g. smtppro.zoho.com).")
    context = ssl.create_default_context()
    try:
        smtp: smtplib.SMTP
        if config.smtp_security == "ssl":
            smtp = smtplib.SMTP_SSL(
                config.smtp_host, config.smtp_port, timeout=TIMEOUT_SECONDS, context=context
            )
        else:
            smtp = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=TIMEOUT_SECONDS)
        with smtp:
            if config.smtp_security == "starttls":
                smtp.starttls(context=context)
            if config.smtp_username and config.smtp_password:
                smtp.login(config.smtp_username, config.smtp_password)
            smtp.send_message(message)
    except MailDeliveryError:
        raise
    except Exception as exc:
        raise _smtp_error(exc, config) from exc


# Headers the ZeptoMail API takes as fields of its own rather than as MIME headers.
_ZEPTO_OWN_HEADERS = {"from", "to", "subject", "reply-to", "content-type", "mime-version"}


def _address(value: str) -> dict[str, str]:
    name, email_address = parseaddr(value)
    return {"address": email_address, "name": name} if name else {"address": email_address}


def _send_zeptomail(config: MailConfig, message: EmailMessage, text_body: str, html_body: str | None) -> None:
    """ZeptoMail's Send Mail API (https://www.zoho.com/zeptomail/help/api/email-sending.html)."""
    import httpx

    if not config.zeptomail_token:
        raise MailDeliveryError("Enter the ZeptoMail Send Mail token (ZeptoMail -> Mail Agents -> SMTP/API).")
    token = config.zeptomail_token.strip()
    if not token.lower().startswith("zoho-enczapikey"):
        token = f"Zoho-enczapikey {token}"
    sender = _address(str(message["From"]))
    sender.setdefault("name", sender["address"])
    payload: dict[str, object] = {
        "from": sender,  # the message's sender (a firm's own name on its campaigns), else the default
        "to": [{"email_address": _address(str(message["To"]))}],
        "subject": str(message["Subject"]),
        "textbody": text_body,
    }
    if html_body:
        payload["htmlbody"] = html_body
    if message["Reply-To"]:
        payload["reply_to"] = [_address(str(message["Reply-To"]))]
    extra = {
        k: str(v)
        for k, v in message.items()
        if k.lower() not in _ZEPTO_OWN_HEADERS and not k.lower().startswith("content-")
    }
    if extra:
        payload["mime_headers"] = extra  # e.g. List-Unsubscribe
    if config.zeptomail_bounce_address:
        payload["bounce_address"] = config.zeptomail_bounce_address
    try:
        response = httpx.post(
            config.zeptomail_api_url,
            json=payload,
            headers={"Authorization": token, "Accept": "application/json"},
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise MailDeliveryError(f"Couldn't reach ZeptoMail at {config.zeptomail_api_url}: {exc}") from exc
    if response.status_code >= 400:
        detail = response.text[:300]
        try:
            error = response.json().get("error", {})
            parts = [error.get("message", "")] + [d.get("message", "") for d in error.get("details", [])]
            detail = " ".join(p for p in parts if p) or detail
        except ValueError:  # not JSON: keep the raw text
            logger.debug("ZeptoMail error body is not JSON")
        hint = ""
        if response.status_code in (401, 403):
            hint = " Check the token and that the From address's domain is verified in ZeptoMail."
        raise MailDeliveryError(f"ZeptoMail refused the e-mail ({response.status_code}): {detail}.{hint}")


def send(
    to: str,
    subject: str,
    text_body: str,
    *,
    html_body: str | None = None,
    from_name: str | None = None,
    from_email: str | None = None,
    headers: dict[str, str] | None = None,
    config: MailConfig | None = None,
) -> None:
    """Send one e-mail now, with ``config`` or the current configuration. Raises MailDeliveryError."""
    config = config or mail_config()
    if config.provider == "console":
        # The text is in the message itself: Celery's log formatter drops `extra` fields.
        logger.info(
            "E-mail (console backend: not sent)\nTo: %s\nSubject: %s\n\n%s",
            to,
            subject,
            text_body,
            extra={"to": to, "subject": subject, "body": text_body},
        )
        return
    message = EmailMessage()
    sender_email = from_email or config.from_email
    sender_name = from_name if from_email else config.from_name
    message["From"] = formataddr((sender_name, sender_email)) if sender_name else sender_email
    message["To"] = to
    message["Subject"] = subject
    for key, value in (headers or {}).items():
        message[key] = value
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    if config.provider == "zeptomail":
        _send_zeptomail(config, message, text_body, html_body)
    else:
        _send_smtp(config, message)
    logger.info("E-mail sent", extra={"to": to, "subject": subject, "provider": config.provider})


def deliver_email(to: str, subject: str, body: str) -> None:
    """Send immediately (the worker task, or the API when no worker is running)."""
    send(to, subject, body)


def deliver_message(
    to: str,
    subject: str,
    text: str,
    *,
    html_body: str | None = None,
    from_name: str | None = None,
    from_email: str | None = None,
    headers: dict[str, str] | None = None,
) -> None:
    """Send a (marketing) message with an optional HTML part and extra headers."""
    send(to, subject, text, html_body=html_body, from_name=from_name, from_email=from_email, headers=headers)


# ------------------------------------------------------------------ queueing


def _send_in_background(to: str, subject: str, body: str) -> None:
    def run() -> None:
        try:
            deliver_email(to, subject, body)
        except Exception:
            logger.exception("E-mail delivery failed", extra={"to": to, "subject": subject})

    threading.Thread(target=run, name="email", daemon=True).start()


def queue_email(to: str, subject: str, body: str, *, wait: bool = False) -> None:
    """Send an e-mail in the background. Call only after the database transaction has committed.

    The worker sends it when one is running (EMAIL_DELIVERY=auto) or always (queue); otherwise the API does.
    ``wait=True`` sends from the API before returning and raises MailDeliveryError on failure, so the caller
    can tell the person (sign-up uses this).
    """
    mode = get_settings().email_delivery
    if mode != "inline":
        from app.worker.dispatch import forget_worker_check, worker_available
        from app.worker.tasks import send_email_task  # local import: avoids a worker <-> service cycle

        if mode == "queue" or worker_available():
            try:
                send_email_task.delay(to, subject, body)
                return
            except Exception:
                logger.warning("Task queue unavailable; sending e-mail from the API", extra={"to": to})
                forget_worker_check()
    if wait:
        deliver_email(to, subject, body)
    elif get_settings().is_serverless:
        # A serverless function may be frozen once it responds: send before returning.
        try:
            deliver_email(to, subject, body)
        except Exception:
            logger.exception("E-mail delivery failed", extra={"to": to, "subject": subject})
    else:
        _send_in_background(to, subject, body)


def app_link(path: str) -> str:
    return get_settings().public_app_url.rstrip("/") + path


# ------------------------------------------------------------------ e-mail after commit

_AFTER_COMMIT = "mail_after_commit"


def queue_after_commit(db: Session, to: str, subject: str, body: str) -> None:
    """Send once the surrounding transaction commits; nothing is sent if it rolls back (a refused
    action must not tell a client that something is waiting for them)."""
    db.info.setdefault(_AFTER_COMMIT, []).append((to, subject, body))


@event.listens_for(Session, "after_commit")
def _send_after_commit(session: Session) -> None:
    for to, subject, body in session.info.pop(_AFTER_COMMIT, None) or []:
        # The change is saved; a mail outage is logged by the sender, not raised here.
        with contextlib.suppress(Exception):
            queue_email(to, subject, body)


@event.listens_for(Session, "after_rollback")
def _drop_after_rollback(session: Session) -> None:
    session.info.pop(_AFTER_COMMIT, None)

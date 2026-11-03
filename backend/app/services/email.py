"""Outgoing e-mail. Delivery runs in the Celery worker; the console backend logs instead of sending."""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger("app.email")


def deliver_email(to: str, subject: str, body: str) -> None:
    """Send immediately (called by the worker task)."""
    settings = get_settings()
    if settings.email_backend == "console":
        logger.info("E-mail (console backend)", extra={"to": to, "subject": subject, "body": body})
        return

    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        if settings.smtp_starttls:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        smtp.send_message(message)
    logger.info("E-mail sent", extra={"to": to, "subject": subject})


def queue_email(to: str, subject: str, body: str) -> None:
    """Hand the e-mail to the worker. Call only after the database transaction has committed."""
    from app.worker.tasks import send_email_task  # local import: avoids a worker <-> service cycle

    send_email_task.delay(to, subject, body)


def app_link(path: str) -> str:
    return get_settings().public_app_url.rstrip("/") + path

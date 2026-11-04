"""The firm's calendar date. Servers run on UTC, but a date a person sees ("opened today", a lodgement
date, a BAS due date) belongs to the firm's time zone: at 9am in Sydney it is still yesterday in UTC."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def local_now() -> datetime:
    return datetime.now(ZoneInfo(get_settings().timezone))


def local_today() -> date:
    return local_now().date()

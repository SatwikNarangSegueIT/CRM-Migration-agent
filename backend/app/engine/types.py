"""Field types: validation and normalisation of values before they are stored in `records.data`.

Stored representations (JSON):
  text-like, picklist, auto_number -> str        number / percent / currency -> number (exact decimal)
  date -> "YYYY-MM-DD"   datetime -> ISO-8601 UTC "...Z"   time -> "HH:MM[:SS]"   checkbox -> bool
  multi_picklist -> [str]   lookup / master_detail -> record id (str)
  address -> {"street", "city", "state", "postcode", "country"}   encrypted_text -> {"enc": token}
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime, time
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.auth.security import decrypt_field, encrypt_field
from app.engine.meta import FieldMeta

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ADDRESS_PARTS = ("street", "city", "state", "postcode", "country")
DEFAULT_MAX_LENGTH = {"text": 255, "textarea": 4000, "long_text": 32000, "email": 254, "phone": 40, "url": 1000}
DEFAULT_SCALE = {"number": 0, "percent": 2, "currency": 2}
MAX_DIGITS = 15  # exact round-trip through JSON numbers


class FieldValueError(ValueError):
    pass


def to_decimal(value: Any) -> Decimal | None:
    """Stored numbers come back from JSONB as int/float; convert without binary noise."""
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise FieldValueError("Enter a number.")
    try:
        return Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError) as exc:
        raise FieldValueError("Enter a number.") from exc


def money(value: Any) -> Decimal:
    """Round half-up to the cent (plan v3, section 8)."""
    d = to_decimal(value) or Decimal(0)
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def decimal_to_json(value: Decimal) -> int | float:
    """JSON number with the decimal's exact digits (PostgreSQL stores JSONB numbers as numeric)."""
    if value == value.to_integral_value() and value.as_tuple().exponent >= 0:
        return int(value)
    return float(value)  # repr() of a float is the shortest string that round-trips (<= 15 digits)


def normalize_phone(raw: str) -> str:
    """E.164 when the number is parseable (Australian defaults), otherwise as entered."""
    digits = re.sub(r"[\s\-().]", "", raw)
    if re.fullmatch(r"\+\d{8,15}", digits):
        return digits
    if re.fullmatch(r"0\d{9}", digits):
        return "+61" + digits[1:]
    if re.fullmatch(r"61\d{9}", digits):
        return "+" + digits
    return raw.strip()


def parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError as exc:
        raise FieldValueError("Enter a date (YYYY-MM-DD).") from exc


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise FieldValueError("Enter a date and time (ISO 8601).") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def format_datetime(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _text(f: FieldMeta, value: Any) -> str:
    if not isinstance(value, str | int | float) or isinstance(value, bool):
        raise FieldValueError("Enter text.")
    s = str(value)
    s = s.strip() if f.type in ("text", "email", "phone", "url") else s
    max_len = int(f.options.get("max_length") or DEFAULT_MAX_LENGTH.get(f.type, 255))
    if len(s) > max_len:
        raise FieldValueError(f"Use at most {max_len} characters.")
    return s


def normalize(f: FieldMeta, value: Any) -> Any:
    """Validate `value` for field `f`; return the stored representation (None = blank)."""
    if value is None or (isinstance(value, str) and value.strip() == "" and f.type != "long_text"):
        return None
    t = f.type
    if t in ("text", "textarea", "long_text"):
        s = _text(f, value)
        return s or None
    if t == "email":
        s = _text(f, value).lower()
        if not EMAIL_RE.match(s):
            raise FieldValueError("Enter a valid e-mail address.")
        return s
    if t == "phone":
        return normalize_phone(_text(f, value))
    if t == "url":
        s = _text(f, value)
        if not re.match(r"^https?://", s, re.IGNORECASE):
            s = "https://" + s
        if " " in s or "." not in s:
            raise FieldValueError("Enter a valid web address.")
        return s
    if t in ("number", "percent", "currency"):
        d = to_decimal(value)
        assert d is not None
        if not d.is_finite():
            raise FieldValueError("Enter a number.")
        scale = int(f.options.get("scale", DEFAULT_SCALE[t]))
        d = d.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)
        if len(d.as_tuple().digits) > MAX_DIGITS:
            raise FieldValueError("Number is too large.")
        if f.options.get("min") is not None and d < Decimal(str(f.options["min"])):
            raise FieldValueError(f"Must be at least {f.options['min']}.")
        if f.options.get("max") is not None and d > Decimal(str(f.options["max"])):
            raise FieldValueError(f"Must be at most {f.options['max']}.")
        return decimal_to_json(d)
    if t == "date":
        return parse_date(value).isoformat()
    if t == "datetime":
        return format_datetime(parse_datetime(value))
    if t == "time":
        try:
            return time.fromisoformat(str(value).strip()).isoformat(timespec="minutes")
        except ValueError as exc:
            raise FieldValueError("Enter a time (HH:MM).") from exc
    if t == "checkbox":
        if isinstance(value, bool):
            return value
        if str(value).lower() in ("true", "1", "yes", "y"):
            return True
        if str(value).lower() in ("false", "0", "no", "n"):
            return False
        raise FieldValueError("Enter true or false.")
    if t == "picklist":
        s = str(value).strip()
        if s not in f.active_values():
            # Keep inactive values that are already stored; the record engine passes them through.
            raise FieldValueError(f"{s!r} is not a valid value.")
        return s
    if t == "multi_picklist":
        items = value if isinstance(value, list) else [v for v in str(value).split(";")]
        cleaned = [str(v).strip() for v in items if str(v).strip()]
        allowed = set(f.active_values())
        bad = [v for v in cleaned if v not in allowed]
        if bad:
            raise FieldValueError(f"{bad[0]!r} is not a valid value.")
        return list(dict.fromkeys(cleaned)) or None
    if t in ("lookup", "master_detail"):
        try:
            return str(uuid.UUID(str(value)))
        except ValueError as exc:
            raise FieldValueError("Choose a record.") from exc
    if t == "address":
        if not isinstance(value, dict):
            raise FieldValueError("Enter an address.")
        out = {k: str(value.get(k) or "").strip()[:255] for k in ADDRESS_PARTS}
        return out if any(out.values()) else None
    if t == "encrypted_text":
        s = _text(f, value)
        return {"enc": encrypt_field(s)}
    if t == "auto_number":
        raise FieldValueError("This field is set automatically.")
    raise FieldValueError(f"Unsupported field type {t!r}.")


def present(f: FieldMeta, stored: Any) -> Any:
    """Stored value -> API value."""
    if stored is None:
        return None
    if f.type == "encrypted_text":
        if isinstance(stored, dict) and "enc" in stored:
            try:
                return decrypt_field(str(stored["enc"]))
            except Exception:  # noqa: BLE001 - key rotation or corruption must not break the page
                return None
        return None
    return stored


def display_text(f: FieldMeta, stored: Any) -> str:
    """Plain-text rendering (search vector, CSV export, e-mail merge)."""
    value = present(f, stored)
    if value is None:
        return ""
    if f.type == "address" and isinstance(value, dict):
        return ", ".join(str(value[k]) for k in ADDRESS_PARTS if value.get(k))
    if f.type == "multi_picklist" and isinstance(value, list):
        return "; ".join(str(v) for v in value)
    if f.type == "checkbox":
        return "Yes" if value else "No"
    if f.type in ("picklist",):
        for v in f.picklist_values:
            if v["value"] == value:
                return str(v.get("label") or value)
    return str(value)

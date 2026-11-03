"""Filter AST -> SQL (plan v3, section 14: "user-supplied filters are parsed into an AST, never concatenated").

AST:   {"logic": "and" | "or", "conditions": [Condition | AST, ...]}
       Condition = {"field": api_name, "op": operator, "value": any}
Field names are checked against metadata; values are always bound parameters.

Relative date values (plan section 12): TODAY, YESTERDAY, TOMORROW, THIS/LAST/NEXT_WEEK|MONTH|QUARTER|YEAR,
LAST_N_DAYS:n, NEXT_N_DAYS:n. "$me" as a value means the current user (owner, created by...).
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Boolean,
    ColumnElement,
    Date,
    DateTime,
    Numeric,
    String,
    and_,
    cast,
    false,
    func,
    literal,
    not_,
    or_,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.core.errors import AppError
from app.db.session import escape_like
from app.engine.meta import FieldMeta, ObjectMeta
from app.engine.types import FieldValueError, normalize, parse_date, parse_datetime, to_decimal

if TYPE_CHECKING:
    from app.engine.sharing import SharingContext

OPERATORS = (
    "equals",
    "not_equals",
    "contains",
    "not_contains",
    "starts_with",
    "gt",
    "gte",
    "lt",
    "lte",
    "between",
    "in",
    "not_in",
    "is_null",
    "is_not_null",
    "includes",
    "excludes",
)
SYSTEM_COLUMNS = {
    "id": "id",
    "name": "name",
    "record_number": "record_number",
    "owner_id": "owner_id",
    "created_at": "created_at",
    "created_by_id": "created_by_id",
    "updated_at": "updated_at",
    "updated_by_id": "updated_by_id",
}
MAX_DEPTH = 5
MAX_CONDITIONS = 50
_RELATIVE_N = re.compile(r"^(LAST|NEXT)_N_DAYS:(\d{1,4})$")


class FilterError(AppError):
    status_code = 422
    code = "invalid_filter"


def _sort_type(f: FieldMeta) -> str:
    if f.type in ("number", "percent", "currency"):
        return "numeric"
    if f.type == "date":
        return "date"
    if f.type in ("datetime",):
        return "datetime"
    if f.type == "checkbox":
        return "bool"
    if f.type in ("id", "owner", "user", "lookup", "master_detail"):
        return "id"
    if f.type == "multi_picklist":
        return "array"
    return "text"


def field_expr(f: FieldMeta, r: Any) -> Any:
    """SQL expression for a field on record alias `r` (matches the engine's expression indexes)."""
    if f.is_system:
        col = getattr(r, SYSTEM_COLUMNS[f.api_name])
        if f.api_name in ("id", "owner_id", "created_by_id", "updated_by_id"):
            return cast(col, String)
        return col
    kind = _sort_type(f)
    if kind == "array":
        return r.data[f.api_name]
    if f.type == "address":
        return cast(r.data[f.api_name], String)
    raw = r.data[f.api_name].astext
    if kind == "numeric":
        return cast(raw, Numeric)
    if kind == "date":
        return cast(raw, Date)
    if kind == "datetime":
        return cast(raw, DateTime(timezone=True))
    if kind == "bool":
        return cast(raw, Boolean)
    return raw


def sort_expr(f: FieldMeta, r: Any) -> Any:
    expr = field_expr(f, r)
    if _sort_type(f) == "text" and not f.is_system:
        return func.lower(expr)
    if f.api_name == "name":
        return func.lower(expr)
    return expr


def _period(token: str, today: date) -> tuple[date, date] | None:
    """Inclusive date range for a relative token."""
    token = token.upper()
    if token == "TODAY":
        return today, today
    if token == "YESTERDAY":
        d = today - timedelta(days=1)
        return d, d
    if token == "TOMORROW":
        d = today + timedelta(days=1)
        return d, d
    m = _RELATIVE_N.match(token)
    if m:
        n = int(m.group(2))
        if m.group(1) == "LAST":
            return today - timedelta(days=n), today
        return today, today + timedelta(days=n)
    parts = token.split("_", 1)
    if len(parts) != 2 or parts[0] not in ("THIS", "LAST", "NEXT"):
        return None
    shift = {"THIS": 0, "LAST": -1, "NEXT": 1}[parts[0]]
    unit = parts[1]
    if unit == "WEEK":
        start = today - timedelta(days=today.weekday()) + timedelta(weeks=shift)
        return start, start + timedelta(days=6)
    if unit == "MONTH":
        month_index = today.year * 12 + today.month - 1 + shift
        y, mth = divmod(month_index, 12)
        start = date(y, mth + 1, 1)
        nxt = date(y + (mth + 1) // 12, (mth + 1) % 12 + 1, 1)
        return start, nxt - timedelta(days=1)
    if unit == "QUARTER":
        q_index = today.year * 4 + (today.month - 1) // 3 + shift
        y, q = divmod(q_index, 4)
        start = date(y, q * 3 + 1, 1)
        end_month_index = y * 12 + q * 3 + 3
        ey, em = divmod(end_month_index, 12)
        return start, date(ey, em + 1, 1) - timedelta(days=1)
    if unit == "YEAR":
        y = today.year + shift
        return date(y, 1, 1), date(y, 12, 31)
    return None


def relative_range(value: Any, tz: str) -> tuple[date, date] | None:
    if not isinstance(value, str):
        return None
    return _period(value.strip(), datetime.now(ZoneInfo(tz)).date())


class _Compiler:
    def __init__(self, meta: ObjectMeta, r: Any, user_id: uuid.UUID | None, tz: str) -> None:
        self.meta = meta
        self.r = r
        self.user_id = user_id
        self.tz = tz
        self.count = 0

    def _literal(self, f: FieldMeta, value: Any) -> Any:
        """Coerce a filter value to the field's SQL type (validated, bound)."""
        if value == "$me":
            if self.user_id is None:
                raise FilterError("'$me' is not available here.")
            return str(self.user_id)
        kind = _sort_type(f)
        try:
            if kind == "numeric":
                d = to_decimal(value)
                if d is None:
                    raise FieldValueError("Enter a number.")
                return d
            if kind == "date":
                return parse_date(value)
            if kind == "datetime":
                return parse_datetime(value)
            if kind == "bool":
                return bool(normalize(FieldMeta(api_name="x", label="x", type="checkbox"), value))
            if kind == "id":
                return str(uuid.UUID(str(value)))
        except (FieldValueError, ValueError) as exc:
            raise FilterError(f"{f.label}: {exc}", fields={f.api_name: str(exc)}) from exc
        if not isinstance(value, str | int | float) or isinstance(value, bool):
            raise FilterError(f"{f.label}: enter text.", fields={f.api_name: "Enter text"})
        return str(value)

    def _date_bounds(self, f: FieldMeta, value: Any) -> tuple[Any, Any] | None:
        """For date/datetime fields and relative tokens: (inclusive start, exclusive end) values."""
        kind = _sort_type(f)
        if kind not in ("date", "datetime"):
            return None
        rng = relative_range(value, self.tz)
        if rng is None:
            return None
        start, end = rng
        if kind == "date":
            return start, end + timedelta(days=1)
        zone = ZoneInfo(self.tz)
        return (
            datetime.combine(start, time.min, zone),
            datetime.combine(end + timedelta(days=1), time.min, zone),
        )

    def condition(self, cond: dict[str, Any]) -> ColumnElement[bool]:
        self.count += 1
        if self.count > MAX_CONDITIONS:
            raise FilterError(f"Use at most {MAX_CONDITIONS} filter conditions.")
        name = cond.get("field")
        op = cond.get("op", "equals")
        value = cond.get("value")
        if not isinstance(name, str) or name not in self.meta.fields:
            raise FilterError(f"Unknown filter field {name!r}.")
        f = self.meta.fields[name]
        if not f.filterable or f.type == "encrypted_text":
            raise FilterError(f"{f.label} cannot be used in filters.")
        if op not in OPERATORS:
            raise FilterError(f"Unknown filter operator {op!r}.")
        expr = field_expr(f, self.r)
        kind = _sort_type(f)

        if op in ("is_null", "is_not_null"):
            if f.is_system:
                blank = getattr(self.r, SYSTEM_COLUMNS[name]).is_(None)
            else:
                blank = or_(
                    self.r.data[name].is_(None),
                    self.r.data[name] == cast(literal("null"), JSONB),
                )
            return blank if op == "is_null" else not_(blank)

        if kind == "array":
            if op not in ("includes", "excludes", "equals", "not_equals"):
                raise FilterError(f"{f.label} supports includes / excludes.")
            values = value if isinstance(value, list) else [value]
            has_any = or_(*(self.r.data[name].contains([str(v)]) for v in values))
            return has_any if op in ("includes", "equals") else not_(func.coalesce(has_any, false()))

        if op in ("in", "not_in"):
            values = value if isinstance(value, list) else [value]
            if not values:
                return false() if op == "in" else true()
            lits = [self._literal(f, v) for v in values]
            clause = (func.lower(expr).in_([str(v).lower() for v in lits]) if kind == "text" else expr.in_(lits))
            return clause if op == "in" else or_(not_(clause), expr.is_(None))

        if op in ("contains", "not_contains", "starts_with"):
            if kind not in ("text",) and f.type != "address":
                raise FilterError(f"{f.label} does not support '{op}'.")
            text_value = escape_like(str(value or ""))
            pattern = f"{text_value}%" if op == "starts_with" else f"%{text_value}%"
            clause = expr.ilike(pattern, escape="\\")
            return clause if op != "not_contains" else or_(not_(clause), expr.is_(None))

        if op == "between":
            if not isinstance(value, list | tuple) or len(value) != 2:
                raise FilterError(f"{f.label}: 'between' needs two values.")
            lo, hi = (self._literal(f, v) for v in value)
            return and_(expr >= lo, expr <= hi)

        bounds = self._date_bounds(f, value)
        if bounds is not None:
            start, end = bounds
            if op == "equals":
                return and_(expr >= start, expr < end)
            if op == "not_equals":
                return or_(expr < start, expr >= end, expr.is_(None))
            if op == "gt":
                return expr >= end
            if op == "gte":
                return expr >= start
            if op == "lt":
                return expr < start
            if op == "lte":
                return expr < end
            raise FilterError(f"{f.label} does not support '{op}'.")

        if value is None:
            raise FilterError(f"{f.label}: enter a value.", fields={name: "Enter a value"})
        lit = self._literal(f, value)
        if kind == "text":
            if op == "equals":
                return func.lower(expr) == str(lit).lower()
            if op == "not_equals":
                return or_(func.lower(expr) != str(lit).lower(), expr.is_(None))
        if op == "equals":
            return expr == lit
        if op == "not_equals":
            return or_(expr != lit, expr.is_(None))
        if kind == "bool" or kind == "id":
            raise FilterError(f"{f.label} does not support '{op}'.")
        ops = {"gt": expr > lit, "gte": expr >= lit, "lt": expr < lit, "lte": expr <= lit}
        if op in ops:
            return ops[op]
        raise FilterError(f"{f.label} does not support '{op}'.")

    def node(self, node: dict[str, Any], depth: int = 0) -> ColumnElement[bool]:
        if depth > MAX_DEPTH:
            raise FilterError("Filters are nested too deeply.")
        if not isinstance(node, dict):
            raise FilterError("Invalid filter.")
        if "field" in node:
            return self.condition(node)
        logic = str(node.get("logic", "and")).lower()
        if logic not in ("and", "or"):
            raise FilterError("Filter logic must be 'and' or 'or'.")
        children = node.get("conditions") or []
        if not isinstance(children, list):
            raise FilterError("Invalid filter.")
        clauses = [self.node(c, depth + 1) for c in children]
        if not clauses:
            return true()
        return and_(*clauses) if logic == "and" else or_(*clauses)


def compile_filter(
    meta: ObjectMeta,
    ast: dict[str, Any] | None,
    r: Any,
    ctx: SharingContext | None,
    *,
    user_id: uuid.UUID | None = None,
    tz: str = "Australia/Sydney",
) -> ColumnElement[bool]:
    if not ast:
        return true()
    uid = user_id if user_id is not None else (ctx.user_id if ctx is not None else None)
    return _Compiler(meta, r, uid, tz).node(ast)


def filter_fields(ast: dict[str, Any] | None) -> set[str]:
    """Every field name referenced by a filter (for field-level security checks)."""
    out: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "field" in node:
                out.add(str(node["field"]))
            for child in node.get("conditions") or []:
                walk(child)

    walk(ast)
    return out


def coerce_cursor_value(f: FieldMeta, value: Any) -> Any:
    if value is None:
        return None
    kind = _sort_type(f)
    if f.api_name == "name" or (kind == "text" and not f.is_system):
        return str(value)
    if kind == "numeric":
        return Decimal(str(value))
    if kind == "date":
        return date.fromisoformat(str(value))
    if kind == "datetime" or f.api_name in ("created_at", "updated_at"):
        return parse_datetime(value)
    if kind == "bool":
        return bool(value)
    return str(value)

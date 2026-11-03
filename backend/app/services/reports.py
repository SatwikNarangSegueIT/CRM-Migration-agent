"""Reports and dashboards (plan v3, section 12).

A report runs over one object through the record engine, so users only see rows they may read and
fields they may see. Columns and groupings may follow one lookup ("account.industry" on opportunities),
which gives report types such as Accounts with Opportunities or Cases with Contacts. Formats: tabular,
summary (up to two row groupings) and matrix (rows x one column grouping). Aggregates: count, sum, avg,
min, max. Dates can be bucketed by day/week/month/quarter/year; "age:<date field>" buckets overdue
items (Current, 1-30, 31-60, 61-90, 90+ days).
"""

from __future__ import annotations

import contextlib
import csv
import io
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, String, and_, case, cast, func, literal, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.engine.filters import FilterError, compile_filter, field_expr, filter_fields
from app.engine.meta import FieldMeta, ObjectMeta
from app.engine.records import RecordService
from app.engine.types import display_text
from app.models import Dashboard, Queue, Record, Report, ReportFolder, ReportSchedule, User
from app.security.catalog import FieldAccess, SystemPermission

MAX_ROWS = 2000
MAX_GROUPS = 500
STATEMENT_TIMEOUT_MS = 15_000
GRANULARITIES = ("day", "week", "month", "quarter", "year")
AGGREGATES = ("count", "sum", "avg", "min", "max")
AGE_BUCKETS = ("Current", "1-30 days", "31-60 days", "61-90 days", "90+ days")


class ReportError(AppError):
    status_code = 422
    code = "invalid_report"


# ------------------------------------------------------------------ access to reports


def folder_visible(svc: RecordService, folder: ReportFolder | None, owner_id: uuid.UUID | None) -> bool:
    if svc.policy.is_system_admin or svc.policy.object("report").view_all:
        return True
    if folder is None:
        return owner_id == svc.user_id
    if folder.visibility == "public" or folder.owner_id == svc.user_id:
        return True
    if folder.visibility == "shared":
        return str(svc.policy.profile_id) in (folder.shared_profile_ids or []) or (
            svc.policy.role_id is not None and str(svc.policy.role_id) in (folder.shared_role_ids or [])
        )
    return False


def can_manage(
    svc: RecordService, folder: ReportFolder | None, owner_id: uuid.UUID | None, obj: str = "report"
) -> bool:
    access = svc.policy.object(obj)
    if svc.policy.is_system_admin or access.modify_all:
        return True
    if not access.edit:
        return False
    if folder is not None and folder.visibility != "private":
        return svc.policy.has(SystemPermission.MANAGE_PUBLIC_REPORTS) or folder.owner_id == svc.user_id
    return owner_id == svc.user_id


def get_report(svc: RecordService, report_id: uuid.UUID) -> Report:
    if not svc.policy.object("report").read:
        raise PermissionDeniedError("You don't have access to reports.")
    report = svc.db.get(Report, report_id)
    if report is None:
        raise NotFoundError("Report not found.")
    folder = svc.db.get(ReportFolder, report.folder_id) if report.folder_id else None
    if not folder_visible(svc, folder, report.owner_id):
        raise NotFoundError("Report not found.")
    return report


def get_dashboard(svc: RecordService, dashboard_id: uuid.UUID) -> Dashboard:
    if not svc.policy.object("dashboard").read:
        raise PermissionDeniedError("You don't have access to dashboards.")
    dash = svc.db.get(Dashboard, dashboard_id)
    if dash is None:
        raise NotFoundError("Dashboard not found.")
    folder = svc.db.get(ReportFolder, dash.folder_id) if dash.folder_id else None
    if not folder_visible(svc, folder, dash.owner_id):
        raise NotFoundError("Dashboard not found.")
    return dash


# ------------------------------------------------------------------ definition helpers


class _Ref:
    """A report column/grouping: a field on the base object or one lookup hop away."""

    def __init__(
        self, path: str, meta: ObjectMeta, field: FieldMeta, via: FieldMeta | None, target: ObjectMeta | None
    ):
        self.path = path
        self.meta = meta
        self.field = field
        self.via = via
        self.target = target

    @property
    def label(self) -> str:
        return f"{self.via.label}: {self.field.label}" if self.via else self.field.label


class Runner:
    def __init__(self, svc: RecordService, report_object: str, definition: dict[str, Any]) -> None:
        self.svc = svc
        self.meta = svc.object(report_object)
        if not self.meta.allow_reports:
            raise ReportError(f"{self.meta.plural_label} aren't available in reports.")
        self.d = definition or {}
        self.joins: dict[str, Any] = {}

    def ref(self, path: str) -> _Ref:
        if path.startswith("age:"):
            r = self.ref(path[4:])
            if r.field.type not in ("date", "datetime"):
                raise ReportError("Aging needs a date field.")
            return r
        head, _, tail = path.partition(".")
        f = self.meta.fields.get(head)
        if f is None or self.svc.field_access(self.meta, f) is FieldAccess.HIDDEN:
            raise ReportError(f"Unknown field {path!r}.")
        if not tail:
            return _Ref(path, self.meta, f, None, None)
        if not f.is_lookup or len(f.targets) != 1:
            raise ReportError(f"{f.label} can't be followed in reports.")
        target = self.svc.object(f.targets[0])
        tf = target.fields.get(tail)
        if tf is None or self.svc.field_access(target, tf) is FieldAccess.HIDDEN:
            raise ReportError(f"Unknown field {path!r}.")
        return _Ref(path, target, tf, f, target)

    def alias_for(self, r: _Ref) -> Any:
        if r.via is None:
            return Record
        if r.via.api_name not in self.joins:
            self.joins[r.via.api_name] = aliased(Record, name=f"j_{r.via.api_name}")
        return self.joins[r.via.api_name]

    def expr(self, path: str) -> Any:
        r = self.ref(path)
        alias = self.alias_for(r)
        base = field_expr(r.field, alias)
        if path.startswith("age:"):
            day = cast(base, Date)
            age = func.current_date() - day
            return case(
                (day.is_(None), literal(None)),
                (age <= 0, literal(AGE_BUCKETS[0])),
                (age <= 30, literal(AGE_BUCKETS[1])),
                (age <= 60, literal(AGE_BUCKETS[2])),
                (age <= 90, literal(AGE_BUCKETS[3])),
                else_=literal(AGE_BUCKETS[4]),
            )
        gran = (self.d.get("date_granularity") or {}).get(path)
        if gran:
            if gran not in GRANULARITIES or (
                r.field.type not in ("date", "datetime", "created_at", "updated_at")
                and not r.field.api_name.endswith("_at")
            ):
                raise ReportError("Date grouping needs a date field.")
            return cast(func.date_trunc(gran, base), Date)
        return base

    def base_statement(self, *columns: Any) -> Any:
        scope = self.d.get("scope", "all")
        if scope not in ("all", "mine", "team"):
            raise ReportError("Invalid scope.")
        stmt = self.svc.base_query(self.meta, scope=scope).with_only_columns(*columns)
        filters = self.d.get("filters")
        if filters:
            self.svc.check_readable_fields(self.meta, filter_fields(filters))
            stmt = stmt.where(
                compile_filter(
                    self.meta, filters, Record, None, user_id=self.svc.user_id, tz=self.svc.time_zone
                )
            )
        for via_name, alias in self.joins.items():
            via = self.meta.fields[via_name]
            target = via.targets[0]
            readable = (
                self.svc.sharing.where_readable(target, alias) if not self.svc.system else literal(True)
            )
            stmt = stmt.outerjoin(
                alias,
                and_(
                    cast(alias.id, String) == Record.data[via_name].astext,
                    alias.object_api_name == target,
                    alias.is_deleted.is_(False),
                    readable,
                ),
            )
        return stmt

    # -------------------------------------------------------------- formats

    def aggregates(self) -> list[dict[str, Any]]:
        aggs = self.d.get("aggregates") or [{"op": "count"}]
        out = []
        for a in aggs[:10]:
            op = a.get("op", "count")
            if op not in AGGREGATES:
                raise ReportError(f"Unknown aggregate {op!r}.")
            if op != "count":
                r = self.ref(str(a.get("field")))
                if op in ("sum", "avg") and r.field.type not in ("number", "percent", "currency"):
                    raise ReportError(f"{r.label} can't be summed or averaged.")
            out.append(
                {"op": op, "field": a.get("field"), "key": op if op == "count" else f"{op}:{a.get('field')}"}
            )
        return out

    def agg_expr(self, a: dict[str, Any]) -> Any:
        if a["op"] == "count":
            return func.count(Record.id)
        expr = self.expr(a["field"])
        if a["op"] == "sum":
            return func.sum(expr)
        if a["op"] == "avg":
            return func.avg(expr)
        if a["op"] == "min":
            return func.min(expr)
        return func.max(expr)

    def run(self) -> dict[str, Any]:
        fmt = self.d.get("format", "tabular")
        session = self.svc.db
        session.execute(select(func.set_config("statement_timeout", str(STATEMENT_TIMEOUT_MS), True)))
        if fmt == "tabular":
            result = self.tabular()
        elif fmt in ("summary", "matrix"):
            result = self.grouped(matrix=fmt == "matrix")
        else:
            raise ReportError("Format is tabular, summary or matrix.")
        session.execute(select(func.set_config("statement_timeout", "0", True)))
        return result

    def tabular(self) -> dict[str, Any]:
        columns = list(self.d.get("columns") or self.meta.list_columns or ["name"])[:50]
        refs = [self.ref(c) for c in columns]
        exprs = [self.expr(c).label(f"c{i}") for i, c in enumerate(columns)]
        stmt = self.base_statement(Record.id, *exprs)
        for s in (self.d.get("sort") or [])[:3]:
            e = self.expr(str(s.get("field")))
            stmt = stmt.order_by(
                e.desc().nulls_last() if s.get("direction") == "desc" else e.asc().nulls_last()
            )
        stmt = stmt.order_by(Record.created_at.desc())
        limit = min(int(self.d.get("limit") or MAX_ROWS), MAX_ROWS)
        rows = self.svc.db.execute(stmt.limit(limit + 1)).all()
        truncated = len(rows) > limit
        rows = rows[:limit]
        labels = self._labels(refs, [[r[i + 1] for r in rows] for i in range(len(refs))])
        out_rows = []
        for r in rows:
            out_rows.append(
                {
                    "id": str(r[0]),
                    "cells": [self._cell(ref, r[i + 1], labels[i]) for i, ref in enumerate(refs)],
                }
            )
        totals = {}
        for a in self.aggregates():
            if a["op"] != "count":
                totals[a["key"]] = _num(self.svc.db.scalar(self.base_statement(self.agg_expr(a))))
        count = self.svc.db.scalar(self.base_statement(func.count(Record.id)))
        return {
            "format": "tabular",
            "columns": [
                {"key": c, "label": ref.label, "type": ref.field.type}
                for c, ref in zip(columns, refs, strict=True)
            ],
            "rows": out_rows,
            "truncated": truncated,
            "totals": {"count": int(count or 0), **totals},
        }

    def grouped(self, *, matrix: bool) -> dict[str, Any]:
        group_by = list(self.d.get("group_by") or [])
        if not group_by or len(group_by) > 2:
            raise ReportError("Group by one or two fields.")
        col_groups = list(self.d.get("group_columns") or []) if matrix else []
        if matrix and len(col_groups) != 1:
            raise ReportError("Matrix reports need one column grouping.")
        dims = group_by + col_groups
        refs = [self.ref(g) for g in dims]
        for g, ref in zip(dims, refs, strict=True):
            if ref.field.type in (
                "long_text",
                "address",
                "encrypted_text",
                "multi_picklist",
            ) and not g.startswith("age:"):
                raise ReportError(f"{ref.label} can't be grouped.")
        aggs = self.aggregates()
        dim_exprs = [self.expr(g).label(f"g{i}") for i, g in enumerate(dims)]
        agg_exprs = [self.agg_expr(a).label(f"a{i}") for i, a in enumerate(aggs)]
        stmt = self.base_statement(*dim_exprs, *agg_exprs).group_by(
            *[e.element if hasattr(e, "element") else e for e in dim_exprs]
        )
        sort = self.d.get("sort") or []
        if sort and str(sort[0].get("field")).startswith("agg:"):
            idx = next((i for i, a in enumerate(aggs) if a["key"] == sort[0]["field"][4:]), 0)
            e = agg_exprs[idx]
            stmt = stmt.order_by(e.desc() if sort[0].get("direction") == "desc" else e.asc())
        else:
            for e in dim_exprs:
                stmt = stmt.order_by(e.asc().nulls_last())
        rows = self.svc.db.execute(stmt.limit(MAX_GROUPS + 1)).all()
        truncated = len(rows) > MAX_GROUPS
        rows = rows[:MAX_GROUPS]
        n = len(dims)
        labels = self._labels(refs, [[r[i] for r in rows] for i in range(n)])
        groups: list[dict[str, Any]] = []
        for r in rows:
            keys = [self._key(r[i]) for i in range(n)]
            groups.append(
                {
                    "keys": keys,
                    "labels": [labels[i].get(self._key(r[i]), _plain(r[i])) for i in range(n)],
                    "values": {a["key"]: _num(r[n + j]) for j, a in enumerate(aggs)},
                }
            )
        if dims and all(d.startswith("age:") for d in dims[:1]):
            order = {b: i for i, b in enumerate(AGE_BUCKETS)}
            groups.sort(key=lambda g: order.get(g["keys"][0], 99))
        else:
            ordered = self._picklist_order(refs[0])
            if ordered and not sort:
                groups.sort(key=lambda g: ordered.get(g["keys"][0], 999))
        totals = {}
        for j, a in enumerate(aggs):
            totals[a["key"]] = _num(
                self.svc.db.scalar(
                    self.base_statement(
                        agg_exprs[j].element if hasattr(agg_exprs[j], "element") else agg_exprs[j]
                    )
                )
            )
        return {
            "format": "matrix" if matrix else "summary",
            "dimensions": [
                {
                    "key": g,
                    "label": ref.label + (" (age)" if g.startswith("age:") else ""),
                    "type": ref.field.type,
                }
                for g, ref in zip(dims, refs, strict=True)
            ],
            "row_dimensions": len(group_by),
            "aggregates": [
                {"key": a["key"], "op": a["op"], "field": a["field"], "label": self._agg_label(a)}
                for a in aggs
            ],
            "groups": groups,
            "truncated": truncated,
            "totals": totals,
            "chart": self.d.get("chart"),
        }

    # -------------------------------------------------------------- labels

    def _agg_label(self, a: dict[str, Any]) -> str:
        if a["op"] == "count":
            return "Record Count"
        return f"{a['op'].capitalize()} of {self.ref(a['field']).label}"

    def _picklist_order(self, ref: _Ref) -> dict[Any, int]:
        if ref.field.type != "picklist":
            return {}
        return {v["value"]: i for i, v in enumerate(ref.field.picklist_values)}

    @staticmethod
    def _key(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, datetime | date):
            return value.isoformat()
        if isinstance(value, uuid.UUID):
            return str(value)
        return value

    def _labels(self, refs: list[_Ref], values: list[list[Any]]) -> list[dict[Any, str]]:
        out: list[dict[Any, str]] = []
        for ref, vals in zip(refs, values, strict=True):
            f = ref.field
            mapping: dict[Any, str] = {}
            keys = {self._key(v) for v in vals if v is not None}
            if (f.api_name in ("owner_id", "created_by_id", "updated_by_id") or f.type == "user") and keys:
                ids = []
                for k in keys:
                    try:
                        ids.append(uuid.UUID(str(k)))
                    except ValueError:
                        continue
                for uid, name in self.svc.db.execute(
                    select(User.id, User.name).where(User.id.in_(ids))
                ).all():
                    mapping[str(uid)] = name
                for qid, name in self.svc.db.execute(
                    select(Queue.id, Queue.name).where(Queue.id.in_(ids))
                ).all():
                    mapping[str(qid)] = name
            elif f.is_lookup and keys:
                ids = [uuid.UUID(str(k)) for k in keys]
                visible: set[uuid.UUID] = set()
                for target in f.targets:
                    visible |= self.svc.visible_ids(target, ids)
                for rid, name in self.svc.db.execute(
                    select(Record.id, Record.name).where(Record.id.in_(visible))
                ).all():
                    mapping[str(rid)] = name
            elif f.type in ("picklist",):
                for v in f.picklist_values:
                    mapping[v["value"]] = v.get("label", v["value"])
            elif f.type == "checkbox":
                mapping[True] = "Yes"
                mapping[False] = "No"
            out.append(mapping)
        return out

    def _cell(self, ref: _Ref, value: Any, labels: dict[Any, str]) -> dict[str, Any]:
        key = self._key(value)
        f = ref.field
        if f.is_lookup or f.type == "user" or f.api_name in ("owner_id", "created_by_id", "updated_by_id"):
            label = labels.get(key)
            return {"value": key if label else None, "label": label or ""}
        if f.type == "encrypted_text":
            return {"value": None, "label": ""}
        if f.type in ("address", "multi_picklist"):
            return {"value": value, "label": display_text(f, value)}
        return {"value": key, "label": labels.get(key, _plain(value))}


def _num(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(round(value, 4))
    if isinstance(value, int | float):
        return value
    return None


def _plain(value: Any) -> str:
    if value is None:
        return "(blank)"
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def validate_definition(svc: RecordService, object_api: str, definition: dict[str, Any]) -> None:
    """Dry-run the definition (also proves the user may see every referenced field)."""
    runner = Runner(svc, object_api, {**definition, "limit": 1})
    try:
        runner.run()
    except (FilterError, ReportError):
        raise
    except AppError:
        raise
    except Exception as exc:
        svc.db.rollback()
        raise ReportError(f"This report can't be run: {exc.__class__.__name__}.") from exc


def run_report(svc: RecordService, report: Report, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    definition = {**(report.definition or {}), **(overrides or {})}
    result = Runner(svc, report.object_api_name, definition).run()
    report.last_run_at = datetime.now(UTC)
    return {
        "report": {"id": str(report.id), "name": report.name, "object": report.object_api_name},
        "run_at": report.last_run_at,
        **result,
    }


def to_csv(result: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    if result["format"] == "tabular":
        w.writerow([c["label"] for c in result["columns"]])
        for row in result["rows"]:
            w.writerow([_csv_safe(c["label"]) for c in row["cells"]])
    else:
        w.writerow([d["label"] for d in result["dimensions"]] + [a["label"] for a in result["aggregates"]])
        for g in result["groups"]:
            w.writerow(
                [_csv_safe(lbl) for lbl in g["labels"]]
                + [g["values"].get(a["key"]) for a in result["aggregates"]]
            )
    return buf.getvalue()


def _csv_safe(value: Any) -> str:
    """Neutralise spreadsheet formula injection."""
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


# ------------------------------------------------------------------ schedules


def next_run(frequency: str, after: datetime) -> datetime:
    if frequency == "daily":
        return after + timedelta(days=1)
    if frequency == "weekly":
        return after + timedelta(weeks=1)
    month = after.month % 12 + 1
    year = after.year + (1 if month == 1 else 0)
    return after.replace(year=year, month=month, day=min(after.day, 28))


def run_due_schedules(db: Session, now: datetime | None = None) -> int:
    from app.security.policy import load_policy
    from app.services.email import queue_email

    now = now or datetime.now(UTC)
    due = db.scalars(
        select(ReportSchedule).where(ReportSchedule.next_run_at <= now).with_for_update(skip_locked=True)
    ).all()
    sent = 0
    outgoing: list[tuple[str, str, str]] = []
    for sched in due:
        owner = db.get(User, sched.owner_id)
        report = db.get(Report, sched.report_id)
        sched.last_run_at = now
        sched.next_run_at = next_run(sched.frequency, now)
        if owner is None or not owner.is_active or report is None:
            continue
        svc = RecordService.for_user(db, owner, load_policy(db, owner))
        try:
            result = run_report(svc, get_report(svc, report.id))
        except AppError:
            continue
        body = f"{report.name}\nRun {now:%d %b %Y %H:%M} UTC as {owner.name}.\n\n{to_csv(result)}"
        for to in sched.recipients or [owner.email]:
            outgoing.append((to, f"Scheduled report: {report.name}", body))
        sent += 1
    db.commit()
    for to, subject, body in outgoing:
        # The schedule has already advanced; a broker outage must not fail the job.
        with contextlib.suppress(Exception):
            queue_email(to, subject, body)
    return sent


def available_columns(svc: RecordService, object_api: str) -> list[dict[str, Any]]:
    """Fields for the report builder, including one lookup hop."""
    meta = svc.object(object_api)
    out = []
    for f in svc.readable_fields(meta):
        out.append({"key": f.api_name, "label": f.label, "type": f.type, "group": meta.label})
    for f in svc.readable_fields(meta):
        if not f.is_lookup or len(f.targets) != 1 or f.targets[0] not in svc.registry.objects:
            continue
        target = svc.registry.get(f.targets[0])
        if not svc.policy.object(target.api_name).read:
            continue
        for tf in svc.readable_fields(target):
            if tf.is_system and tf.api_name not in ("name", "owner_id", "created_at"):
                continue
            out.append(
                {
                    "key": f"{f.api_name}.{tf.api_name}",
                    "label": f"{f.label}: {tf.label}",
                    "type": tf.type,
                    "group": f.label,
                }
            )
    return out


__all__ = ["or_"]

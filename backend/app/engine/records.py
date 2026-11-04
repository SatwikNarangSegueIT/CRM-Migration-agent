"""The record engine (plan v3, sections 3, 7 and 9).

One service validates, secures and stores records of every object. All four security layers apply:
system/object permissions (profile), field-level security, and record sharing. Records the user cannot
see return 404; hidden fields are removed from every response and refused on write.
"""

from __future__ import annotations

import base64
import json
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import (
    ColumnElement,
    and_,
    delete,
    false,
    func,
    literal,
    literal_column,
    not_,
    or_,
    select,
    text,
    true,
    union_all,
    update,
)
from sqlalchemy.orm import Session

from app.core.cache import new_cache, tenant_of
from app.core.clock import local_today
from app.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.db.session import escape_like
from app.engine import hooks
from app.engine.filters import (
    FilterError,
    coerce_cursor_value,
    compile_filter,
    filter_fields,
    sort_expr,
)
from app.engine.hooks import Change, Event
from app.engine.meta import FieldMeta, ObjectMeta, Registry, load_registry
from app.engine.sharing import SharingContext, build_sharing_context
from app.engine.types import FieldValueError, display_text, normalize, present
from app.models import (
    FieldHistory,
    PackInstallation,
    Queue,
    QueueMember,
    Record,
    RecordLink,
    RecordShare,
    Role,
    StoredFile,
    User,
)
from app.security.catalog import FieldAccess, SystemPermission
from app.security.policy import AccessPolicy
from app.services import audit
from app.services.audit import AuditAction, RequestMeta

RECYCLE_DAYS = 30
MAX_PAGE = 200
COUNT_CAP = 10_000


def utcnow() -> datetime:
    return datetime.now(UTC)


class RecordValidationError(AppError):
    status_code = 422
    code = "validation_error"


@dataclass
class QueryResult:
    records: list[Record]
    next_cursor: str | None
    total: int
    total_capped: bool


def system_policy(user_id: uuid.UUID) -> AccessPolicy:
    return AccessPolicy(
        user_id=user_id,
        profile_id=uuid.UUID(int=0),
        profile_name="System",
        is_system_admin=True,
        is_portal=False,
        role_id=None,
        role_path=None,
    )


def next_sequence(db: Session, key: str) -> int:
    """Atomically take the next value of a counter (row-locked by the upsert)."""
    value = db.scalar(
        text(
            "INSERT INTO sequences (key, next_value) VALUES (:k, 2) "
            "ON CONFLICT (key) DO UPDATE SET next_value = sequences.next_value + 1 "
            "RETURNING next_value - 1"
        ),
        {"k": key},
    )
    return int(value or 1)


_NUM_TOKEN = re.compile(r"\{(0+)\}")


def format_number(db: Session, key: str, fmt: str, now: datetime | None = None) -> str:
    """Format such as "CASE-{00000}" or "MAT-{YYYY}-{0000}" (yearly counter when {YYYY} is used)."""
    now = now or utcnow()
    seq_key = f"{key}:{now.year}" if "{YYYY}" in fmt or "{YY}" in fmt else key
    n = next_sequence(db, seq_key)
    out = fmt.replace("{YYYY}", f"{now.year:04d}").replace("{YY}", f"{now.year % 100:02d}")
    out = out.replace("{MM}", f"{now.month:02d}")
    m = _NUM_TOKEN.search(out)
    return out[: m.start()] + str(n).zfill(len(m.group(1))) + out[m.end() :] if m else f"{out}{n}"


def _encode_cursor(value: Any, record_id: uuid.UUID) -> str:
    if isinstance(value, datetime):
        value = value.isoformat()
    elif value is not None and not isinstance(value, str | int | float | bool):
        value = str(value)
    raw = json.dumps({"v": value, "id": str(record_id)}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[Any, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
        return data["v"], uuid.UUID(data["id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise AppError("Invalid cursor.", code="invalid_cursor", status_code=422) from exc


_packs_cache = new_cache(256)


class RecordService:
    """Per-request record engine bound to one user (or the system)."""

    def __init__(
        self,
        db: Session,
        policy: AccessPolicy,
        *,
        meta: RequestMeta | None = None,
        system: bool = False,
        registry: Registry | None = None,
    ) -> None:
        self.db = db
        self.policy = policy
        self.request_meta = meta or RequestMeta()
        self.system = system
        self.registry = registry or load_registry(db)
        self._sharing: SharingContext | None = None
        self._packs: frozenset[str] | None = None
        self.time_zone = "Australia/Sydney"

    # ------------------------------------------------------------------ construction

    @classmethod
    def for_user(
        cls, db: Session, user: User, policy: AccessPolicy, meta: RequestMeta | None = None
    ) -> RecordService:
        svc = cls(db, policy, meta=meta)
        svc.time_zone = user.time_zone or "Australia/Sydney"
        return svc

    @classmethod
    def as_system(
        cls, db: Session, user_id: uuid.UUID | None = None, meta: RequestMeta | None = None
    ) -> RecordService:
        return cls(db, system_policy(user_id or uuid.UUID(int=0)), meta=meta, system=True)

    def elevated(self) -> RecordService:
        """Same user and transaction, without sharing/FLS checks (for hooks)."""
        svc = RecordService(
            self.db,
            system_policy(self.policy.user_id),
            meta=self.request_meta,
            system=True,
            registry=self.registry,
        )
        svc.time_zone = self.time_zone
        svc._packs = self._packs
        return svc

    @property
    def user_id(self) -> uuid.UUID | None:
        uid = self.policy.user_id
        return None if uid.int == 0 else uid

    @property
    def sharing(self) -> SharingContext:
        if self._sharing is None:
            self._sharing = build_sharing_context(self.db, self.policy, self.registry)
        return self._sharing

    @property
    def enabled_packs(self) -> frozenset[str]:
        if self._packs is None:
            # Pack enable/disable bumps the metadata revision, which keys this cache.
            key = (tenant_of(self.db), "packs", self.registry.revision)
            self._packs = _packs_cache.get_or_build(
                self.db,
                key,
                lambda: frozenset(
                    self.db.scalars(
                        select(PackInstallation.pack_key).where(PackInstallation.is_enabled)
                    ).all()
                ),
            )
        return self._packs

    # ------------------------------------------------------------------ access helpers

    def object(self, api_name: str, *, need: str = "read") -> ObjectMeta:
        meta = self.registry.get(api_name)
        if meta.pack_key and meta.pack_key not in self.enabled_packs:
            raise NotFoundError("Object not found.")
        if self.system:
            return meta
        access = self.policy.object(api_name)
        allowed = {
            "read": access.read,
            "create": access.create,
            "edit": access.edit,
            "delete": access.delete,
        }[need]
        if not allowed:
            if not access.read:
                raise PermissionDeniedError(f"You don't have access to {meta.plural_label}.")
            raise PermissionDeniedError(f"You don't have permission to {need} {meta.plural_label}.")
        return meta

    def field_access(self, meta: ObjectMeta, f: FieldMeta) -> FieldAccess:
        if self.system:
            return FieldAccess.EDIT
        if f.is_system:
            if f.api_name == "owner_id":
                return FieldAccess.READ
            if f.api_name == "name" and not f.is_readonly:
                return self.policy.field(meta.api_name, "name", FieldAccess.EDIT)
            return FieldAccess.READ
        access = self.policy.field(meta.api_name, f.api_name, f.default_access)
        if f.is_readonly and access is FieldAccess.EDIT:
            return FieldAccess.READ
        return access

    def readable_fields(self, meta: ObjectMeta) -> list[FieldMeta]:
        return [f for f in meta.fields.values() if self.field_access(meta, f) is not FieldAccess.HIDDEN]

    def check_readable_fields(self, meta: ObjectMeta, names: set[str]) -> None:
        for name in names:
            f = meta.fields.get(name)
            if f is None:
                raise FilterError(f"Unknown field {name!r}.")
            if self.field_access(meta, f) is FieldAccess.HIDDEN:
                raise FilterError(f"Unknown field {name!r}.")

    def _readable_clause(self, api_name: str, r: Any = Record) -> ColumnElement[bool]:
        if self.system:
            return literal(True)
        return self.sharing.where_readable(api_name, r)

    def can_edit(self, record: Record) -> bool:
        if self.system:
            return True
        if not self.policy.object(record.object_api_name).edit:
            return False
        return self.sharing.can(self.db, record, edit=True)

    def can_delete(self, record: Record) -> bool:
        if self.system:
            return True
        access = self.policy.object(record.object_api_name)
        if not access.delete:
            return False
        if access.modify_all:
            return True
        return self.sharing.can(self.db, record, edit=True)

    def editable_ids(self, api_name: str, ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not ids:
            return set()
        if self.system:
            return set(ids)
        if not self.policy.object(api_name).edit:
            return set()
        pred = self.sharing.editable(api_name)
        if pred is None:
            return set(ids)
        return set(self.db.scalars(select(Record.id).where(Record.id.in_(ids), pred)))

    # ------------------------------------------------------------------ reads

    def get(
        self, api_name: str, record_id: uuid.UUID, *, include_deleted: bool = False, lock: bool = False
    ) -> Record:
        meta = self.object(api_name)
        stmt = select(Record).where(
            Record.id == record_id,
            Record.object_api_name == meta.api_name,
            self._readable_clause(meta.api_name),
        )
        if not include_deleted:
            stmt = stmt.where(Record.is_deleted == false())
        if lock:
            stmt = stmt.with_for_update(of=Record)
        record = self.db.scalar(stmt)
        if record is None:
            raise NotFoundError(f"{meta.label} not found.")
        return record

    def get_any(self, record_id: uuid.UUID) -> Record:
        """A readable record of any object (search results, links)."""
        record = self.db.get(Record, record_id)
        if record is None or record.is_deleted:
            raise NotFoundError("Record not found.")
        return self.get(record.object_api_name, record_id)

    def visible_ids(self, api_name: str, ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not ids:
            return set()
        if not self.system and not self.policy.object(api_name).read:
            return set()
        stmt = select(Record.id).where(
            Record.id.in_(ids),
            Record.object_api_name == api_name,
            Record.is_deleted == false(),
            self._readable_clause(api_name),
        )
        return set(self.db.scalars(stmt))

    def visible_ids_many(self, ids_by_object: dict[str, list[uuid.UUID]]) -> set[uuid.UUID]:
        """visible_ids for several objects in one query."""
        clauses = [
            and_(Record.object_api_name == obj, Record.id.in_(ids), self._readable_clause(obj))
            for obj, ids in ids_by_object.items()
            if ids and (self.system or self.policy.object(obj).read)
        ]
        if not clauses:
            return set()
        return set(self.db.scalars(select(Record.id).where(Record.is_deleted == false(), or_(*clauses))))

    # ------------------------------------------------------------------ serialisation

    def _prefetch(
        self, meta: ObjectMeta, records: list[Record], *, with_access: bool
    ) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, str], set[uuid.UUID]]:
        return self._prefetch_groups([(meta, records)], with_access=with_access)

    def _prefetch_groups(
        self, groups: list[tuple[ObjectMeta, list[Record]]], *, with_access: bool
    ) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, str], set[uuid.UUID]]:
        """Everything serialisation needs about other rows, in one round trip (UNION ALL):
        names of lookup targets the user can read, user names, queue names, and which records are editable.
        """
        lookup_ids: set[uuid.UUID] = set()
        targets: set[str] = set()
        user_ids: set[uuid.UUID] = set()
        all_records = [(meta, rec) for meta, recs in groups for rec in recs]
        for meta, rec in all_records:
            for f in meta.data_fields:
                value = rec.data.get(f.api_name)
                if not value:
                    continue
                if f.is_lookup or f.type == "user":
                    try:
                        parsed = uuid.UUID(str(value))
                    except ValueError:
                        continue
                    if f.type == "user":
                        user_ids.add(parsed)
                    else:
                        lookup_ids.add(parsed)
                        targets.update(t for t in f.targets if t in self.registry.objects)
            for uid in (rec.owner_id, rec.created_by_id, rec.updated_by_id):
                if uid:
                    user_ids.add(uid)
        queue_ids = {r.queue_id for _, r in all_records if r.queue_id}

        parts: list[Any] = []
        kind: Any = literal_column("'r'").label("kind")
        obj_col: Any = Record.object_api_name.label("obj")
        if lookup_ids and targets:
            readable_targets = [t for t in sorted(targets) if self.system or self.policy.object(t).read]
            if readable_targets:
                clause = or_(
                    *(and_(Record.object_api_name == t, self._readable_clause(t)) for t in readable_targets)
                )
                parts.append(
                    select(kind, Record.id.label("rid"), Record.name.label("label"), obj_col).where(
                        Record.id.in_(lookup_ids), Record.is_deleted == false(), clause
                    )
                )
        if user_ids:
            parts.append(
                select(
                    literal_column("'u'").label("kind"), User.id, User.name, literal_column("NULL::varchar")
                ).where(User.id.in_(user_ids))
            )
        if queue_ids:
            parts.append(
                select(
                    literal_column("'q'").label("kind"), Queue.id, Queue.name, literal_column("NULL::varchar")
                ).where(Queue.id.in_(queue_ids))
            )
        editable: set[uuid.UUID] = set()
        restricted: list[Any] = []
        if with_access:
            for meta, recs in groups:
                ids = [r.id for r in recs]
                if not ids:
                    continue
                if self.system:
                    editable.update(ids)
                elif self.policy.object(meta.api_name).edit:
                    pred = self.sharing.editable(meta.api_name)
                    if pred is None:
                        editable.update(ids)
                    else:
                        restricted.append(and_(Record.id.in_(ids), pred))
        if restricted:
            parts.append(
                select(
                    literal_column("'e'").label("kind"),
                    Record.id,
                    literal_column("NULL::varchar"),
                    literal_column("NULL::varchar"),
                ).where(or_(*restricted))
            )

        labels: dict[str, dict[str, Any]] = {}
        users: dict[str, str] = {}
        queues: dict[str, str] = {}
        if parts:
            combined: Any = parts[0] if len(parts) == 1 else union_all(*parts)
            for row_kind, rid, name, obj in self.db.execute(combined).all():
                if row_kind == "r":
                    target_meta = self.registry.objects.get(obj)
                    labels[str(rid)] = {
                        "id": str(rid),
                        "name": name,
                        "object": obj,
                        "object_label": target_meta.label if target_meta else obj,
                    }
                elif row_kind == "u":
                    users[str(rid)] = name
                elif row_kind == "q":
                    queues[str(rid)] = name
                else:
                    editable.add(rid)
        return labels, users, queues, editable

    def serialize_groups(
        self,
        groups: list[tuple[str, list[Record]]],
        *,
        columns: dict[str, list[str]] | None = None,
        with_access: bool = True,
    ) -> dict[str, list[dict[str, Any]]]:
        """serialize_many for several objects with one shared prefetch query."""
        metas = [(self.registry.get(api), recs) for api, recs in groups]
        prefetched = self._prefetch_groups(metas, with_access=with_access)
        return {
            meta.api_name: self.serialize_many(
                meta.api_name,
                recs,
                columns=(columns or {}).get(meta.api_name),
                with_access=with_access,
                prefetched=prefetched,
            )
            for meta, recs in metas
        }

    def serialize_many(
        self,
        api_name: str,
        records: list[Record],
        *,
        columns: list[str] | None = None,
        with_access: bool = True,
        prefetched: tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, str], set[uuid.UUID]]
        | None = None,
    ) -> list[dict[str, Any]]:
        meta = self.registry.get(api_name)
        readable = {f.api_name: f for f in self.readable_fields(meta)}
        wanted = [c for c in (columns or list(readable)) if c in readable]
        labels, users, queue_names, editable = prefetched or self._prefetch(
            meta, records, with_access=with_access
        )
        can_delete_obj = self.system or self.policy.object(api_name).delete
        out: list[dict[str, Any]] = []
        for r in records:
            values: dict[str, Any] = {}
            display: dict[str, Any] = {}
            for name in wanted:
                f = readable[name]
                if f.is_system:
                    continue
                stored = r.data.get(name)
                if f.is_lookup and stored is not None:
                    info = labels.get(str(stored))
                    values[name] = str(stored) if info else None
                    if info:
                        display[name] = info
                    continue
                if f.type == "user" and stored is not None:
                    values[name] = str(stored)
                    display[name] = {
                        "id": str(stored),
                        "name": users.get(str(stored), ""),
                        "object": "user",
                        "object_label": "User",
                    }
                    continue
                values[name] = present(f, stored)
            owner: dict[str, Any] | None = None
            if r.owner_id:
                owner = {"id": str(r.owner_id), "name": users.get(str(r.owner_id), ""), "type": "user"}
            elif r.queue_id:
                owner = {"id": str(r.queue_id), "name": queue_names.get(str(r.queue_id), ""), "type": "queue"}
            out.append(
                {
                    "id": str(r.id),
                    "object": r.object_api_name,
                    "name": r.name,
                    "record_number": r.record_number,
                    "owner": owner,
                    "created_at": r.created_at,
                    "created_by": {"id": str(r.created_by_id), "name": users.get(str(r.created_by_id), "")}
                    if r.created_by_id
                    else None,
                    "updated_at": r.updated_at,
                    "updated_by": {"id": str(r.updated_by_id), "name": users.get(str(r.updated_by_id), "")}
                    if r.updated_by_id
                    else None,
                    "version": r.version,
                    "is_deleted": r.is_deleted,
                    "fields": values,
                    "display": display,
                    "access": {
                        "edit": r.id in editable and not r.is_deleted,
                        "delete": can_delete_obj and r.id in editable and not r.is_deleted,
                    },
                }
            )
        return out

    def serialize(self, record: Record) -> dict[str, Any]:
        return self.serialize_many(record.object_api_name, [record])[0]

    # ------------------------------------------------------------------ writes: validation

    def _normalize_values(
        self,
        meta: ObjectMeta,
        values: dict[str, Any],
        *,
        existing: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], set[str]]:
        """Validate caller-supplied values. Returns (normalized values, changed field names)."""
        errors: dict[str, str] = {}
        out: dict[str, Any] = {}
        changed: set[str] = set()
        for name, raw in values.items():
            if name in ("name",):
                continue
            f = meta.fields.get(name)
            if f is None or f.is_system:
                errors[name] = "Unknown field."
                continue
            access = self.field_access(meta, f)
            try:
                value = normalize(f, raw)
            except FieldValueError as exc:
                if f.type == "picklist" and existing is not None and existing.get(name) == raw:
                    value = raw  # an inactive value already stored may be kept
                else:
                    errors[name] = str(exc)
                    continue
            old = (existing or {}).get(name)
            if f.type == "encrypted_text":
                same = present(f, old) == raw if old is not None else value is None
            else:
                same = old == value
            if same and existing is not None:
                continue
            if access is not FieldAccess.EDIT:
                if access is FieldAccess.HIDDEN:
                    errors[name] = "Unknown field."
                else:
                    errors[name] = "This field is read-only."
                continue
            out[name] = value
            changed.add(name)
        if errors:
            raise RecordValidationError("Some fields are invalid.", fields=errors)
        return out, changed

    def _check_required_and_lookups(self, meta: ObjectMeta, data: dict[str, Any], changed: set[str]) -> None:
        errors: dict[str, str] = {}
        for f in meta.data_fields:
            value = data.get(f.api_name)
            if f.required and (value is None or value == [] or value == "") and f.type != "auto_number":
                errors[f.api_name] = "This field is required."
        for name in changed:
            f = meta.fields[name]
            value = data.get(name)
            if f.type == "user" and value is not None:
                user = self.db.get(User, uuid.UUID(str(value)))
                if user is None or not user.is_active or user.profile.is_portal:
                    errors[name] = "Choose an active user."
                continue
            if not f.is_lookup or value is None:
                continue
            target_id = uuid.UUID(str(value))
            target = self.db.get(Record, target_id)
            if target is None or target.is_deleted or target.object_api_name not in f.targets:
                errors[name] = "Choose a valid record."
                continue
            if not self.system and target_id not in self.visible_ids(target.object_api_name, [target_id]):
                errors[name] = "Choose a valid record."
                continue
            flt = f.options.get("filter")
            if flt:
                target_meta = self.registry.get(target.object_api_name)
                ok = self.db.scalar(
                    select(literal(True)).where(
                        Record.id == target_id,
                        compile_filter(target_meta, flt, Record, None, user_id=self.user_id),
                    )
                )
                if not ok:
                    errors[name] = "This record doesn't match the lookup filter."
        if errors:
            raise RecordValidationError("Some fields are invalid.", fields=errors)

    def _check_unique(
        self, meta: ObjectMeta, data: dict[str, Any], changed: set[str], exclude: uuid.UUID | None
    ) -> None:
        errors: dict[str, str] = {}
        for name in changed:
            f = meta.fields[name]
            if not (f.is_unique or f.external_id) or data.get(name) is None:
                continue
            stmt = select(Record.id).where(
                Record.object_api_name == meta.api_name,
                Record.is_deleted == false(),
                func.lower(Record.data[name].astext) == str(data[name]).lower(),
            )
            if exclude is not None:
                stmt = stmt.where(Record.id != exclude)
            if self.db.scalar(stmt.limit(1)) is not None:
                errors[name] = "Another record already uses this value."
        if errors:
            raise ConflictError("Duplicate value.", fields=errors)

    def _apply_defaults(self, meta: ObjectMeta, data: dict[str, Any]) -> None:
        for f in meta.data_fields:
            if f.api_name in data or f.default_value is None:
                continue
            default = f.default_value
            if f.type == "date" and default == "today":
                default = local_today().isoformat()
            elif f.type == "datetime" and default == "now":
                default = utcnow().isoformat().replace("+00:00", "Z")
            elif f.type == "picklist" and default not in f.active_values():
                continue
            data[f.api_name] = default
        for f in meta.data_fields:
            if f.type == "picklist" and f.api_name not in data:
                for v in f.picklist_values:
                    if v.get("default") and v.get("active", True):
                        data[f.api_name] = v["value"]
                        break

    def _sync_links(self, meta: ObjectMeta, record: Record, changed: set[str]) -> None:
        for name in changed:
            f = meta.fields.get(name)
            if f is None or not f.is_lookup:
                continue
            self.db.execute(
                delete(RecordLink).where(
                    RecordLink.from_record_id == record.id, RecordLink.field_api_name == name
                )
            )
            value = record.data.get(name)
            if value is not None:
                self.db.add(
                    RecordLink(
                        from_record_id=record.id,
                        field_api_name=name,
                        to_record_id=uuid.UUID(str(value)),
                        from_object=meta.api_name,
                        is_master=f.type == "master_detail",
                    )
                )

    def _search_text(self, meta: ObjectMeta, record: Record) -> str:
        parts = [record.name or "", record.record_number or ""]
        for f in meta.data_fields:
            if f.searchable and f.type != "encrypted_text":
                parts.append(display_text(f, record.data.get(f.api_name)))
        text_value = " ".join(p for p in parts if p)
        # Also index the parts of e-mail addresses, web sites and codes ("jo@acme.com" -> "jo acme com").
        return (text_value + " " + re.sub(r"[@._/:\-]+", " ", text_value))[:20000]

    def _refresh_search(self, meta: ObjectMeta, record: Record) -> None:
        if not meta.searchable:
            return
        self.db.execute(
            update(Record)
            .where(Record.id == record.id)
            .values(search_vector=func.to_tsvector("simple", self._search_text(meta, record)))
        )

    def _run(self, object_api_name: str, event: Event, change: Change) -> None:
        for fn in hooks.hooks_for(object_api_name, event, self.enabled_packs):
            fn(change)

    def _resolve_owner(
        self, meta: ObjectMeta, owner_id: Any, queue_id: Any, *, creating: bool
    ) -> tuple[uuid.UUID | None, uuid.UUID | None]:
        if queue_id:
            if not meta.allow_queues:
                raise RecordValidationError(
                    "Queues can't own these records.", fields={"owner_id": "Queues not allowed"}
                )
            q = self.db.get(Queue, uuid.UUID(str(queue_id)))
            if q is None or meta.api_name not in (q.object_api_names or []):
                raise RecordValidationError(
                    "Choose a valid queue.", fields={"owner_id": "Choose a valid queue"}
                )
            return None, q.id
        if owner_id:
            uid = uuid.UUID(str(owner_id))
            user = self.db.get(User, uid)
            if user is None or not user.is_active or user.profile.is_portal:
                raise RecordValidationError(
                    "Choose an active user.", fields={"owner_id": "Choose an active user"}
                )
            return uid, None
        return (self.user_id if creating else None), None

    # ------------------------------------------------------------------ writes

    def create(
        self,
        api_name: str,
        values: dict[str, Any],
        *,
        owner_id: Any = None,
        queue_id: Any = None,
        system_values: dict[str, Any] | None = None,
    ) -> Record:
        meta = self.object(api_name, need="create")
        values = dict(values)
        name_value = values.pop("name", None)
        owner_id = owner_id or values.pop("owner_id", None)
        queue_id = queue_id or values.pop("queue_id", None)
        data, changed = self._normalize_values(meta, values, existing=None)
        self._apply_defaults(meta, data)
        name_field = meta.fields["name"]
        if meta.name_field_type == "text" and name_value is not None:
            if self.field_access(meta, name_field) is not FieldAccess.EDIT:
                raise RecordValidationError(
                    "Some fields are invalid.", fields={"name": "This field is read-only."}
                )
            try:
                name_value = normalize(name_field, name_value)
            except FieldValueError as exc:
                raise RecordValidationError("Some fields are invalid.", fields={"name": str(exc)}) from exc
        owner, queue = self._resolve_owner(meta, owner_id, queue_id, creating=True)
        other_owner = owner is not None and owner != self.user_id and queue is None
        if other_owner and not self.system and not self.policy.has(SystemPermission.TRANSFER_RECORDS):
            raise PermissionDeniedError("You can't create records owned by someone else.")
        change = Change(
            svc=self,
            object_api_name=api_name,
            record=None,
            data=data,
            changed=changed | ({"name"} if name_value else set()),
            system={"name": name_value, "owner_id": owner, "queue_id": queue, **(system_values or {})},
        )
        self._run(api_name, Event.BEFORE_CREATE, change)
        data = {k: v for k, v in change.data.items() if v is not None}
        changed = {k for k in data if k in meta.fields and not meta.fields[k].is_system}
        self._check_required_and_lookups(meta, data, changed)
        self._check_unique(meta, data, changed, None)
        self._check_master_edit(meta, data)
        record_number = None
        name = change.system.get("name")
        if meta.name_field_type == "auto_number":
            record_number = format_number(self.db, meta.api_name, meta.name_format or "{00000}")
            name = record_number
        if not name:
            raise RecordValidationError(
                "Some fields are invalid.", fields={"name": "This field is required."}
            )
        now = utcnow()
        record = Record(
            id=uuid.uuid4(),
            object_api_name=meta.api_name,
            name=str(name)[:255],
            record_number=record_number,
            owner_id=change.system.get("owner_id"),
            queue_id=change.system.get("queue_id"),
            data=data,
            created_at=now,
            updated_at=now,
            created_by_id=self.user_id,
            updated_by_id=self.user_id,
            version=1,
        )
        self.db.add(record)
        self.db.flush()
        self._sync_links(
            meta, record, {f.api_name for f in meta.data_fields if f.is_lookup and data.get(f.api_name)}
        )
        self._refresh_search(meta, record)
        self._run(api_name, Event.AFTER_CREATE, Change(self, api_name, record, record.data, changed=changed))
        audit.record(
            self.db,
            action=AuditAction.CREATE,
            entity_type=f"record:{meta.api_name}",
            entity_id=record.id,
            summary=f"Created {meta.label} {record.name}",
            actor_id=self.user_id,
            meta=self.request_meta,
        )
        self.db.flush()
        return record

    def _check_master_edit(self, meta: ObjectMeta, data: dict[str, Any]) -> None:
        master = meta.master_field
        if master is None or self.system or not data.get(master.api_name):
            return
        parent = self.db.get(Record, uuid.UUID(str(data[master.api_name])))
        if parent is None or not self.can_edit(parent):
            raise PermissionDeniedError(
                f"You need edit access to the {master.label} to change its {meta.plural_label}."
            )

    def update(
        self,
        api_name: str,
        record_id: uuid.UUID,
        values: dict[str, Any],
        *,
        version: int | None = None,
        record: Record | None = None,
    ) -> Record:
        meta = self.object(api_name, need="edit")
        record = record or self.get(api_name, record_id, lock=True)
        if version is not None and version != record.version:
            raise ConflictError(
                "This record was changed by someone else. Reload it and try again.", code="stale_version"
            )
        if not self.can_edit(record):
            raise PermissionDeniedError("You don't have permission to edit this record.")
        values = dict(values)
        name_value = values.pop("name", None)
        owner_value = values.pop("owner_id", None)
        values.pop("queue_id", None)
        if owner_value is not None:
            raise RecordValidationError(
                "Use Change Owner to transfer records.", fields={"owner_id": "Use Change Owner"}
            )
        old = dict(record.data)
        data, changed = self._normalize_values(meta, values, existing=old)
        system: dict[str, Any] = {}
        if name_value is not None and meta.name_field_type == "text":
            name_field = meta.fields["name"]
            try:
                normalized_name = normalize(name_field, name_value)
            except FieldValueError as exc:
                raise RecordValidationError("Some fields are invalid.", fields={"name": str(exc)}) from exc
            if normalized_name != record.name:
                if self.field_access(meta, name_field) is not FieldAccess.EDIT:
                    raise RecordValidationError(
                        "Some fields are invalid.", fields={"name": "This field is read-only."}
                    )
                if not normalized_name:
                    raise RecordValidationError(
                        "Some fields are invalid.", fields={"name": "This field is required."}
                    )
                system["name"] = normalized_name
        merged = {**old, **data}
        change = Change(
            svc=self,
            object_api_name=api_name,
            record=record,
            data=merged,
            old=old,
            changed=changed | ({"name"} if "name" in system else set()),
            system=system,
        )
        self._run(api_name, Event.BEFORE_UPDATE, change)
        merged = {k: v for k, v in change.data.items() if v is not None}
        changed = {k for k in set(merged) | set(old) if merged.get(k) != old.get(k)}
        if not changed and "name" not in change.system:
            return record
        self._check_required_and_lookups(meta, merged, changed)
        self._check_unique(meta, merged, changed, record.id)
        self._check_master_edit(meta, merged)
        self._write_history(meta, record, old, merged, changed, change.system.get("name"))
        if change.system.get("name"):
            record.name = str(change.system["name"])[:255]
        record.data = merged
        record.version += 1
        record.updated_at = utcnow()
        record.updated_by_id = self.user_id
        self.db.flush()
        self._sync_links(meta, record, changed)
        self._refresh_search(meta, record)
        self._run(
            api_name, Event.AFTER_UPDATE, Change(self, api_name, record, merged, old=old, changed=changed)
        )
        audit_changes = {
            k: {"from": old.get(k), "to": merged.get(k)}
            for k in sorted(changed)
            if k in meta.fields and meta.fields[k].type != "encrypted_text"
        }
        audit.record(
            self.db,
            action=AuditAction.UPDATE,
            entity_type=f"record:{meta.api_name}",
            entity_id=record.id,
            summary=f"Updated {meta.label} {record.name}",
            actor_id=self.user_id,
            changes=audit_changes or None,
            meta=self.request_meta,
        )
        self.db.flush()
        return record

    def _write_history(
        self,
        meta: ObjectMeta,
        record: Record,
        old: dict[str, Any],
        new: dict[str, Any],
        changed: set[str],
        new_name: str | None,
    ) -> None:
        if not meta.track_history:
            return
        now = utcnow()
        for name in sorted(changed):
            f = meta.fields.get(name)
            if f is None or not f.track_history:
                continue
            masked = f.type == "encrypted_text"
            self.db.add(
                FieldHistory(
                    record_id=record.id,
                    field_api_name=name,
                    old_value=None if masked else old.get(name),
                    new_value=None if masked else new.get(name),
                    changed_by_id=self.user_id,
                    changed_at=now,
                )
            )
        if new_name and new_name != record.name:
            self.db.add(
                FieldHistory(
                    record_id=record.id,
                    field_api_name="name",
                    old_value=record.name,
                    new_value=new_name,
                    changed_by_id=self.user_id,
                    changed_at=now,
                )
            )

    def change_owner(
        self, api_name: str, record_id: uuid.UUID, owner_id: Any = None, queue_id: Any = None
    ) -> Record:
        meta = self.object(api_name, need="edit")
        record = self.get(api_name, record_id, lock=True)
        if not self.can_edit(record):
            raise PermissionDeniedError("You don't have permission to edit this record.")
        owner, queue = self._resolve_owner(meta, owner_id, queue_id, creating=False)
        taking_from_queue = (
            record.queue_id is not None
            and record.queue_id in self.sharing.queue_ids
            and owner == self.user_id
        )
        if (
            not self.system
            and record.owner_id != self.user_id
            and not taking_from_queue
            and not self.policy.has(SystemPermission.TRANSFER_RECORDS)
        ):
            raise PermissionDeniedError(
                "Transferring records you don't own needs the Transfer Records permission."
            )
        if owner is None and queue is None:
            raise RecordValidationError("Choose a new owner.", fields={"owner_id": "Choose a new owner"})
        if (record.owner_id, record.queue_id) == (owner, queue):
            return record
        before = {"owner_id": record.owner_id, "queue_id": record.queue_id}
        if meta.track_history:
            self.db.add(
                FieldHistory(
                    record_id=record.id,
                    field_api_name="owner_id",
                    old_value=str(record.owner_id or record.queue_id)
                    if (record.owner_id or record.queue_id)
                    else None,
                    new_value=str(owner or queue),
                    changed_by_id=self.user_id,
                )
            )
        record.owner_id, record.queue_id = owner, queue
        record.version += 1
        record.updated_at = utcnow()
        record.updated_by_id = self.user_id
        # Manual shares are removed when ownership changes (as in other CRMs); system shares stay.
        self.db.execute(
            delete(RecordShare).where(
                RecordShare.record_id == record.id, RecordShare.created_by_id.is_not(None)
            )
        )
        audit.record(
            self.db,
            action=AuditAction.UPDATE,
            entity_type=f"record:{meta.api_name}",
            entity_id=record.id,
            summary=f"Changed owner of {meta.label} {record.name}",
            actor_id=self.user_id,
            changes=audit.diff(before, {"owner_id": owner, "queue_id": queue}),
            meta=self.request_meta,
        )
        self.db.flush()
        return record

    def delete(self, api_name: str, record_id: uuid.UUID) -> Record:
        meta = self.object(api_name, need="delete")
        record = self.get(api_name, record_id, lock=True)
        if not self.can_delete(record):
            raise PermissionDeniedError("You don't have permission to delete this record.")
        self._run(
            api_name,
            Event.BEFORE_DELETE,
            Change(self, api_name, record, dict(record.data), old=dict(record.data)),
        )
        self._check_restrict(record)
        now = utcnow()
        self._soft_delete_tree(record, now)
        self._run(
            api_name,
            Event.AFTER_DELETE,
            Change(self, api_name, record, dict(record.data), old=dict(record.data)),
        )
        audit.record(
            self.db,
            action=AuditAction.DELETE,
            entity_type=f"record:{meta.api_name}",
            entity_id=record.id,
            summary=f"Deleted {meta.label} {record.name}",
            actor_id=self.user_id,
            meta=self.request_meta,
        )
        self.db.flush()
        return record

    def _check_restrict(self, record: Record) -> None:
        """Lookups with delete rule "restrict" block deleting a record that is still referenced."""
        for child, f in self.registry.children_of(record.object_api_name):
            if f.type == "master_detail" or f.options.get("delete_rule", "clear") != "restrict":
                continue
            exists_ref = self.db.scalar(
                select(RecordLink.from_record_id)
                .join(Record, Record.id == RecordLink.from_record_id)
                .where(
                    RecordLink.to_record_id == record.id,
                    RecordLink.field_api_name == f.api_name,
                    RecordLink.from_object == child.api_name,
                    Record.is_deleted == false(),
                )
                .limit(1)
            )
            if exists_ref is not None:
                raise ConflictError(
                    f"This record is used by {child.plural_label} ({f.label}) and can't be deleted.",
                    code="delete_restricted",
                )

    def _soft_delete_tree(self, record: Record, now: datetime) -> None:
        record.is_deleted = True
        record.deleted_at = now
        record.deleted_by_id = self.user_id
        record.version += 1
        children = self.db.scalars(
            select(Record)
            .join(RecordLink, RecordLink.from_record_id == Record.id)
            .where(RecordLink.to_record_id == record.id, RecordLink.is_master, Record.is_deleted == false())
        ).all()
        for child in children:
            self._soft_delete_tree(child, now)

    def restore(self, api_name: str, record_id: uuid.UUID) -> Record:
        meta = self.object(api_name, need="delete")
        record = self.get(api_name, record_id, include_deleted=True, lock=True)
        if not record.is_deleted:
            return record
        if not self.system and not (
            record.deleted_by_id == self.user_id
            or self.policy.object(api_name).modify_all
            or self.can_delete(record)
        ):
            raise PermissionDeniedError("You can't restore this record.")
        master = meta.master_field
        if master and record.data.get(master.api_name):
            parent = self.db.get(Record, uuid.UUID(str(record.data[master.api_name])))
            if parent is not None and parent.is_deleted:
                raise ConflictError(f"Restore the {master.label} first.", code="parent_deleted")
        self._restore_tree(record, record.deleted_at)
        audit.record(
            self.db,
            action=AuditAction.UPDATE,
            entity_type=f"record:{meta.api_name}",
            entity_id=record.id,
            summary=f"Restored {meta.label} {record.name}",
            actor_id=self.user_id,
            meta=self.request_meta,
        )
        self.db.flush()
        return record

    def _restore_tree(self, record: Record, deleted_at: datetime | None) -> None:
        record.is_deleted = False
        record.deleted_at = None
        record.deleted_by_id = None
        record.version += 1
        children = self.db.scalars(
            select(Record)
            .join(RecordLink, RecordLink.from_record_id == Record.id)
            .where(
                RecordLink.to_record_id == record.id,
                RecordLink.is_master,
                Record.is_deleted == true(),
                Record.deleted_at == deleted_at,
            )
        ).all()
        for child in children:
            self._restore_tree(child, deleted_at)

    def hard_delete(self, record: Record) -> None:
        """Permanently remove a record (recycle-bin purge / admin). Clears lookups that pointed at it."""
        children = self.db.scalars(
            select(Record)
            .join(RecordLink, RecordLink.from_record_id == Record.id)
            .where(RecordLink.to_record_id == record.id, RecordLink.is_master)
        ).all()
        for child in children:
            self.hard_delete(child)
        refs = self.db.execute(
            select(RecordLink.from_record_id, RecordLink.field_api_name).where(
                RecordLink.to_record_id == record.id
            )
        ).all()
        for from_id, field_name in refs:
            ref_rec = self.db.get(Record, from_id)
            if ref_rec is not None:
                data = dict(ref_rec.data)
                data.pop(field_name, None)
                ref_rec.data = data
        self.db.execute(delete(RecordLink).where(RecordLink.to_record_id == record.id))
        self.db.flush()
        stored_id = record.data.get("stored_file_id") if record.object_api_name == "file" else None
        self.db.delete(record)
        self.db.flush()
        if stored_id:
            stored = self.db.get(StoredFile, uuid.UUID(str(stored_id)))
            if stored is not None:
                self.db.delete(stored)
                self.db.flush()

    def purge_deleted(self, older_than_days: int = RECYCLE_DAYS) -> int:
        cutoff = utcnow() - timedelta(days=older_than_days)
        roots = self.db.scalars(
            select(Record).where(Record.is_deleted == true(), Record.deleted_at < cutoff).limit(500)
        ).all()
        count = 0
        for rec in roots:
            if self.db.get(Record, rec.id) is not None:
                self.hard_delete(rec)
                count += 1
        return count

    # ------------------------------------------------------------------ query

    def base_query(self, meta: ObjectMeta, *, scope: str = "all", deleted: bool = False) -> Any:
        stmt = select(Record).where(
            Record.object_api_name == meta.api_name, Record.is_deleted == (true() if deleted else false())
        )
        if not self.system:
            stmt = stmt.where(self._readable_clause(meta.api_name))
        uid = self.user_id
        if scope == "mine":
            stmt = stmt.where(Record.owner_id == uid)
        elif scope == "team":
            team: list[Any] = [Record.owner_id == uid]
            if self.policy.role_path:
                subs = (
                    select(User.id)
                    .join(Role, Role.id == User.role_id)
                    .where(Role.path.like(self.policy.role_path + "%"))
                )
                team.append(Record.owner_id.in_(subs))
            stmt = stmt.where(or_(*team))
        elif scope == "queue":
            stmt = stmt.where(
                Record.queue_id.in_(select(QueueMember.queue_id).where(QueueMember.user_id == uid))
            )
        return stmt

    def search_clause(self, meta: ObjectMeta, term: str) -> ColumnElement[bool]:
        term = term.strip()[:100]
        like = f"%{escape_like(term)}%"
        clauses: list[ColumnElement[bool]] = [
            # Name only: auto-numbered objects store their number as the name, and a second ILIKE
            # column would defeat the trigram index.
            Record.name.ilike(like, escape="\\"),
        ]
        words = [w for w in re.split(r"\W+", term) if w]
        if words and meta.searchable:
            tsquery = " & ".join(f"{w}:*" for w in words[:8])
            clauses.append(Record.search_vector.op("@@")(func.to_tsquery("simple", tsquery)))
        return or_(*clauses)

    def query(
        self,
        api_name: str,
        *,
        filters: dict[str, Any] | None = None,
        scope: str = "all",
        search: str | None = None,
        sort: list[dict[str, str]] | None = None,
        cursor: str | None = None,
        limit: int = 50,
        deleted: bool = False,
        extra: list[ColumnElement[bool]] | None = None,
        count: bool = True,
    ) -> QueryResult:
        meta = self.object(api_name)
        limit = max(1, min(limit, MAX_PAGE))
        self.check_readable_fields(meta, filter_fields(filters))
        stmt = self.base_query(meta, scope=scope, deleted=deleted)
        if filters:
            stmt = stmt.where(
                compile_filter(meta, filters, Record, None, user_id=self.user_id, tz=self.time_zone)
            )
        if search:
            stmt = stmt.where(self.search_clause(meta, search))
        for clause in extra or []:
            stmt = stmt.where(clause)

        # The total (capped) is computed in the same statement as the page, as a scalar subquery.
        count_expr = (
            select(func.count())
            .select_from(stmt.with_only_columns(Record.id).limit(COUNT_CAP + 1).subquery())
            .scalar_subquery()
        )

        sort = sort or [{"field": "name", "direction": "asc"}]
        primary = sort[0]
        sort_field = meta.fields.get(primary.get("field", ""))
        if sort_field is None or self.field_access(meta, sort_field) is FieldAccess.HIDDEN:
            raise FilterError(f"Unknown sort field {primary.get('field')!r}.")
        if sort_field.type in ("multi_picklist", "address", "encrypted_text", "long_text"):
            raise FilterError(f"{sort_field.label} can't be sorted.")
        desc = str(primary.get("direction", "asc")).lower() == "desc"
        expr = sort_expr(sort_field, Record)

        if cursor:
            last_value, last_id = _decode_cursor(cursor)
            last = coerce_cursor_value(sort_field, last_value)
            id_cmp = Record.id < last_id if desc else Record.id > last_id
            if last is None:
                stmt = stmt.where(and_(expr.is_(None), id_cmp))
            else:
                after = expr < last if desc else expr > last
                stmt = stmt.where(or_(after, and_(expr == last, id_cmp), expr.is_(None)))
        order = [
            (expr.desc() if desc else expr.asc()).nulls_last(),
            Record.id.desc() if desc else Record.id.asc(),
        ]
        # One round trip: page rows, the sort value of each row (for the next-page cursor) and the total.
        columns: list[Any] = [Record, expr.label("_sort_value")]
        if count:
            columns.append(count_expr.label("_total"))
        result = self.db.execute(stmt.with_only_columns(*columns).order_by(*order).limit(limit + 1)).all()
        rows = [r[0] for r in result]
        total = 0
        capped = False
        if count:
            if result:
                n = int(result[0][2] or 0)
            elif cursor is None:
                n = 0
            else:
                n = int(self.db.scalar(select(count_expr)) or 0)
            capped = n > COUNT_CAP
            total = min(n, COUNT_CAP)
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            last_rec = rows[-1]
            value = result[limit - 1][1]
            if isinstance(value, datetime | date):
                value = value.isoformat()
            elif value is not None and not isinstance(value, str | int | float | bool):
                value = str(value)
            next_cursor = _encode_cursor(value, last_rec.id)
        return QueryResult(rows, next_cursor, total, capped)

    def related(
        self,
        api_name: str,
        record_id: uuid.UUID,
        child_object: str,
        field_name: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
        sort: list[dict[str, str]] | None = None,
    ) -> QueryResult:
        self.get(api_name, record_id)
        child = self.object(child_object)
        f = child.fields.get(field_name)
        if f is None or not f.is_lookup or api_name not in f.targets:
            raise NotFoundError("Related list not found.")
        if self.field_access(child, f) is FieldAccess.HIDDEN:
            raise NotFoundError("Related list not found.")
        link_exists = select(RecordLink.from_record_id).where(
            RecordLink.to_record_id == record_id,
            RecordLink.field_api_name == field_name,
            RecordLink.from_object == child_object,
        )
        return self.query(
            child_object,
            extra=[Record.id.in_(link_exists)],
            limit=limit,
            cursor=cursor,
            sort=sort or [{"field": "created_at", "direction": "desc"}],
        )

    def top_records(
        self, specs: Sequence[tuple[ObjectMeta, Sequence[Any], Any]], limit: int
    ) -> dict[str, list[Record]]:
        """Up to ``limit + 1`` readable records per object, in one round trip.

        ``specs``: (object, extra conditions, sort expression - newest/highest first). Callers trim to
        ``limit`` and use the extra row to show "more".
        """
        ranked = []
        for meta, conditions, order in specs:
            base = self.base_query(meta)
            ranked.append(
                base.with_only_columns(
                    Record.id.label("rid"),
                    func.row_number()
                    .over(order_by=(order.desc().nulls_last(), Record.id.desc()))
                    .label("rn"),
                ).where(*conditions)
            )
        if not ranked:
            return {}
        combined: Any = ranked[0] if len(ranked) == 1 else union_all(*ranked)
        inner = combined.subquery()
        rows = self.db.execute(
            select(Record)
            .join(inner, inner.c.rid == Record.id)
            .where(inner.c.rn <= limit + 1)
            .order_by(Record.object_api_name, inner.c.rn)
        ).scalars()
        out: dict[str, list[Record]] = {meta.api_name: [] for meta, _, _ in specs}
        for rec in rows:
            out.setdefault(rec.object_api_name, []).append(rec)
        return out

    def history(self, api_name: str, record_id: uuid.UUID) -> list[dict[str, Any]]:
        meta = self.object(api_name)
        self.get(api_name, record_id)
        rows = self.db.execute(
            select(FieldHistory, User.name)
            .outerjoin(User, User.id == FieldHistory.changed_by_id)
            .where(FieldHistory.record_id == record_id)
            .order_by(FieldHistory.changed_at.desc(), FieldHistory.id)
            .limit(500)
        ).all()
        out: list[dict[str, Any]] = []
        for h, user_name in rows:
            f = meta.fields.get(h.field_api_name)
            if f is None or self.field_access(meta, f) is FieldAccess.HIDDEN:
                continue
            out.append(
                {
                    "id": str(h.id),
                    "field": h.field_api_name,
                    "field_label": f.label,
                    "old_value": h.old_value,
                    "new_value": h.new_value,
                    "changed_by": user_name,
                    "changed_at": h.changed_at,
                }
            )
        return out

    # ------------------------------------------------------------------ bulk

    def bulk(
        self, api_name: str, ids: list[uuid.UUID], operation: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Mass update / change owner / delete. Each record succeeds or fails on its own."""
        if len(ids) > MAX_PAGE:
            raise AppError(f"Select at most {MAX_PAGE} records.", status_code=422)
        results: list[dict[str, Any]] = []
        for rid in ids:
            try:
                with self.db.begin_nested():
                    if operation == "update":
                        self.update(api_name, rid, dict(payload.get("values") or {}))
                    elif operation == "change_owner":
                        self.change_owner(api_name, rid, payload.get("owner_id"), payload.get("queue_id"))
                    elif operation == "delete":
                        self.delete(api_name, rid)
                    else:
                        raise AppError("Unknown bulk operation.", status_code=422)
                results.append({"id": str(rid), "ok": True})
            except AppError as exc:
                results.append({"id": str(rid), "ok": False, "error": exc.message, "fields": exc.fields})
        return {
            "succeeded": sum(1 for r in results if r["ok"]),
            "failed": sum(1 for r in results if not r["ok"]),
            "results": results,
        }

    # ------------------------------------------------------------------ sharing (manual)

    def shares(self, api_name: str, record_id: uuid.UUID) -> list[RecordShare]:
        self.get(api_name, record_id)
        return list(self.db.scalars(select(RecordShare).where(RecordShare.record_id == record_id)))

    def add_share(
        self, api_name: str, record_id: uuid.UUID, principal_type: str, principal_id: uuid.UUID, access: str
    ) -> RecordShare:
        record = self.get(api_name, record_id)
        if not self.system and not (
            record.owner_id == self.user_id
            or self.policy.object(api_name).modify_all
            or self.policy.has(SystemPermission.MANAGE_PROFILES_SHARING)
        ):
            raise PermissionDeniedError("Only the owner or an administrator can share this record.")
        if access not in ("read", "read_write") or principal_type not in (
            "user",
            "group",
            "role",
            "role_and_subordinates",
        ):
            raise RecordValidationError("Invalid share.", fields={"access": "Invalid"})
        share = RecordShare(
            record_id=record.id,
            principal_type=principal_type,
            principal_id=principal_id,
            access=access,
            created_by_id=self.user_id,
        )
        self.db.add(share)
        audit.record(
            self.db,
            action=AuditAction.CREATE,
            entity_type="record_share",
            entity_id=record.id,
            summary=f"Shared {record.name} with {principal_type} ({access})",
            actor_id=self.user_id,
            changes={
                "principal_id": {"from": None, "to": str(principal_id)},
                "access": {"from": None, "to": access},
            },
            meta=self.request_meta,
        )
        self.db.flush()
        return share

    def remove_share(self, api_name: str, record_id: uuid.UUID, share_id: uuid.UUID) -> None:
        record = self.get(api_name, record_id)
        if not self.system and not (
            record.owner_id == self.user_id
            or self.policy.object(api_name).modify_all
            or self.policy.has(SystemPermission.MANAGE_PROFILES_SHARING)
        ):
            raise PermissionDeniedError("Only the owner or an administrator can change sharing.")
        share = self.db.get(RecordShare, share_id)
        if share is None or share.record_id != record.id:
            raise NotFoundError("Share not found.")
        self.db.delete(share)
        audit.record(
            self.db,
            action=AuditAction.DELETE,
            entity_type="record_share",
            entity_id=record.id,
            summary=f"Removed a share of {record.name}",
            actor_id=self.user_id,
            meta=self.request_meta,
        )
        self.db.flush()


def not_deleted() -> ColumnElement[bool]:
    return not_(Record.is_deleted)

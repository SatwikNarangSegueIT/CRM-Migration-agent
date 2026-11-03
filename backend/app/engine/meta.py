"""In-process metadata cache.

Object and field definitions are read on almost every request, so each process keeps an immutable
snapshot and reloads it when `metadata_revision` moves (any metadata change bumps it in the same
transaction). Snapshots are plain dataclasses, safe to share between threads.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field, replace
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError
from app.models import FieldDefinition, MetadataRevision, ObjectDefinition
from app.security.catalog import FieldAccess

# System fields exist on every object as real columns of `records`.
SYSTEM_FIELDS: dict[str, tuple[str, str]] = {
    "id": ("ID", "id"),
    "name": ("Name", "text"),
    "record_number": ("Record Number", "text"),
    "owner_id": ("Owner", "owner"),
    "created_at": ("Created Date", "datetime"),
    "created_by_id": ("Created By", "user"),
    "updated_at": ("Last Modified Date", "datetime"),
    "updated_by_id": ("Last Modified By", "user"),
}
LOOKUP_TYPES = frozenset({"lookup", "master_detail"})
NUMERIC_TYPES = frozenset({"number", "percent", "currency"})
TEXT_TYPES = frozenset({"text", "textarea", "long_text", "email", "phone", "url", "picklist", "auto_number"})


@dataclass(frozen=True)
class FieldMeta:
    api_name: str
    label: str
    type: str
    help_text: str | None = None
    is_custom: bool = False
    is_standard: bool = True
    is_readonly: bool = False
    required: bool = False
    is_unique: bool = False
    external_id: bool = False
    filterable: bool = True
    indexed: bool = False
    searchable: bool = False
    track_history: bool = False
    default_access: FieldAccess = FieldAccess.EDIT
    default_value: Any = None
    options: dict[str, Any] = field(default_factory=dict)
    sort_order: int = 0
    is_system: bool = False

    @property
    def is_lookup(self) -> bool:
        return self.type in LOOKUP_TYPES

    @property
    def targets(self) -> tuple[str, ...]:
        """Lookup target object(s). Polymorphic lookups (e.g. "related to") list several."""
        if "targets" in self.options:
            return tuple(self.options["targets"])
        target = self.options.get("target")
        return (target,) if target else ()

    @property
    def picklist_values(self) -> list[dict[str, Any]]:
        return list(self.options.get("values", []))

    def active_values(self) -> list[str]:
        return [v["value"] for v in self.picklist_values if v.get("active", True)]

    @property
    def is_path(self) -> bool:
        return bool(self.options.get("is_path"))


@dataclass(frozen=True)
class ObjectMeta:
    api_name: str
    label: str
    plural_label: str
    description: str | None
    icon: str
    color: str
    is_custom: bool
    pack_key: str | None
    name_field_type: str
    name_label: str
    name_format: str | None
    track_history: bool
    allow_activities: bool
    allow_files: bool
    allow_notes: bool
    searchable: bool
    allow_reports: bool
    show_in_portal: bool
    allow_queues: bool
    is_detail_only: bool
    page_layout: list[dict[str, Any]]
    compact_layout: list[str]
    related_lists: list[dict[str, Any]]
    list_columns: list[str]
    portal_fields: list[str]
    fields: dict[str, FieldMeta]

    def field(self, api_name: str) -> FieldMeta:
        meta = self.fields.get(api_name)
        if meta is None:
            raise NotFoundError(f"Field {api_name!r} does not exist on {self.label}.")
        return meta

    @property
    def data_fields(self) -> list[FieldMeta]:
        """Fields stored in `records.data` (everything except system columns)."""
        return [f for f in self.fields.values() if not f.is_system]

    @property
    def master_field(self) -> FieldMeta | None:
        return next((f for f in self.fields.values() if f.type == "master_detail"), None)

    @property
    def path_field(self) -> FieldMeta | None:
        return next((f for f in self.fields.values() if f.type == "picklist" and f.is_path), None)


@dataclass(frozen=True)
class Registry:
    revision: int
    objects: dict[str, ObjectMeta]

    def get(self, api_name: str) -> ObjectMeta:
        obj = self.objects.get(api_name)
        if obj is None:
            raise NotFoundError("Object not found.")
        return obj

    def children_of(self, api_name: str) -> list[tuple[ObjectMeta, FieldMeta]]:
        """(child object, lookup field) pairs pointing at `api_name`."""
        out: list[tuple[ObjectMeta, FieldMeta]] = []
        for obj in self.objects.values():
            for f in obj.data_fields:
                if f.is_lookup and api_name in f.targets:
                    out.append((obj, f))
        return out


def _system_fields(obj: ObjectDefinition) -> dict[str, FieldMeta]:
    out: dict[str, FieldMeta] = {}
    for order, (api, (label, ftype)) in enumerate(SYSTEM_FIELDS.items()):
        if api == "name":
            label = obj.name_label
            readonly = obj.name_field_type == "auto_number"
            out[api] = FieldMeta(
                api_name=api,
                label=label,
                type="auto_number" if readonly else "text",
                is_readonly=readonly,
                required=not readonly,
                searchable=True,
                is_system=True,
                sort_order=-100,
                options={"max_length": 255},
            )
            continue
        if api == "record_number":
            continue
        out[api] = FieldMeta(
            api_name=api,
            label=label,
            type=ftype,
            is_readonly=api != "owner_id",
            default_access=FieldAccess.READ if api != "owner_id" else FieldAccess.EDIT,
            is_system=True,
            sort_order=1000 + order,
        )
    return out


def _to_meta(obj: ObjectDefinition) -> ObjectMeta:
    fields = _system_fields(obj)
    for f in obj.fields:
        if f.deleted_at is not None:
            continue
        fields[f.api_name] = FieldMeta(
            api_name=f.api_name,
            label=f.label,
            type=f.type,
            help_text=f.help_text,
            is_custom=f.is_custom,
            is_standard=f.is_standard,
            is_readonly=f.is_readonly or f.type == "auto_number",
            required=f.required,
            is_unique=f.is_unique,
            external_id=f.external_id,
            filterable=f.filterable,
            indexed=f.indexed,
            searchable=f.searchable,
            track_history=f.track_history,
            default_access=FieldAccess(f.default_access),
            default_value=f.default_value,
            options=dict(f.options or {}),
            sort_order=f.sort_order,
        )
    return ObjectMeta(
        api_name=obj.api_name,
        label=obj.label,
        plural_label=obj.plural_label,
        description=obj.description,
        icon=obj.icon,
        color=obj.color,
        is_custom=obj.is_custom,
        pack_key=obj.pack_key,
        name_field_type=obj.name_field_type,
        name_label=obj.name_label,
        name_format=obj.name_format,
        track_history=obj.track_history,
        allow_activities=obj.allow_activities,
        allow_files=obj.allow_files,
        allow_notes=obj.allow_notes,
        searchable=obj.searchable,
        allow_reports=obj.allow_reports,
        show_in_portal=obj.show_in_portal,
        allow_queues=obj.allow_queues,
        is_detail_only=obj.is_detail_only,
        page_layout=list(obj.page_layout or []),
        compact_layout=list(obj.compact_layout or []),
        related_lists=list(obj.related_lists or []),
        list_columns=list(obj.list_columns or []),
        portal_fields=list(obj.portal_fields or []),
        fields=dict(sorted(fields.items(), key=lambda kv: kv[1].sort_order)),
    )


_WILDCARD_FLAG = {"note": "allow_notes", "file": "allow_files"}


def _resolve_wildcards(metas: dict[str, ObjectMeta]) -> dict[str, ObjectMeta]:
    """Polymorphic "related to" lookups list ["*"]: every object with activities / notes / files enabled."""
    out: dict[str, ObjectMeta] = {}
    for api, meta in metas.items():
        flag = _WILDCARD_FLAG.get(api, "allow_activities")
        targets = tuple(sorted(o.api_name for o in metas.values() if getattr(o, flag)))
        fields = dict(meta.fields)
        changed = False
        for name, f in meta.fields.items():
            if f.options.get("targets") == ["*"]:
                fields[name] = replace(f, options={**f.options, "targets": list(targets)})
                changed = True
        out[api] = replace(meta, fields=fields) if changed else meta
    return out


_lock = threading.Lock()
_cache: Registry | None = None


def current_revision(db: Session) -> int:
    return int(db.scalar(select(MetadataRevision.revision).where(MetadataRevision.id == 1)) or 0)


def load_registry(db: Session) -> Registry:
    """Return the cached registry, reloading it when the stored revision has changed."""
    global _cache
    revision = current_revision(db)
    cached = _cache
    if cached is not None and cached.revision == revision:
        return cached
    objects = db.scalars(select(ObjectDefinition).options(selectinload(ObjectDefinition.fields))).all()
    metas = {o.api_name: _to_meta(o) for o in objects}
    registry = Registry(revision=revision, objects=_resolve_wildcards(metas))
    with _lock:
        _cache = registry
    return registry


def bump_revision(db: Session) -> None:
    """Call in the same transaction as any metadata change."""
    result = db.execute(update(MetadataRevision).where(MetadataRevision.id == 1).values(revision=MetadataRevision.revision + 1))
    if getattr(result, "rowcount", 0) == 0:
        db.execute(text("INSERT INTO metadata_revision (id, revision) VALUES (1, 2) ON CONFLICT (id) DO UPDATE SET revision = metadata_revision.revision + 1"))
    db.flush()


def invalidate_cache() -> None:
    global _cache
    with _lock:
        _cache = None

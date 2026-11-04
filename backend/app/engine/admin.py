"""Object Manager (plan v3, section 4): custom objects and fields, picklists, page layouts, apps.

Every change is audited and bumps the metadata revision. Limits: 200 custom objects, 400 fields per
object, 25 indexed fields per object. New custom fields are hidden from every profile except System
Administrator until access is granted (secure by default); new custom objects grant no access to other
profiles.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, false, func, select, text
from sqlalchemy.orm import Session

from app.core.errors import AppError, ConflictError, NotFoundError
from app.engine import installer
from app.engine.indexes import MAX_INDEXED_FIELDS, drop_statements, index_statements
from app.engine.meta import SYSTEM_FIELDS, bump_revision, load_registry
from app.models import (
    App,
    FieldDefinition,
    ListView,
    ObjectDefinition,
    ProfileObjectPermission,
    Record,
    SharingDefault,
)
from app.models.metadata import FIELD_TYPES
from app.services import audit
from app.services.audit import AuditAction, RequestMeta

MAX_CUSTOM_OBJECTS = 200
MAX_FIELDS = 400
DELETED_FIELD_DAYS = 15
API_RE = re.compile(r"^[a-z][a-z0-9_]{0,76}$")
RESERVED = set(SYSTEM_FIELDS) | {
    "queue_id",
    "data",
    "version",
    "is_deleted",
    "deleted_at",
    "search_vector",
    "object",
}
COMPATIBLE_TYPES: dict[str, set[str]] = {
    "text": {"textarea", "long_text", "email", "phone", "url", "picklist"},
    "textarea": {"long_text", "text"},
    "long_text": {"textarea"},
    "email": {"text"},
    "phone": {"text"},
    "url": {"text"},
    "number": {"currency", "percent"},
    "currency": {"number"},
    "percent": {"number"},
    "picklist": {"text", "multi_picklist"},
}
TYPE_OPTION_KEYS: dict[str, set[str]] = {
    "text": {"max_length"},
    "textarea": {"max_length"},
    "long_text": {"max_length"},
    "encrypted_text": {"max_length"},
    "number": {"scale", "min", "max"},
    "percent": {"scale", "min", "max"},
    "currency": {"scale", "min", "max"},
    "picklist": {"values", "is_path"},
    "multi_picklist": {"values"},
    "lookup": {"target", "delete_rule", "filter"},
    "master_detail": {"target"},
}


class MetadataError(AppError):
    status_code = 422
    code = "invalid_metadata"


def _api(name: str, *, custom: bool) -> str:
    base = re.sub(r"[^a-z0-9_]+", "_", name.strip().lower()).strip("_")
    if base.endswith("__c"):
        base = base[:-3]
    base = re.sub(r"_+", "_", base)
    if not base or not base[0].isalpha():
        base = "x_" + base
    api = base[:74]
    return f"{api}__c" if custom else api


def _audit(
    db: Session,
    actor_id: uuid.UUID | None,
    action: AuditAction,
    entity: str,
    entity_id: Any,
    summary: str,
    changes: dict[str, Any] | None,
    meta: RequestMeta,
) -> None:
    audit.record(
        db,
        action=action,
        entity_type=entity,
        entity_id=str(entity_id),
        summary=summary,
        actor_id=actor_id,
        changes=changes,
        meta=meta,
    )


def get_object(db: Session, api_name: str) -> ObjectDefinition:
    obj = db.scalar(select(ObjectDefinition).where(ObjectDefinition.api_name == api_name))
    if obj is None:
        raise NotFoundError("Object not found.")
    return obj


# ---------------------------------------------------------------- objects


def create_object(
    db: Session,
    actor_id: uuid.UUID | None,
    data: dict[str, Any],
    meta: RequestMeta,
    *,
    pack_key: str | None = None,
) -> ObjectDefinition:
    label = str(data.get("label") or "").strip()
    plural = str(data.get("plural_label") or "").strip() or (label + "s")
    if not label:
        raise MetadataError("Enter a label.", fields={"label": "Required"})
    api = _api(str(data.get("api_name") or label), custom=True)
    count = int(
        db.scalar(select(func.count()).select_from(ObjectDefinition).where(ObjectDefinition.is_custom)) or 0
    )
    if count >= MAX_CUSTOM_OBJECTS:
        raise MetadataError(f"An organisation can have at most {MAX_CUSTOM_OBJECTS} custom objects.")
    if db.scalar(select(ObjectDefinition.id).where(ObjectDefinition.api_name == api)) is not None:
        raise ConflictError(
            "An object with this API name already exists.", fields={"api_name": "Already in use"}
        )
    name_type = data.get("name_field_type", "text")
    if name_type not in ("text", "auto_number"):
        raise MetadataError("Invalid name field type.", fields={"name_field_type": "Invalid"})
    name_format = data.get("name_format") if name_type == "auto_number" else None
    if name_type == "auto_number" and not (name_format and re.search(r"\{0+\}", str(name_format))):
        raise MetadataError(
            "Auto-number format needs a number such as {0000}.", fields={"name_format": "e.g. ITEM-{0000}"}
        )
    bundle = {
        "api_name": api,
        "label": label,
        "plural_label": plural,
        "description": data.get("description"),
        "icon": data.get("icon", "custom"),
        "color": data.get("color", "#6366f1"),
        "name_field_type": name_type,
        "name_label": data.get("name_label") or f"{label} Name",
        "name_format": name_format,
        **{f: bool(data.get(f, installer._OBJECT_DEFAULTS[f])) for f in installer.OBJECT_FLAGS},
        "page_layout": [
            {"label": f"{label} Information", "columns": 2, "fields": ["name", "owner_id"]},
            {
                "label": "System Information",
                "columns": 2,
                "fields": ["created_by_id", "created_at", "updated_by_id", "updated_at"],
            },
        ],
        "compact_layout": ["owner_id"],
        "list_columns": ["name", "owner_id", "created_at"],
        "sharing": data.get("sharing", "private"),
    }
    if bundle["sharing"] not in ("private", "read", "read_write"):
        raise MetadataError("Invalid sharing default.", fields={"sharing": "Invalid"})
    conn = db.connection()
    installer.install_object(conn, bundle, pack_key)
    installer.install_list_view(
        conn, {"key": f"{api}_all", "object": api, "name": f"All {plural}", "columns": bundle["list_columns"]}
    )
    installer.install_list_view(
        conn,
        {
            "key": f"{api}_mine",
            "object": api,
            "name": f"My {plural}",
            "scope": "mine",
            "columns": bundle["list_columns"],
        },
    )
    bump_revision(db)
    obj = get_object(db, api)
    _audit(
        db,
        actor_id,
        AuditAction.CREATE,
        "object_definition",
        obj.id,
        f"Created custom object {label}",
        {"api_name": {"from": None, "to": api}},
        meta,
    )
    return obj


OBJECT_EDITABLE = (
    "label",
    "plural_label",
    "description",
    "icon",
    "color",
    "name_label",
    *installer.OBJECT_FLAGS,
)


def update_object(
    db: Session, actor_id: uuid.UUID | None, api_name: str, data: dict[str, Any], meta: RequestMeta
) -> ObjectDefinition:
    obj = get_object(db, api_name)
    before = {k: getattr(obj, k) for k in OBJECT_EDITABLE}
    for key in OBJECT_EDITABLE:
        if key in data and data[key] is not None:
            value = data[key]
            if key in ("label", "plural_label", "name_label") and not str(value).strip():
                raise MetadataError("Labels can't be blank.", fields={key: "Required"})
            setattr(obj, key, value.strip() if isinstance(value, str) else value)
    for key in ("page_layout", "compact_layout", "related_lists", "list_columns"):
        if key in data and data[key] is not None:
            _validate_layout_part(db, obj, key, data[key])
            setattr(obj, key, data[key])
    bump_revision(db)
    after = {k: getattr(obj, k) for k in OBJECT_EDITABLE}
    _audit(
        db,
        actor_id,
        AuditAction.UPDATE,
        "object_definition",
        obj.id,
        f"Updated object {obj.label}",
        audit.diff(before, after) or None,
        meta,
    )
    db.flush()
    return obj


def _validate_layout_part(db: Session, obj: ObjectDefinition, key: str, value: Any) -> None:
    registry = load_registry(db)
    meta = registry.get(obj.api_name)
    names = set(meta.fields)
    if key == "page_layout":
        if not isinstance(value, list) or not value:
            raise MetadataError("A page layout needs at least one section.", fields={key: "Invalid"})
        seen: set[str] = set()
        for section in value:
            if not isinstance(section, dict) or not str(section.get("label", "")).strip():
                raise MetadataError("Every section needs a label.", fields={key: "Invalid"})
            if section.get("columns", 2) not in (1, 2):
                raise MetadataError("Sections have 1 or 2 columns.", fields={key: "Invalid"})
            for f in section.get("fields", []):
                if f not in names:
                    raise MetadataError(f"Unknown field {f!r} in layout.", fields={key: f"Unknown field {f}"})
                if f in seen:
                    raise MetadataError(f"{f!r} appears twice in the layout.", fields={key: f"Duplicate {f}"})
                seen.add(f)
    elif key in ("compact_layout", "list_columns"):
        if not isinstance(value, list) or any(f not in names for f in value):
            raise MetadataError("Unknown field in list.", fields={key: "Invalid"})
        if key == "compact_layout" and len(value) > 10:
            raise MetadataError("Use at most 10 highlight fields.", fields={key: "Too many"})
    elif key == "related_lists":
        if not isinstance(value, list):
            raise MetadataError("Invalid related lists.", fields={key: "Invalid"})
        for item in value:
            child = registry.objects.get(str(item.get("object")))
            if child is None:
                raise MetadataError("Unknown related object.", fields={key: "Unknown object"})
            f = child.fields.get(str(item.get("field")))
            if f is None or not f.is_lookup or obj.api_name not in f.targets:
                raise MetadataError(
                    "Related list field must be a lookup to this object.", fields={key: "Invalid field"}
                )


def delete_object(db: Session, actor_id: uuid.UUID | None, api_name: str, meta: RequestMeta) -> None:
    obj = get_object(db, api_name)
    if not obj.is_custom or obj.pack_key:
        raise MetadataError("Standard and pack objects can't be deleted.")
    if db.scalar(select(Record.id).where(Record.object_api_name == api_name).limit(1)) is not None:
        raise ConflictError("Delete or move the object's records first.", code="object_has_records")
    registry = load_registry(db)
    for child, f in registry.children_of(api_name):
        if child.api_name != api_name:
            raise ConflictError(f"{child.label}.{f.label} looks up to this object; delete that field first.")
    db.execute(delete(ListView).where(ListView.object_api_name == api_name))
    db.execute(delete(ProfileObjectPermission).where(ProfileObjectPermission.object_api_name == api_name))
    db.execute(delete(SharingDefault).where(SharingDefault.object_api_name == api_name))
    db.execute(text("DELETE FROM profile_field_permissions WHERE object_api_name = :o"), {"o": api_name})
    for app in db.scalars(select(App)):
        tabs = [t for t in app.tabs if t.get("object") != api_name]
        if tabs != app.tabs:
            app.tabs = tabs
    db.delete(obj)
    bump_revision(db)
    _audit(
        db,
        actor_id,
        AuditAction.DELETE,
        "object_definition",
        obj.id,
        f"Deleted custom object {obj.label}",
        None,
        meta,
    )
    db.flush()


# ---------------------------------------------------------------- fields


def _clean_options(db: Session, ftype: str, options: dict[str, Any], *, object_api: str) -> dict[str, Any]:
    allowed = TYPE_OPTION_KEYS.get(ftype, set())
    unknown = set(options) - allowed - {"probabilities"}
    if unknown:
        raise MetadataError(
            f"Unknown option {sorted(unknown)[0]!r} for {ftype}.", fields={"options": "Invalid"}
        )
    out = dict(options)
    if ftype in ("picklist", "multi_picklist"):
        values = out.get("values") or []
        if not isinstance(values, list) or not values:
            raise MetadataError("Add at least one picklist value.", fields={"options.values": "Required"})
        cleaned: list[dict[str, Any]] = []
        seen: set[str] = set()
        defaults = 0
        for v in values:
            item = {"value": v} if isinstance(v, str) else dict(v)
            value = str(item.get("value", "")).strip()
            if not value or len(value) > 255:
                raise MetadataError(
                    "Picklist values need 1-255 characters.", fields={"options.values": "Invalid"}
                )
            if value.lower() in seen:
                raise MetadataError(
                    f"Duplicate picklist value {value!r}.", fields={"options.values": "Duplicate"}
                )
            seen.add(value.lower())
            entry = {
                "value": value,
                "label": str(item.get("label") or value).strip()[:255],
                "active": bool(item.get("active", True)),
            }
            if item.get("color"):
                entry["color"] = str(item["color"])[:9]
            for extra in ("probability", "forecast", "closed", "won"):
                if extra in item:
                    entry[extra] = item[extra]
            if item.get("default"):
                entry["default"] = True
                defaults += 1
            cleaned.append(entry)
        if defaults > 1:
            raise MetadataError(
                "Only one default picklist value.", fields={"options.values": "Several defaults"}
            )
        out["values"] = cleaned
    if ftype in ("lookup", "master_detail"):
        target = out.get("target")
        if (
            not target
            or db.scalar(select(ObjectDefinition.id).where(ObjectDefinition.api_name == target)) is None
        ):
            raise MetadataError(
                "Choose the object this field looks up to.", fields={"options.target": "Required"}
            )
        if ftype == "lookup":
            rule = out.setdefault("delete_rule", "clear")
            if rule not in ("clear", "restrict"):
                raise MetadataError(
                    "Delete rule is 'clear' or 'restrict'.", fields={"options.delete_rule": "Invalid"}
                )
        if ftype == "master_detail" and target == object_api:
            raise MetadataError("An object can't be its own master.", fields={"options.target": "Invalid"})
    if "max_length" in out:
        try:
            ml = int(out["max_length"])
        except (TypeError, ValueError) as exc:
            raise MetadataError("Invalid maximum length.", fields={"options.max_length": "Invalid"}) from exc
        cap = {"text": 255, "textarea": 4000, "long_text": 131072, "encrypted_text": 255}[ftype]
        if not 1 <= ml <= cap:
            raise MetadataError(f"Maximum length is 1-{cap}.", fields={"options.max_length": "Out of range"})
        out["max_length"] = ml
    if "scale" in out:
        try:
            scale = int(out["scale"])
        except (TypeError, ValueError) as exc:
            raise MetadataError("Invalid decimal places.", fields={"options.scale": "Invalid"}) from exc
        if not 0 <= scale <= 6:
            raise MetadataError("Decimal places are 0-6.", fields={"options.scale": "Out of range"})
        out["scale"] = scale
    return out


def create_field(
    db: Session,
    actor_id: uuid.UUID | None,
    object_api: str,
    data: dict[str, Any],
    meta: RequestMeta,
    *,
    pack_key: str | None = None,
) -> FieldDefinition:
    obj = get_object(db, object_api)
    label = str(data.get("label") or "").strip()
    ftype = str(data.get("type") or "")
    if not label:
        raise MetadataError("Enter a label.", fields={"label": "Required"})
    if ftype not in FIELD_TYPES or ftype == "auto_number":
        raise MetadataError("Choose a field type.", fields={"type": "Invalid"})
    custom = pack_key is None
    api = _api(str(data.get("api_name") or label), custom=custom)
    if api.removesuffix("__c") in RESERVED:
        raise MetadataError("This API name is reserved.", fields={"api_name": "Reserved"})
    active = [f for f in obj.fields if f.deleted_at is None]
    if len(active) >= MAX_FIELDS:
        raise MetadataError(f"An object can have at most {MAX_FIELDS} fields.")
    if any(f.api_name == api for f in obj.fields):
        raise ConflictError(
            "A field with this API name already exists (or is in deleted fields).",
            fields={"api_name": "Already in use"},
        )
    if ftype == "master_detail" and any(
        f.type == "master_detail" and f.deleted_at is None for f in obj.fields
    ):
        raise MetadataError(
            "An object can have only one master-detail relationship.", fields={"type": "Only one"}
        )
    if (
        ftype == "master_detail"
        and db.scalar(select(Record.id).where(Record.object_api_name == object_api).limit(1)) is not None
    ):
        raise MetadataError(
            "Master-detail fields can only be added to objects without records.",
            fields={"type": "Object has records"},
        )
    options = _clean_options(db, ftype, dict(data.get("options") or {}), object_api=object_api)
    indexed = bool(data.get("indexed", False)) and ftype not in (
        "long_text",
        "encrypted_text",
        "address",
        "multi_picklist",
    )
    if indexed and sum(1 for f in active if f.indexed or f.is_unique) >= MAX_INDEXED_FIELDS:
        raise MetadataError(
            f"An object can have at most {MAX_INDEXED_FIELDS} indexed fields.",
            fields={"indexed": "Limit reached"},
        )
    required = bool(data.get("required", False)) or ftype == "master_detail"
    if (
        required
        and db.scalar(
            select(Record.id)
            .where(Record.object_api_name == object_api, Record.is_deleted == false())
            .limit(1)
        )
        is not None
        and data.get("default_value") is None
    ):
        raise MetadataError(
            "A new required field needs a default value when records exist.",
            fields={"required": "Add a default value"},
        )
    field = FieldDefinition(
        object_id=obj.id,
        api_name=api,
        label=label,
        type=ftype,
        help_text=data.get("help_text"),
        is_custom=custom,
        is_standard=False,
        required=required,
        is_unique=bool(data.get("is_unique", False)) and ftype in ("text", "email", "phone", "url", "number"),
        external_id=bool(data.get("external_id", False)) and ftype in ("text", "email", "number"),
        filterable=ftype not in ("long_text", "encrypted_text"),
        indexed=indexed,
        searchable=bool(data.get("searchable", False))
        and ftype in ("text", "textarea", "long_text", "email", "phone", "url"),
        track_history=bool(data.get("track_history", False)),
        default_access=str(data.get("default_access") or ("edit" if pack_key else "hidden")),
        default_value=data.get("default_value"),
        options=options,
        sort_order=max([f.sort_order for f in obj.fields] + [0]) + 10,
        pack_key=pack_key,
    )
    if field.default_access not in ("hidden", "read", "edit"):
        raise MetadataError("Invalid default access.", fields={"default_access": "Invalid"})
    if ftype == "encrypted_text":
        field.searchable = False
        field.track_history = False
    db.add(field)
    db.flush()
    if ftype == "master_detail":
        db.merge(
            SharingDefault(
                object_api_name=object_api, access="controlled_by_parent", grant_access_using_hierarchy=True
            )
        )
    _add_to_layout(obj, api)
    bump_revision(db)
    _audit(
        db,
        actor_id,
        AuditAction.CREATE,
        "field_definition",
        field.id,
        f"Created field {obj.label}.{label}",
        {"api_name": {"from": None, "to": api}, "type": {"from": None, "to": ftype}},
        meta,
    )
    return field


def _add_to_layout(obj: ObjectDefinition, api: str) -> None:
    layout = [dict(s) for s in (obj.page_layout or [])]
    if not layout:
        layout = [{"label": f"{obj.label} Information", "columns": 2, "fields": []}]
    target = next((s for s in layout if s.get("label") != "System Information"), layout[0])
    if api not in target.get("fields", []):
        target["fields"] = [*target.get("fields", []), api]
    obj.page_layout = layout


FIELD_EDITABLE = (
    "label",
    "help_text",
    "required",
    "track_history",
    "searchable",
    "indexed",
    "default_access",
    "default_value",
    "is_unique",
)


def get_field(db: Session, object_api: str, field_api: str) -> tuple[ObjectDefinition, FieldDefinition]:
    obj = get_object(db, object_api)
    field = next((f for f in obj.fields if f.api_name == field_api), None)
    if field is None:
        raise NotFoundError("Field not found.")
    return obj, field


def update_field(
    db: Session,
    actor_id: uuid.UUID | None,
    object_api: str,
    field_api: str,
    data: dict[str, Any],
    meta: RequestMeta,
) -> tuple[FieldDefinition, list[str]]:
    """Returns (field, index DDL to run after commit)."""
    obj, field = get_field(db, object_api, field_api)
    if field.deleted_at is not None:
        raise MetadataError("Restore the field before editing it.")
    before = {k: getattr(field, k) for k in (*FIELD_EDITABLE, "type", "options")}
    new_type = data.get("type")
    if new_type and new_type != field.type:
        if field.is_standard:
            raise MetadataError(
                "The type of a standard field can't be changed.", fields={"type": "Standard field"}
            )
        if new_type not in COMPATIBLE_TYPES.get(field.type, set()):
            raise MetadataError(
                f"A {field.type} field can't become {new_type}; create a new field instead.",
                fields={"type": "Incompatible"},
            )
        field.type = new_type
    if "options" in data and data["options"] is not None:
        merged = {**(field.options or {}), **dict(data["options"])}
        if "targets" in (field.options or {}):
            # Polymorphic lookups ("related to") are managed by the platform.
            raise MetadataError("This field's options can't be changed.", fields={"options": "Managed field"})
        if field.type in ("lookup", "master_detail"):
            # The target object of an existing relationship never changes.
            merged["target"] = field.options.get("target")
        field.options = _clean_options(db, field.type, merged, object_api=object_api)
    for key in FIELD_EDITABLE:
        if key in data and data[key] is not None:
            if key == "label" and not str(data[key]).strip():
                raise MetadataError("Enter a label.", fields={"label": "Required"})
            if key == "default_access" and data[key] not in ("hidden", "read", "edit"):
                raise MetadataError("Invalid default access.", fields={"default_access": "Invalid"})
            if key == "required" and field.type == "master_detail" and not data[key]:
                raise MetadataError(
                    "Master-detail fields are always required.", fields={"required": "Always required"}
                )
            setattr(field, key, data[key])
    if field.type in ("long_text", "encrypted_text", "address", "multi_picklist"):
        field.indexed = False
    if field.indexed and not before["indexed"]:
        count = sum(
            1 for f in obj.fields if (f.indexed or f.is_unique) and f.deleted_at is None and f.id != field.id
        )
        if count >= MAX_INDEXED_FIELDS:
            raise MetadataError(
                f"An object can have at most {MAX_INDEXED_FIELDS} indexed fields.",
                fields={"indexed": "Limit reached"},
            )
    bump_revision(db)
    after = {k: getattr(field, k) for k in (*FIELD_EDITABLE, "type", "options")}
    _audit(
        db,
        actor_id,
        AuditAction.UPDATE,
        "field_definition",
        field.id,
        f"Updated field {obj.label}.{field.label}",
        audit.diff(before, after) or None,
        meta,
    )
    db.flush()
    ddl: list[str] = []
    if (before["indexed"], before["is_unique"], before["type"]) != (
        field.indexed,
        field.is_unique,
        field.type,
    ):
        ddl += drop_statements(object_api, field_api, concurrently=True)
        registry = load_registry(db)
        ddl += index_statements(
            registry.get(object_api), registry.get(object_api).field(field_api), concurrently=True
        )
    return field, ddl


def delete_field(
    db: Session, actor_id: uuid.UUID | None, object_api: str, field_api: str, meta: RequestMeta
) -> list[str]:
    obj, field = get_field(db, object_api, field_api)
    if field.is_standard or (field.pack_key and not field.is_custom):
        raise MetadataError("Standard fields can't be deleted.")
    if field.deleted_at is not None:
        return []
    registry = load_registry(db)
    for o in registry.objects.values():
        for r in o.related_lists:
            if r.get("object") == object_api and r.get("field") == field_api:
                o_def = get_object(db, o.api_name)
                o_def.related_lists = [
                    x
                    for x in o_def.related_lists
                    if not (x.get("object") == object_api and x.get("field") == field_api)
                ]
    field.deleted_at = datetime.now(UTC)
    obj.page_layout = [
        {**s, "fields": [f for f in s.get("fields", []) if f != field_api]} for s in obj.page_layout or []
    ]
    obj.compact_layout = [f for f in obj.compact_layout or [] if f != field_api]
    obj.list_columns = [f for f in obj.list_columns or [] if f != field_api]
    bump_revision(db)
    _audit(
        db,
        actor_id,
        AuditAction.DELETE,
        "field_definition",
        field.id,
        f"Deleted field {obj.label}.{field.label} (restorable for {DELETED_FIELD_DAYS} days)",
        None,
        meta,
    )
    db.flush()
    return drop_statements(object_api, field_api, concurrently=True)


def restore_field(
    db: Session, actor_id: uuid.UUID | None, object_api: str, field_api: str, meta: RequestMeta
) -> FieldDefinition:
    obj, field = get_field(db, object_api, field_api)
    if field.deleted_at is None:
        return field
    field.deleted_at = None
    _add_to_layout(obj, field_api)
    bump_revision(db)
    _audit(
        db,
        actor_id,
        AuditAction.UPDATE,
        "field_definition",
        field.id,
        f"Restored field {obj.label}.{field.label}",
        None,
        meta,
    )
    db.flush()
    return field


def purge_deleted_fields(db: Session, days: int = DELETED_FIELD_DAYS) -> int:
    """Remove fields deleted more than `days` ago, together with their stored values."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    fields = db.scalars(select(FieldDefinition).where(FieldDefinition.deleted_at < cutoff)).all()
    for field in fields:
        obj = db.get(ObjectDefinition, field.object_id)
        if obj is None:
            continue
        db.execute(
            text("UPDATE records SET data = data - :f WHERE object_api_name = :o AND data ? :f"),
            {"f": field.api_name, "o": obj.api_name},
        )
        db.execute(
            text("DELETE FROM record_links WHERE from_object = :o AND field_api_name = :f"),
            {"o": obj.api_name, "f": field.api_name},
        )
        db.execute(
            text("DELETE FROM profile_field_permissions WHERE object_api_name = :o AND field_api_name = :f"),
            {"o": obj.api_name, "f": field.api_name},
        )
        db.delete(field)
    if fields:
        bump_revision(db)
    db.flush()
    return len(fields)


# ---------------------------------------------------------------- apps


def _validate_tabs(db: Session, tabs: Any) -> list[dict[str, Any]]:
    if not isinstance(tabs, list):
        raise MetadataError("Tabs must be a list.", fields={"tabs": "Invalid"})
    kinds = {"home", "object", "calendar", "reports", "dashboards", "queues"}
    out: list[dict[str, Any]] = []
    registry = load_registry(db)
    for t in tabs:
        kind = t.get("kind") if isinstance(t, dict) else None
        if kind not in kinds:
            raise MetadataError("Unknown tab kind.", fields={"tabs": "Invalid"})
        if kind == "object":
            if t.get("object") not in registry.objects:
                raise MetadataError("Unknown object tab.", fields={"tabs": "Unknown object"})
            out.append({"kind": "object", "object": t["object"]})
        else:
            out.append({"kind": kind})
    return out


def save_app(
    db: Session,
    actor_id: uuid.UUID | None,
    data: dict[str, Any],
    meta: RequestMeta,
    app_id: uuid.UUID | None = None,
) -> App:
    label = str(data.get("label") or "").strip()
    if not label:
        raise MetadataError("Enter a label.", fields={"label": "Required"})
    tabs = _validate_tabs(db, data.get("tabs", []))
    profile_ids = [str(uuid.UUID(str(p))) for p in data.get("profile_ids", [])]
    if app_id is None:
        key = _api(str(data.get("key") or label), custom=False)
        if db.scalar(select(App.id).where(App.key == key)) is not None:
            raise ConflictError("An app with this key already exists.", fields={"key": "Already in use"})
        app = App(key=key, label=label, tabs=tabs, profile_ids=profile_ids)
        db.add(app)
        before: dict[str, Any] = {}
    else:
        app_or_none = db.get(App, app_id)
        if app_or_none is None:
            raise NotFoundError("App not found.")
        app = app_or_none
        before = {
            "label": app.label,
            "tabs": app.tabs,
            "profile_ids": app.profile_ids,
            "is_active": app.is_active,
        }
        app.label = label
        app.tabs = tabs
        app.profile_ids = profile_ids
    for key in ("description", "icon", "color", "sort_order", "is_active"):
        if key in data and data[key] is not None:
            setattr(app, key, data[key])
    db.flush()
    after = {"label": app.label, "tabs": app.tabs, "profile_ids": app.profile_ids, "is_active": app.is_active}
    _audit(
        db,
        actor_id,
        AuditAction.CREATE if app_id is None else AuditAction.UPDATE,
        "app",
        app.id,
        f"{'Created' if app_id is None else 'Updated'} app {app.label}",
        audit.diff(before, after) or None,
        meta,
    )
    return app


def delete_app(db: Session, actor_id: uuid.UUID | None, app_id: uuid.UUID, meta: RequestMeta) -> None:
    app = db.get(App, app_id)
    if app is None:
        raise NotFoundError("App not found.")
    db.delete(app)
    _audit(db, actor_id, AuditAction.DELETE, "app", app.id, f"Deleted app {app.label}", None, meta)
    db.flush()

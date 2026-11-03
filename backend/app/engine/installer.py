"""Install metadata bundles (objects, fields, apps, list views, field security, records) from plain data.

Used by the migrations that ship the standard objects and by industry packs, so both go through the
same code. Statements name their columns explicitly (raw SQL) so that old migrations keep working
when later migrations add columns. Every insert is idempotent: existing rows (possibly customised by
an administrator) are left untouched.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Final

from sqlalchemy import Connection, text

NAMESPACE: Final = uuid.UUID("2c3e9a64-55f1-4f5b-8f0e-1d6a3b7c9e21")

OBJECT_FLAGS = (
    "track_history",
    "allow_activities",
    "allow_files",
    "allow_notes",
    "searchable",
    "allow_reports",
    "show_in_portal",
    "allow_queues",
    "is_detail_only",
)
FIELD_FLAGS = (
    "is_readonly",
    "required",
    "is_unique",
    "external_id",
    "filterable",
    "indexed",
    "searchable",
    "track_history",
)


def stable_id(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{kind}:{key}")


def _j(value: Any) -> str:
    return json.dumps(value)


def install_object(conn: Connection, obj: dict[str, Any], pack_key: str | None = None) -> uuid.UUID:
    api = obj["api_name"]
    object_id = stable_id("object", api)
    flags = {f: obj.get(f, _OBJECT_DEFAULTS[f]) for f in OBJECT_FLAGS}
    conn.execute(
        text(
            "INSERT INTO object_definitions (id, api_name, label, plural_label, description, icon, color, is_custom, "
            "pack_key, name_field_type, name_label, name_format, track_history, allow_activities, allow_files, "
            "allow_notes, searchable, allow_reports, show_in_portal, allow_queues, is_detail_only, page_layout, "
            "compact_layout, related_lists, list_columns, portal_fields, created_at, updated_at) VALUES (:id, :api, "
            ":label, :plural, :description, :icon, :color, :is_custom, :pack, :nft, :nlabel, :nformat, :track_history, "
            ":allow_activities, :allow_files, :allow_notes, :searchable, :allow_reports, :show_in_portal, "
            ":allow_queues, :is_detail_only, CAST(:layout AS jsonb), CAST(:compact AS jsonb), CAST(:related AS jsonb), "
            "CAST(:columns AS jsonb), CAST(:portal AS jsonb), now(), now()) ON CONFLICT (api_name) DO NOTHING"
        ),
        {
            "id": object_id,
            "api": api,
            "label": obj["label"],
            "plural": obj["plural_label"],
            "description": obj.get("description"),
            "icon": obj.get("icon", "record"),
            "color": obj.get("color", "#64748b"),
            "is_custom": api.endswith("__c"),
            "pack": pack_key,
            "nft": obj.get("name_field_type", "text"),
            "nlabel": obj.get("name_label", "Name"),
            "nformat": obj.get("name_format"),
            **flags,
            "layout": _j(obj.get("page_layout", [])),
            "compact": _j(obj.get("compact_layout", [])),
            "related": _j(obj.get("related_lists", [])),
            "columns": _j(obj.get("list_columns", [])),
            "portal": _j(obj.get("portal_fields", [])),
        },
    )
    for order, field in enumerate(obj.get("fields", [])):
        install_field(conn, api, field, order=(order + 1) * 10, pack_key=pack_key, standard=pack_key is None)
    sharing = obj.get("sharing")
    if sharing:
        conn.execute(
            text(
                "INSERT INTO sharing_defaults (object_api_name, access, grant_access_using_hierarchy) "
                "VALUES (:o, :a, true) ON CONFLICT DO NOTHING"
            ),
            {"o": api, "a": sharing},
        )
    return object_id


_OBJECT_DEFAULTS: Final[dict[str, bool]] = {
    "track_history": True,
    "allow_activities": True,
    "allow_files": True,
    "allow_notes": True,
    "searchable": True,
    "allow_reports": True,
    "show_in_portal": False,
    "allow_queues": False,
    "is_detail_only": False,
}


def install_field(
    conn: Connection,
    object_api: str,
    field: dict[str, Any],
    *,
    order: int,
    pack_key: str | None = None,
    standard: bool = True,
) -> None:
    api = field["api_name"]
    flags = {f: bool(field.get(f, f == "filterable")) for f in FIELD_FLAGS}
    if field["type"] in ("long_text", "encrypted_text", "address", "multi_picklist"):
        flags["indexed"] = False
    conn.execute(
        text(
            "INSERT INTO field_definitions (id, object_id, api_name, label, type, help_text, is_custom, is_standard, "
            "is_readonly, required, is_unique, external_id, filterable, indexed, searchable, track_history, "
            "default_access, default_value, options, sort_order, pack_key, created_at, updated_at) VALUES (:id, "
            "(SELECT id FROM object_definitions WHERE api_name = :obj), :api, :label, :type, :help, :is_custom, "
            ":is_standard, :is_readonly, :required, :is_unique, :external_id, :filterable, :indexed, :searchable, "
            ":track_history, :access, CAST(:default AS jsonb), CAST(:options AS jsonb), :order, :pack, now(), now()) "
            "ON CONFLICT ON CONSTRAINT uq_field_definitions_object_api DO NOTHING"
        ),
        {
            "id": stable_id("field", f"{object_api}.{api}"),
            "obj": object_api,
            "api": api,
            "label": field["label"],
            "type": field["type"],
            "help": field.get("help_text"),
            "is_custom": api.endswith("__c"),
            "is_standard": standard and not api.endswith("__c"),
            **flags,
            "access": field.get("default_access", "edit"),
            "default": _j(field["default_value"]) if "default_value" in field else None,
            "options": _j(field.get("options", {})),
            "order": field.get("sort_order", order),
            "pack": pack_key,
        },
    )


def install_app(conn: Connection, app: dict[str, Any], pack_key: str | None = None) -> None:
    conn.execute(
        text(
            "INSERT INTO apps (id, key, label, description, icon, color, sort_order, is_active, tabs, profile_ids, "
            "pack_key, created_at, updated_at) VALUES (:id, :key, :label, :description, :icon, :color, :sort, true, "
            "CAST(:tabs AS jsonb), CAST(:profiles AS jsonb), :pack, now(), now()) ON CONFLICT (key) DO NOTHING"
        ),
        {
            "id": stable_id("app", app["key"]),
            "key": app["key"],
            "label": app["label"],
            "description": app.get("description"),
            "icon": app.get("icon", "app"),
            "color": app.get("color", "#0176d3"),
            "sort": app.get("sort_order", 0),
            "tabs": _j(app["tabs"]),
            "profiles": _j(app.get("profile_ids", [])),
            "pack": pack_key,
        },
    )


def install_list_view(conn: Connection, view: dict[str, Any]) -> None:
    key = view["key"]
    conn.execute(
        text(
            "INSERT INTO list_views (id, object_api_name, name, key, owner_id, visibility, shared_profile_ids, "
            "shared_role_ids, scope, columns, filters, sort, kanban_field, created_at, updated_at) VALUES (:id, :obj, "
            ":name, :key, NULL, 'public', '[]'::jsonb, '[]'::jsonb, :scope, CAST(:columns AS jsonb), "
            "CAST(:filters AS jsonb), CAST(:sort AS jsonb), :kanban, now(), now()) ON CONFLICT (id) DO NOTHING"
        ),
        {
            "id": stable_id("list_view", key),
            "obj": view["object"],
            "name": view["name"],
            "key": key,
            "scope": view.get("scope", "all"),
            "columns": _j(view.get("columns", [])),
            "filters": _j(view.get("filters", {})),
            "sort": _j(view.get("sort", [{"field": "name", "direction": "asc"}])),
            "kanban": view.get("kanban_field"),
        },
    )


def install_field_security(
    conn: Connection, profile_id: uuid.UUID, obj: str, field: str, access: str
) -> None:
    conn.execute(
        text(
            "INSERT INTO profile_field_permissions (profile_id, object_api_name, field_api_name, access) "
            "VALUES (:p, :o, :f, :a) ON CONFLICT DO NOTHING"
        ),
        {"p": profile_id, "o": obj, "f": field, "a": access},
    )


def install_object_permission(
    conn: Connection, profile_id: uuid.UUID, obj: str, flags: dict[str, bool]
) -> None:
    conn.execute(
        text(
            "INSERT INTO profile_object_permissions (profile_id, object_api_name, can_read, can_create, can_edit, "
            "can_delete, view_all, modify_all) VALUES (:p, :o, :r, :c, :e, :d, :va, :ma) ON CONFLICT DO NOTHING"
        ),
        {
            "p": profile_id,
            "o": obj,
            "r": flags.get("can_read", False),
            "c": flags.get("can_create", False),
            "e": flags.get("can_edit", False),
            "d": flags.get("can_delete", False),
            "va": flags.get("view_all", False),
            "ma": flags.get("modify_all", False),
        },
    )


def install_record(conn: Connection, key: str, obj: str, name: str, data: dict[str, Any]) -> uuid.UUID:
    """Shipped reference record (e.g. the GST tax rate, the standard price book)."""
    rid = stable_id("record", key)
    conn.execute(
        text(
            "INSERT INTO records (id, object_api_name, name, data, created_at, updated_at, is_deleted, version, "
            "search_vector) VALUES (:id, :obj, :name, CAST(:data AS jsonb), now(), now(), false, 1, "
            "to_tsvector('simple', :search)) ON CONFLICT (id) DO NOTHING"
        ),
        {"id": rid, "obj": obj, "name": name, "search": name, "data": _j(data)},
    )
    return rid


def install_link(
    conn: Connection, from_id: uuid.UUID, field: str, to_id: uuid.UUID, from_object: str, is_master: bool
) -> None:
    conn.execute(
        text(
            "INSERT INTO record_links (from_record_id, field_api_name, to_record_id, from_object, is_master) "
            "VALUES (:f, :fld, :t, :o, :m) ON CONFLICT DO NOTHING"
        ),
        {"f": from_id, "fld": field, "t": to_id, "o": from_object, "m": is_master},
    )


def set_setting(conn: Connection, key: str, value: Any) -> None:
    conn.execute(
        text(
            "INSERT INTO org_settings (key, value, updated_at) VALUES (:k, CAST(:v AS jsonb), now()) "
            "ON CONFLICT (key) DO NOTHING"
        ),
        {"k": key, "v": _j(value)},
    )


def bump_revision(conn: Connection) -> None:
    conn.execute(
        text(
            "INSERT INTO metadata_revision (id, revision) VALUES (1, 1) "
            "ON CONFLICT (id) DO UPDATE SET revision = metadata_revision.revision + 1"
        )
    )


def install_bundle(conn: Connection, bundle: dict[str, Any], pack_key: str | None = None) -> None:
    for obj in bundle.get("objects", []):
        install_object(conn, obj, pack_key)
    for field in bundle.get("fields", []):
        install_field(
            conn,
            field["object"],
            field,
            order=field.get("sort_order", 500),
            pack_key=pack_key,
            standard=pack_key is None,
        )
    for app in bundle.get("apps", []):
        install_app(conn, app, pack_key)
    for view in bundle.get("list_views", []):
        install_list_view(conn, view)
    bump_revision(conn)


def install_folder(conn: Connection, key: str, name: str) -> uuid.UUID:
    fid = stable_id("report_folder", key)
    conn.execute(
        text(
            "INSERT INTO report_folders (id, name, key, owner_id, visibility, shared_profile_ids, shared_role_ids, "
            "created_at, updated_at) VALUES (:id, :name, :key, NULL, 'public', '[]'::jsonb, '[]'::jsonb, now(), now()) "
            "ON CONFLICT DO NOTHING"
        ),
        {"id": fid, "name": name, "key": key},
    )
    return fid


def install_report(
    conn: Connection,
    key: str,
    folder_key: str,
    name: str,
    obj: str,
    definition: dict[str, Any],
    description: str | None = None,
    pack_key: str | None = None,
) -> uuid.UUID:
    rid = stable_id("report", key)
    conn.execute(
        text(
            "INSERT INTO reports (id, name, key, description, folder_id, owner_id, object_api_name, definition, pack_key, "
            "created_at, updated_at) VALUES (:id, :name, :key, :description, :folder, NULL, :obj, CAST(:definition AS jsonb), "
            ":pack, now(), now()) ON CONFLICT DO NOTHING"
        ),
        {
            "id": rid,
            "name": name,
            "key": key,
            "description": description,
            "folder": stable_id("report_folder", folder_key),
            "obj": obj,
            "definition": _j(definition),
            "pack": pack_key,
        },
    )
    return rid


def install_dashboard(
    conn: Connection,
    key: str,
    folder_key: str,
    name: str,
    components: list[dict[str, Any]],
    description: str | None = None,
    pack_key: str | None = None,
) -> uuid.UUID:
    did = stable_id("dashboard", key)
    comps = [{**c, "report_id": str(stable_id("report", c["report"]))} for c in components]
    for c in comps:
        c.pop("report", None)
    conn.execute(
        text(
            "INSERT INTO dashboards (id, name, key, description, folder_id, owner_id, running_user_id, components, pack_key, "
            "created_at, updated_at) VALUES (:id, :name, :key, :description, :folder, NULL, NULL, CAST(:components AS jsonb), "
            ":pack, now(), now()) ON CONFLICT DO NOTHING"
        ),
        {
            "id": did,
            "name": name,
            "key": key,
            "description": description,
            "folder": stable_id("report_folder", folder_key),
            "components": _j(comps),
            "pack": pack_key,
        },
    )
    return did

"""Metadata as the current user may see it (GET /meta/...): fields filtered by field-level security,
related lists and tabs filtered by object permissions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select

from app.engine import hooks
from app.engine.meta import FieldMeta, ObjectMeta
from app.engine.records import RecordService
from app.models import App, ListView
from app.security.catalog import FieldAccess


def describe_field(svc: RecordService, meta: ObjectMeta, f: FieldMeta) -> dict[str, Any]:
    access = svc.field_access(meta, f)
    options = dict(f.options)
    if f.type in ("picklist", "multi_picklist"):
        options["values"] = f.picklist_values
    return {
        "api_name": f.api_name,
        "label": f.label,
        "type": f.type,
        "help_text": f.help_text,
        "required": f.required,
        "is_unique": f.is_unique,
        "external_id": f.external_id,
        "filterable": f.filterable and f.type != "encrypted_text",
        "sortable": f.type not in ("multi_picklist", "address", "encrypted_text", "long_text"),
        "searchable": f.searchable,
        "track_history": f.track_history,
        "is_custom": f.is_custom,
        "is_standard": f.is_standard,
        "is_system": f.is_system,
        "is_readonly": f.is_readonly,
        "indexed": f.indexed,
        "default_value": f.default_value,
        "default_access": f.default_access.value,
        "access": access.value,
        "options": options,
    }


def object_summary(svc: RecordService, meta: ObjectMeta) -> dict[str, Any]:
    access = svc.policy.object(meta.api_name) if not svc.system else None
    return {
        "api_name": meta.api_name,
        "label": meta.label,
        "plural_label": meta.plural_label,
        "description": meta.description,
        "icon": meta.icon,
        "color": meta.color,
        "is_custom": meta.is_custom,
        "pack_key": meta.pack_key,
        "is_detail_only": meta.is_detail_only,
        "searchable": meta.searchable,
        "allow_reports": meta.allow_reports,
        "access": {
            "read": access.read if access else True,
            "create": access.create if access else True,
            "edit": access.edit if access else True,
            "delete": access.delete if access else True,
            "view_all": access.view_all if access else True,
            "modify_all": access.modify_all if access else True,
        },
    }


def readable_objects(svc: RecordService) -> list[ObjectMeta]:
    out = []
    for meta in svc.registry.objects.values():
        if meta.pack_key and meta.pack_key not in svc.enabled_packs:
            continue
        if svc.system or svc.policy.object(meta.api_name).read:
            out.append(meta)
    return sorted(out, key=lambda m: m.label)


def visible_list_views(svc: RecordService, object_api: str) -> list[ListView]:
    uid = svc.user_id
    stmt = select(ListView).where(ListView.object_api_name == object_api)
    views = svc.db.scalars(stmt.order_by(ListView.key.is_(None), ListView.name)).all()
    out: list[ListView] = []
    for v in views:
        if (
            v.visibility == "public"
            or v.owner_id == uid
            or (
                v.visibility == "shared"
                and (
                    str(svc.policy.profile_id) in (v.shared_profile_ids or [])
                    or (
                        svc.policy.role_id is not None
                        and str(svc.policy.role_id) in (v.shared_role_ids or [])
                    )
                )
            )
        ):
            out.append(v)
    return out


def describe_object(svc: RecordService, meta: ObjectMeta) -> dict[str, Any]:
    fields = {
        f.api_name: describe_field(svc, meta, f)
        for f in meta.fields.values()
        if svc.field_access(meta, f) is not FieldAccess.HIDDEN
    }
    layout = []
    for section in meta.page_layout:
        names = [n for n in section.get("fields", []) if n in fields]
        if names:
            layout.append({"label": section["label"], "columns": section.get("columns", 2), "fields": names})
    related = []
    for item in meta.related_lists:
        child = svc.registry.objects.get(item.get("object", ""))
        if child is None or (child.pack_key and child.pack_key not in svc.enabled_packs):
            continue
        if not svc.system and not svc.policy.object(child.api_name).read:
            continue
        lookup = child.fields.get(item.get("field", ""))
        if lookup is None or svc.field_access(child, lookup) is FieldAccess.HIDDEN:
            continue
        cols = [
            c
            for c in item.get("columns", [])
            if c in child.fields and svc.field_access(child, child.fields[c]) is not FieldAccess.HIDDEN
        ]
        related.append(
            {
                **item,
                "columns": cols or ["name"],
                "object_label": child.plural_label,
                "can_create": svc.system or svc.policy.object(child.api_name).create,
            }
        )
    activity_objects = []
    for api in ("task", "event", "note", "file"):
        child = svc.registry.objects.get(api)
        if (
            child is None
            or "related_to" not in child.fields
            or meta.api_name not in child.fields["related_to"].targets
        ):
            continue
        acc = svc.policy.object(api)
        if svc.system or acc.read:
            activity_objects.append({"object": api, "can_create": svc.system or acc.create})
    path = meta.path_field
    actions = [
        {"name": a.name, "label": a.label, "requires_edit": a.requires_edit}
        for a in hooks.actions_for(meta.api_name, svc.enabled_packs)
        if not a.client_only
    ]
    return {
        **object_summary(svc, meta),
        "name_field_type": meta.name_field_type,
        "name_label": meta.name_label,
        "name_format": meta.name_format,
        "track_history": meta.track_history,
        "allow_activities": meta.allow_activities,
        "allow_files": meta.allow_files,
        "allow_notes": meta.allow_notes,
        "allow_queues": meta.allow_queues,
        "show_in_portal": meta.show_in_portal,
        "fields": fields,
        "page_layout": layout,
        "compact_layout": [f for f in meta.compact_layout if f in fields],
        "list_columns": [f for f in meta.list_columns if f in fields] or ["name"],
        "related_lists": related,
        "activity_objects": activity_objects,
        "path_field": path.api_name if path is not None and path.api_name in fields else None,
        "actions": actions,
        "list_views": [
            {
                "id": str(v.id),
                "name": v.name,
                "key": v.key,
                "visibility": v.visibility,
                "is_mine": v.owner_id == svc.user_id,
                "kanban_field": v.kanban_field,
            }
            for v in visible_list_views(svc, meta.api_name)
        ],
    }


def visible_apps(svc: RecordService) -> list[dict[str, Any]]:
    apps = svc.db.scalars(
        select(App)
        .where(
            App.is_active.is_(True), or_(App.pack_key.is_(None), App.pack_key.in_(svc.enabled_packs or {""}))
        )
        .order_by(App.sort_order, App.label)
    ).all()
    from app.services.settings import get_setting

    primary = (get_setting(svc.db, "workspace") or {}).get("primary_app")
    out = []
    for app in apps:
        if (
            app.profile_ids
            and str(svc.policy.profile_id) not in app.profile_ids
            and not svc.policy.is_system_admin
        ):
            continue
        tabs = []
        for t in app.tabs:
            if t["kind"] == "object":
                meta = svc.registry.objects.get(t["object"])
                if meta is None or (meta.pack_key and meta.pack_key not in svc.enabled_packs):
                    continue
                if not svc.policy.object(meta.api_name).read:
                    continue
                tabs.append(
                    {
                        "kind": "object",
                        "object": meta.api_name,
                        "label": meta.plural_label,
                        "icon": meta.icon,
                        "color": meta.color,
                    }
                )
            elif t["kind"] in ("reports", "dashboards"):
                if svc.policy.object("report" if t["kind"] == "reports" else "dashboard").read:
                    tabs.append({"kind": t["kind"], "label": t["kind"].capitalize()})
            elif t["kind"] == "calendar":
                if svc.policy.object("event").read:
                    tabs.append({"kind": "calendar", "label": "Calendar"})
            elif t["kind"] == "queues":
                tabs.append({"kind": "queues", "label": "Queues"})
            else:
                tabs.append({"kind": t["kind"], "label": "Home"})
        if not tabs:
            continue
        out.append(
            {
                "id": str(app.id),
                "key": app.key,
                "label": app.label,
                "description": app.description,
                "icon": app.icon,
                "color": app.color,
                "tabs": tabs,
                "is_primary": app.key == primary,
            }
        )
    return out

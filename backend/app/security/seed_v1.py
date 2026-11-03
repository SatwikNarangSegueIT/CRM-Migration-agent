"""Security defaults, version 1 (plan v3, sections 9-10).

FROZEN: this module is applied by an Alembic migration. Never edit it after release; ship changes as
seed_v2 plus a new migration. `apply()` is idempotent: it only inserts rows that are missing, so admin
changes to existing profiles are never overwritten.
"""

from __future__ import annotations

import uuid
from typing import Final

from sqlalchemy import Connection, text

NAMESPACE: Final = uuid.UUID("6f1b3c1e-6d4a-4c55-9a3e-0b1f8d2c9e10")


def stable_id(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{kind}:{key}")


# key, name, description, is_locked, is_portal
PROFILES: Final = (
    (
        "system_administrator",
        "System Administrator",
        "Full access to all data and Setup. Cannot be edited.",
        True,
        False,
    ),
    (
        "sales_manager",
        "Sales Manager",
        "Leads the sales team; sees the team's pipeline through the role hierarchy.",
        False,
        False,
    ),
    (
        "sales_representative",
        "Sales Representative",
        "Works own leads, accounts, contacts, opportunities and quotes.",
        False,
        False,
    ),
    (
        "service_agent",
        "Service Agent",
        "Works cases (own and queue); updates contacts and accounts.",
        False,
        False,
    ),
    (
        "marketing_user",
        "Marketing User",
        "Campaigns, segments, templates, e-mail sends and leads.",
        False,
        False,
    ),
    ("finance", "Finance", "Products, price books, invoices, payments and tax rates.", False, False),
    ("read_only", "Read Only (Auditor)", "Reads all data and the audit log; changes nothing.", False, False),
    ("customer_portal", "Customer Portal User", "External customer contact using the portal.", False, True),
)

GROUPS: Final[dict[str, tuple[str, ...]]] = {
    "account": ("account",),
    "contact": ("contact",),
    "lead": ("lead",),
    "opportunity": ("opportunity", "opportunity_product"),
    "product": ("product", "price_book", "price_book_entry"),
    "quote": ("quote", "quote_line"),
    "invoice": ("invoice", "invoice_line", "payment"),
    "tax_rate": ("tax_rate",),
    "case": ("case",),
    "campaign": ("campaign", "campaign_member", "segment", "email_template"),
    "email": ("email_send", "consent"),
    "activity": ("task", "event", "note", "file"),
    "report": ("report", "dashboard"),
}

# Plan v3 section 10, "Object permissions". "-" = no access.
_COLUMNS: Final = (
    "system_administrator",
    "sales_manager",
    "sales_representative",
    "service_agent",
    "marketing_user",
    "finance",
    "read_only",
    "customer_portal",
)
OBJECT_MATRIX: Final[dict[str, tuple[str, ...]]] = {
    "account":     ("RCED VA MA", "RCED", "RCE", "RE",   "R",    "R",          "R VA", "R"),
    "contact":     ("RCED VA MA", "RCED", "RCE", "RCE",  "RCE",  "R",          "R VA", "RE"),
    "lead":        ("RCED VA MA", "RCED", "RCE", "-",    "RCED", "-",          "R VA", "-"),
    "opportunity": ("RCED VA MA", "RCED", "RCE", "R",    "R",    "R VA",       "R VA", "-"),
    "product":     ("RCED VA MA", "R",    "R",   "R",    "R",    "RCED",       "R VA", "-"),
    "quote":       ("RCED VA MA", "RCED", "RCE", "-",    "-",    "R VA",       "R VA", "-"),
    "invoice":     ("RCED VA MA", "R",    "R",   "R",    "-",    "RCE VA MA",  "R VA", "R"),
    "tax_rate":    ("RCED VA MA", "R",    "R",   "-",    "-",    "RCED",       "R VA", "-"),
    "case":        ("RCED VA MA", "R",    "R",   "RCE",  "-",    "R",          "R VA", "RC"),
    "campaign":    ("RCED VA MA", "R",    "R",   "-",    "RCED", "-",          "R VA", "-"),
    "email":       ("RCED VA MA", "R",    "-",   "-",    "RCE",  "-",          "R VA", "-"),
    "activity":    ("RCED VA MA", "RCED", "RCED", "RCED", "RCED", "RCED",      "R VA", "-"),
    "report":      ("RCED VA MA", "RCED", "RC",  "RC",   "RCED", "RCED",       "R VA", "-"),
}  # fmt: skip
# Portal users may read/create notes and files (case comments, uploads); not tasks/events.
PORTAL_EXTRA: Final[dict[str, str]] = {"note": "RC", "file": "RC"}

# Plan v3 section 10, "System permissions by profile".
SYSTEM_MATRIX: Final[dict[str, tuple[str, ...]]] = {
    "system_administrator": (
        "manage_users",
        "customize_application",
        "manage_profiles_sharing",
        "manage_billing_settings",
        "manage_industry_packs",
        "view_setup",
        "view_audit_log",
        "import_data",
        "export_data",
        "send_mass_email",
        "manage_public_reports",
        "transfer_records",
        "manage_portal_users",
        "api_access",
    ),
    "sales_manager": ("import_data", "export_data", "manage_public_reports", "transfer_records"),
    "sales_representative": (),
    "service_agent": ("manage_portal_users",),
    "marketing_user": ("import_data", "export_data", "send_mass_email", "manage_public_reports"),
    "finance": ("manage_billing_settings", "import_data", "export_data", "manage_public_reports"),
    "read_only": ("view_setup", "view_audit_log", "export_data"),
    "customer_portal": (),
}

# Plan v3 section 10, "Default role hierarchy": key, name, parent key.
ROLES: Final = (
    ("ceo", "CEO", None),
    ("sales_director", "Sales Director", "ceo"),
    ("sales_manager", "Sales Manager", "sales_director"),
    ("sales_representative", "Sales Representative", "sales_manager"),
    ("service_manager", "Service Manager", "ceo"),
    ("service_agent", "Service Agent", "service_manager"),
    ("marketing_manager", "Marketing Manager", "ceo"),
    ("marketing_user", "Marketing User", "marketing_manager"),
    ("finance_manager", "Finance Manager", "ceo"),
    ("finance_officer", "Finance Officer", "finance_manager"),
)

# Plan v3 section 9, "Default org-wide sharing".
SHARING_DEFAULTS: Final[dict[str, str]] = {
    "account": "read", "contact": "read",
    "lead": "private", "opportunity": "private", "case": "private", "quote": "private", "invoice": "private",
    "campaign": "read", "product": "read", "price_book": "read", "email_template": "read",
    "segment": "read", "tax_rate": "read", "email_send": "private",
    "report": "private", "dashboard": "private",
    "opportunity_product": "controlled_by_parent", "price_book_entry": "controlled_by_parent",
    "quote_line": "controlled_by_parent", "invoice_line": "controlled_by_parent",
    "payment": "controlled_by_parent", "campaign_member": "controlled_by_parent",
    "consent": "controlled_by_parent",
    "task": "controlled_by_parent", "event": "controlled_by_parent",
    "note": "controlled_by_parent", "file": "controlled_by_parent",
}  # fmt: skip


def _flags(code: str) -> dict[str, bool]:
    code = code.strip()
    if code == "-":
        return dict.fromkeys(
            ("can_read", "can_create", "can_edit", "can_delete", "view_all", "modify_all"), False
        )
    parts = code.split()
    letters = parts[0] if parts[0] not in ("VA", "MA") else ""
    extra = set(parts[1:] if letters else parts)
    return {
        "can_read": "R" in letters or bool(extra),
        "can_create": "C" in letters,
        "can_edit": "E" in letters or "MA" in extra,
        "can_delete": "D" in letters,
        "view_all": "VA" in extra or "MA" in extra,
        "modify_all": "MA" in extra,
    }


def object_permission_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for group, codes in OBJECT_MATRIX.items():
        for profile_key, code in zip(_COLUMNS, codes, strict=True):
            for obj in GROUPS[group]:
                if profile_key == "customer_portal" and obj in PORTAL_EXTRA:
                    code_for = PORTAL_EXTRA[obj]
                else:
                    code_for = code
                flags = _flags(code_for)
                if flags["can_read"]:
                    rows.append(
                        {"profile_id": stable_id("profile", profile_key), "object_api_name": obj, **flags}
                    )
    return rows


def apply(conn: Connection) -> None:
    """Insert missing default rows (idempotent)."""
    for key, name, description, is_locked, is_portal in PROFILES:
        conn.execute(
            text(
                "INSERT INTO profiles (id, key, name, description, is_locked, is_portal, created_at, updated_at) "  # noqa: E501
                "VALUES (:id, :key, :name, :description, :is_locked, :is_portal, now(), now()) "
                "ON CONFLICT DO NOTHING"
            ),
            {
                "id": stable_id("profile", key),
                "key": key,
                "name": name,
                "description": description,
                "is_locked": is_locked,
                "is_portal": is_portal,
            },
        )
    for profile_key, perms in SYSTEM_MATRIX.items():
        for perm in perms:
            conn.execute(
                text(
                    "INSERT INTO profile_system_permissions (profile_id, permission) VALUES (:p, :perm) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"p": stable_id("profile", profile_key), "perm": perm},
            )
    for row in object_permission_rows():
        conn.execute(
            text(
                "INSERT INTO profile_object_permissions (profile_id, object_api_name, can_read, can_create, "
                "can_edit, can_delete, view_all, modify_all) VALUES (:profile_id, :object_api_name, :can_read, "  # noqa: E501
                ":can_create, :can_edit, :can_delete, :view_all, :modify_all) ON CONFLICT DO NOTHING"
            ),
            row,
        )
    paths: dict[str, str] = {}
    for key, name, parent in ROLES:
        role_id = stable_id("role", key)
        paths[key] = (paths[parent] if parent else "/") + f"{role_id}/"
        conn.execute(
            text(
                "INSERT INTO roles (id, key, name, parent_id, path, created_at, updated_at) "
                "VALUES (:id, :key, :name, :parent_id, :path, now(), now()) ON CONFLICT DO NOTHING"
            ),
            {
                "id": role_id,
                "key": key,
                "name": name,
                "parent_id": stable_id("role", parent) if parent else None,
                "path": paths[key],
            },
        )
    for obj, access in SHARING_DEFAULTS.items():
        conn.execute(
            text(
                "INSERT INTO sharing_defaults (object_api_name, access, grant_access_using_hierarchy) "
                "VALUES (:o, :a, true) ON CONFLICT DO NOTHING"
            ),
            {"o": obj, "a": access},
        )

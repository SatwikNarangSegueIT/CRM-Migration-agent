"""Security vocabulary: system permissions, object access flags, sharing levels, standard objects.

Plan v3, sections 9-10. Object-level and field-level grants are data (profiles), not code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class SystemPermission(StrEnum):
    MANAGE_USERS = "manage_users"
    CUSTOMIZE_APPLICATION = "customize_application"
    MANAGE_PROFILES_SHARING = "manage_profiles_sharing"
    MANAGE_BILLING_SETTINGS = "manage_billing_settings"
    MANAGE_INDUSTRY_PACKS = "manage_industry_packs"
    VIEW_SETUP = "view_setup"
    VIEW_AUDIT_LOG = "view_audit_log"
    IMPORT_DATA = "import_data"
    EXPORT_DATA = "export_data"
    SEND_MASS_EMAIL = "send_mass_email"
    MANAGE_PUBLIC_REPORTS = "manage_public_reports"
    TRANSFER_RECORDS = "transfer_records"
    MANAGE_PORTAL_USERS = "manage_portal_users"
    API_ACCESS = "api_access"


SYSTEM_PERMISSION_LABELS: Final[dict[SystemPermission, str]] = {
    SystemPermission.MANAGE_USERS: "Manage Users",
    SystemPermission.CUSTOMIZE_APPLICATION: "Customize Application",
    SystemPermission.MANAGE_PROFILES_SHARING: "Manage Profiles & Sharing",
    SystemPermission.MANAGE_BILLING_SETTINGS: "Manage Billing Settings",
    SystemPermission.MANAGE_INDUSTRY_PACKS: "Manage Industry Packs",
    SystemPermission.VIEW_SETUP: "View Setup",
    SystemPermission.VIEW_AUDIT_LOG: "View Audit Log",
    SystemPermission.IMPORT_DATA: "Import Data",
    SystemPermission.EXPORT_DATA: "Export Data",
    SystemPermission.SEND_MASS_EMAIL: "Send Mass Email",
    SystemPermission.MANAGE_PUBLIC_REPORTS: "Manage Public Reports & Dashboards",
    SystemPermission.TRANSFER_RECORDS: "Transfer Records",
    SystemPermission.MANAGE_PORTAL_USERS: "Manage Portal Users",
    SystemPermission.API_ACCESS: "API Access",
}


class SharingAccess(StrEnum):
    """Organisation-wide default for an object."""

    PRIVATE = "private"
    READ = "read"
    READ_WRITE = "read_write"
    CONTROLLED_BY_PARENT = "controlled_by_parent"


class ShareLevel(StrEnum):
    """Access granted by a sharing rule or manual share."""

    READ = "read"
    READ_WRITE = "read_write"


class FieldAccess(StrEnum):
    HIDDEN = "hidden"
    READ = "read"
    EDIT = "edit"


@dataclass(frozen=True)
class ObjectAccess:
    read: bool = False
    create: bool = False
    edit: bool = False
    delete: bool = False
    view_all: bool = False
    modify_all: bool = False

    @classmethod
    def parse(cls, code: str) -> ObjectAccess:
        """Parse the plan notation, e.g. "RCED VA MA", "RCE", "R VA", "-"."""
        code = code.strip()
        if code in ("", "-", "—"):
            return NO_ACCESS
        tokens = code.split()
        letters = tokens[0] if tokens and tokens[0] not in ("VA", "MA") else ""
        flags = set(tokens[1:] if letters else tokens)
        unknown = (set(letters) - set("RCED")) | (flags - {"VA", "MA"})
        if unknown:
            raise ValueError(f"Invalid object access code: {code!r}")
        access = cls(
            read="R" in letters or bool(flags),
            create="C" in letters,
            edit="E" in letters or "MA" in flags,
            delete="D" in letters,
            view_all="VA" in flags or "MA" in flags,
            modify_all="MA" in flags,
        )
        access.validate()
        return access

    def validate(self) -> None:
        if (self.create or self.edit or self.delete or self.view_all) and not self.read:
            raise ValueError("Create, edit, delete and view-all require read access")
        if self.modify_all and not (self.view_all and self.edit):
            raise ValueError("Modify-all requires view-all and edit")

    def code(self) -> str:
        letters = "".join(
            ch for ch, on in zip("RCED", (self.read, self.create, self.edit, self.delete), strict=True) if on
        )
        flags = [f for f, on in (("VA", self.view_all), ("MA", self.modify_all)) if on]
        return " ".join([letters, *flags]).strip() or "-"


NO_ACCESS: Final = ObjectAccess()


@dataclass(frozen=True)
class StandardObject:
    api_name: str
    label: str
    plural: str
    app: str
    sharing: SharingAccess


# Standard objects (plan v3, section 5). Metadata definitions arrive in phase 3; security references them by API name.
STANDARD_OBJECTS: Final[tuple[StandardObject, ...]] = (
    StandardObject("account", "Account", "Accounts", "sales", SharingAccess.READ),
    StandardObject("contact", "Contact", "Contacts", "sales", SharingAccess.READ),
    StandardObject("lead", "Lead", "Leads", "sales", SharingAccess.PRIVATE),
    StandardObject("opportunity", "Opportunity", "Opportunities", "sales", SharingAccess.PRIVATE),
    StandardObject(
        "opportunity_product",
        "Opportunity Product",
        "Opportunity Products",
        "sales",
        SharingAccess.CONTROLLED_BY_PARENT,
    ),
    StandardObject("product", "Product", "Products", "billing", SharingAccess.READ),
    StandardObject("price_book", "Price Book", "Price Books", "billing", SharingAccess.READ),
    StandardObject(
        "price_book_entry",
        "Price Book Entry",
        "Price Book Entries",
        "billing",
        SharingAccess.CONTROLLED_BY_PARENT,
    ),
    StandardObject("quote", "Quote", "Quotes", "billing", SharingAccess.PRIVATE),
    StandardObject("quote_line", "Quote Line", "Quote Lines", "billing", SharingAccess.CONTROLLED_BY_PARENT),
    StandardObject("invoice", "Invoice", "Invoices", "billing", SharingAccess.PRIVATE),
    StandardObject(
        "invoice_line", "Invoice Line", "Invoice Lines", "billing", SharingAccess.CONTROLLED_BY_PARENT
    ),
    StandardObject("payment", "Payment", "Payments", "billing", SharingAccess.CONTROLLED_BY_PARENT),
    StandardObject("tax_rate", "Tax Rate", "Tax Rates", "billing", SharingAccess.READ),
    StandardObject("case", "Case", "Cases", "service", SharingAccess.PRIVATE),
    StandardObject("campaign", "Campaign", "Campaigns", "marketing", SharingAccess.READ),
    StandardObject(
        "campaign_member",
        "Campaign Member",
        "Campaign Members",
        "marketing",
        SharingAccess.CONTROLLED_BY_PARENT,
    ),
    StandardObject("segment", "Segment", "Segments", "marketing", SharingAccess.READ),
    StandardObject("email_template", "Email Template", "Email Templates", "marketing", SharingAccess.READ),
    StandardObject("email_send", "Email Send", "Email Sends", "marketing", SharingAccess.PRIVATE),
    StandardObject("consent", "Consent", "Consents", "marketing", SharingAccess.CONTROLLED_BY_PARENT),
    StandardObject("task", "Task", "Tasks", "all", SharingAccess.CONTROLLED_BY_PARENT),
    StandardObject("event", "Event", "Events", "all", SharingAccess.CONTROLLED_BY_PARENT),
    StandardObject("note", "Note", "Notes", "all", SharingAccess.CONTROLLED_BY_PARENT),
    StandardObject("file", "File", "Files", "all", SharingAccess.CONTROLLED_BY_PARENT),
    StandardObject("report", "Report", "Reports", "analytics", SharingAccess.PRIVATE),
    StandardObject("dashboard", "Dashboard", "Dashboards", "analytics", SharingAccess.PRIVATE),
)
STANDARD_OBJECT_NAMES: Final[frozenset[str]] = frozenset(o.api_name for o in STANDARD_OBJECTS)

# Groups used by the plan's permission matrix rows.
OBJECT_GROUPS: Final[dict[str, tuple[str, ...]]] = {
    "Account": ("account",),
    "Contact": ("contact",),
    "Lead": ("lead",),
    "Opportunity (+ products)": ("opportunity", "opportunity_product"),
    "Product, Price Book": ("product", "price_book", "price_book_entry"),
    "Quote": ("quote", "quote_line"),
    "Invoice, Payment": ("invoice", "invoice_line", "payment"),
    "Tax Rate": ("tax_rate",),
    "Case": ("case",),
    "Campaign, Segment, Email Template": ("campaign", "campaign_member", "segment", "email_template"),
    "Email Send, Consent": ("email_send", "consent"),
    "Task, Event, Note, File": ("task", "event", "note", "file"),
    "Report, Dashboard": ("report", "dashboard"),
}

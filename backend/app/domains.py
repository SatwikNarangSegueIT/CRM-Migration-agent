"""Professions a workspace can be set up for (plan v4, sections 5 and 6).

Sign-up offers one card per domain. Provisioning calls ``apply_domain``, which installs the domain's pack
and makes the workspace feel built for the profession:
  - domain-first navigation: the pack's app comes first and is the home page; the generic Sales, Service,
    Marketing and Billing apps are hidden (not deleted) and can be switched back on in Setup -> Apps;
  - terminology: standard objects are renamed (Contact -> Client...) with their list views, related
    lists, lookups and reports following;
  - branding: the domain's colour unless the firm already chose one.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.meta import bump_revision, invalidate_cache
from app.models import App, FieldDefinition, ListView, ObjectDefinition, Report
from app.services import audit
from app.services.audit import AuditAction

DomainKey = Literal["legal", "migration", "accounting", "lending"]
GENERIC_APPS = ("sales", "service", "marketing", "billing")


@dataclass(frozen=True)
class Domain:
    key: DomainKey
    label: str
    profession: str
    description: str
    includes: tuple[str, ...]
    pack_key: str | None
    app_key: str = ""
    color: str = "#0176d3"
    # object api_name -> (label, plural label)
    terminology: dict[str, tuple[str, str]] = field(default_factory=dict)


DOMAINS: dict[str, Domain] = {
    d.key: d
    for d in (
        Domain(
            "legal",
            "Law firm",
            "Lawyers and legal practices",
            "Matters, parties, conflict checks, time recording, court dates and trust accounting.",
            ("Matters", "Conflict checks", "Time entries", "Court dates", "Trust ledger", "Costs disclosure"),
            "legal_practice",
            app_key="legal_practice",
            color="#1e3a8a",
            terminology={
                "contact": ("Client", "Clients"),
                "account": ("Organisation", "Organisations"),
                "lead": ("Enquiry", "Enquiries"),
            },
        ),
        Domain(
            "migration",
            "Migration agency",
            "Registered migration agents",
            "Visa matters, client documents, application stages, deadlines and Code of Conduct compliance.",
            ("Visa matters", "Document checklists", "Stages and deadlines", "Agreements", "Client portal"),
            "migration_agency",
            app_key="migration_practice",
            color="#0f766e",
            terminology={
                "contact": ("Client", "Clients"),
                "account": ("Organisation", "Organisations"),
                "lead": ("Enquiry", "Enquiries"),
            },
        ),
        Domain(
            "accounting",
            "Accounting practice",
            "Chartered accountants and tax agents",
            "Client entities, engagements, engagement letters, lodgement deadlines and document requests.",
            ("Engagements", "Engagement letters", "Lodgement deadlines", "Document requests", "Time entries"),
            "accounting_practice",
            app_key="accounting_practice",
            color="#6d28d9",
            terminology={
                "account": ("Client", "Clients"),
                "contact": ("Contact Person", "Contact People"),
                "lead": ("Prospect", "Prospects"),
            },
        ),
        Domain(
            "lending",
            "Loan broking",
            "Mortgage and finance brokers",
            "Loan applications from fact find to settlement, lenders, commissions and credit compliance.",
            ("Loan applications", "Fact finds", "Lender panel", "Commissions", "Credit guide and BID"),
            "loan_broker",
            app_key="loan_broking",
            color="#b45309",
            terminology={
                "contact": ("Client", "Clients"),
                "account": ("Organisation", "Organisations"),
                "lead": ("Enquiry", "Enquiries"),
            },
        ),
    )
}


def swap_words(text_value: str, pairs: list[tuple[str, str]]) -> str:
    """Replace several whole words in one pass, so a replacement is never renamed again
    ("Contacts" -> "Contact People" must not then become "Contact Person People")."""
    mapping = {old.lower(): new for old, new in pairs}
    if not mapping:
        return text_value
    pattern = "|".join(re.escape(old) for old in sorted(mapping, key=len, reverse=True))

    def repl(m: re.Match[str]) -> str:
        new = mapping[m.group(0).lower()]
        return new if m.group(0)[0].isupper() else new[0].lower() + new[1:]

    return re.sub(rf"\b(?:{pattern})\b", repl, text_value, flags=re.IGNORECASE)


# Labels written by the earlier two-pass rename; repaired by `app.cli refresh-domain-layouts`.
DOUBLE_RENAMES = (("Contact Person People", "Contact People"), ("contact Person People", "contact People"))


def repair_double_renames(db: Session) -> int:
    changed = 0

    def fix(value: str) -> str:
        for bad, good in DOUBLE_RENAMES:
            value = value.replace(bad, good)
        return value

    for f in db.scalars(select(FieldDefinition)):
        if fix(f.label) != f.label:
            f.label, changed = fix(f.label), changed + 1
    for obj in db.scalars(select(ObjectDefinition)):
        lists = obj.related_lists or []
        new_lists = [{**rl, "label": fix(rl.get("label", ""))} for rl in lists]
        if new_lists != lists:
            obj.related_lists, changed = new_lists, changed + 1
    for view in db.scalars(select(ListView)):
        if fix(view.name) != view.name:
            view.name, changed = fix(view.name), changed + 1
    for report in db.scalars(select(Report)):
        if fix(report.name) != report.name:
            report.name, changed = fix(report.name), changed + 1
    return changed


def apply_terminology(db: Session, terms: dict[str, tuple[str, str]]) -> int:
    """Rename standard objects and everything that names them. Returns the number of rows changed."""
    changed = 0
    objects = {o.api_name: o for o in db.scalars(select(ObjectDefinition))}
    pairs: list[tuple[str, str]] = []  # (old word, new word), plurals first so "Contacts" wins over "Contact"
    for api, (label, plural) in terms.items():
        obj = objects.get(api)
        if obj is None or (obj.label, obj.plural_label) == (label, plural):
            continue
        pairs = [(obj.plural_label, plural), *pairs, (obj.label, label)]
        obj.label, obj.plural_label = label, plural
        changed += 1
    if not pairs:
        return 0

    def rename(value: str) -> str:
        return swap_words(value, pairs)

    targets = set(terms)
    for f in db.scalars(select(FieldDefinition)):
        target = (f.options or {}).get("target")
        if f.type in ("lookup", "master_detail") and target in targets:
            new = rename(f.label)
            if new != f.label:
                f.label, changed = new, changed + 1
    for obj in objects.values():
        lists = obj.related_lists or []
        new_lists = [
            {**rl, "label": rename(rl["label"])} if rl.get("object") in targets else rl for rl in lists
        ]
        if new_lists != lists:
            obj.related_lists, changed = new_lists, changed + 1
    for view in db.scalars(select(ListView).where(ListView.object_api_name.in_(targets))):
        new = rename(view.name)
        if new != view.name:
            view.name, changed = new, changed + 1
    for report in db.scalars(select(Report).where(Report.owner_id.is_(None))):
        new = rename(report.name)
        if new != report.name:
            report.name, changed = new, changed + 1
    return changed


def apply_navigation(db: Session, app_key: str) -> None:
    """The domain app first (and the home page); generic apps hidden but kept."""
    for app in db.scalars(select(App)):
        if app.key == app_key:
            app.sort_order, app.is_active = 1, True
        elif app.key in GENERIC_APPS:
            app.is_active = False


# Kept on every record page even when no visible app lists them (privacy consent is a legal record).
ALWAYS_RELATED = frozenset({"consent"})


def apply_related_lists(db: Session) -> int:
    """Related lists follow the visible apps: drop lists of objects only hidden apps use (opportunities,
    cases and campaigns in a law firm) and add one for each app object that looks the record up (a
    client's matters). Returns the number of objects changed."""
    visible: set[str] = set()
    hidden_apps: set[str] = set()
    for app in db.scalars(select(App)):
        tab_objects = {t["object"] for t in (app.tabs or []) if t.get("kind") == "object" and t.get("object")}
        if app.is_active:
            visible |= tab_objects
        else:
            hidden_apps |= tab_objects
    # Only objects that belong to hidden apps and to no visible one are dropped; children reached only from
    # a record (a matter's checklist items) stay.
    hidden = hidden_apps - visible - ALWAYS_RELATED
    objects = {o.api_name: o for o in db.scalars(select(ObjectDefinition))}
    by_id = {o.id: o for o in objects.values()}
    lookups: dict[str, list[tuple[ObjectDefinition, FieldDefinition]]] = {}
    for f in db.scalars(select(FieldDefinition).where(FieldDefinition.type.in_(("lookup", "master_detail")))):
        child = by_id.get(f.object_id)
        target = (f.options or {}).get("target")
        if (
            child is not None
            and target
            and child.pack_key  # the profession's own records, e.g. matter.client
            and not f.is_readonly
            and child.api_name in visible
            and child.api_name != target
        ):
            lookups.setdefault(target, []).append((child, f))
    # Records that only exist under a hidden parent (a campaign's members) are hidden with it.
    tab_objects = visible | hidden_apps
    for f in db.scalars(select(FieldDefinition).where(FieldDefinition.type.in_(("lookup", "master_detail")))):
        child = by_id.get(f.object_id)
        target = (f.options or {}).get("target")
        if (
            child is not None
            and child.api_name not in tab_objects
            and target in hidden
            and (f.required or f.type == "master_detail")
        ):
            hidden.add(child.api_name)
    hidden -= ALWAYS_RELATED
    views = {
        v.object_api_name: v.columns
        for v in db.scalars(select(ListView).where(ListView.owner_id.is_(None)).order_by(ListView.name))
    }
    changed = 0
    for obj in objects.values():
        current = list(obj.related_lists or [])
        kept = [rl for rl in current if rl.get("object") not in hidden]
        present = {(rl.get("object"), rl.get("field")) for rl in kept}
        added = 0
        for child, f in lookups.get(obj.api_name, []):
            if (child.api_name, f.api_name) in present:
                continue
            columns = [c for c in (views.get(child.api_name) or ["name"]) if c != f.api_name][:4]
            label = (
                child.plural_label
                if f.label in (obj.label, obj.name_label)
                else f"{child.plural_label} ({f.label})"
            )
            # The main relationship (e.g. matter.client) goes first: it's what people open the record for.
            kept.insert(
                added, {"field": f.api_name, "label": label, "object": child.api_name, "columns": columns}
            )
            present.add((child.api_name, f.api_name))
            added += 1
        if kept != current:
            obj.related_lists = kept
            changed += 1
    return changed


# ------------------------------------------------------------------ forms

# Bump when apply_forms changes: existing workspaces are brought up to date at start-up.
FORMS_VERSION = 1

# Sales-oriented fields that a profession workspace doesn't use. They're taken off the page layouts (so off
# the forms and record pages), not deleted: an administrator can put them back in Object Manager.
HIDDEN_FROM_LAYOUT: dict[str, set[str]] = {
    "lead": {"rating", "campaign", "industry", "annual_revenue", "employees"},
    "contact": {"department", "reports_to"},
    "account": {"annual_revenue", "employees", "shipping_address"},
    "invoice": {"opportunity", "quote"},
}

# Where the profession's own client/organisation fields go: (domain, object) -> section label.
PACK_SECTIONS: dict[tuple[str, str], str] = {
    ("legal", "contact"): "Identity",
    ("legal", "account"): "Company Details",
    ("migration", "contact"): "Immigration and Privacy",
    ("migration", "account"): "Sponsorship",
    ("accounting", "account"): "Tax and Entity",
    ("lending", "contact"): "Borrower Details",
}

# Filled in later in the work (or by the system): not asked for when creating the record.
HIDE_ON_CREATE: dict[str, set[str]] = {
    "legal_matter": {"stage", "status"},
    "conflict_check": {"result"},
    "matter": {"stage", "status", "immi_trn", "decision_date", "outcome", "grant_number", "visa_expiry"},
    "engagement": {"stage", "ato_reference"},
    "lodgement_deadline": {"status", "lodged_on"},
    "loan_application": {
        "stage",
        "lender_reference",
        "approval_expiry",
        "settlement_date",
        "rate_review_date",
        "decline_reason",
    },
    "commission": {"received_date"},
    "checklist_item": {"status", "sort_order"},
    "document_request": {"status", "sort_order"},
    "fact_find": {"status"},
}
# What the system fills in when a field is left empty, said on the form (only where there's no hint yet).
FORM_HINTS: dict[tuple[str, str], str] = {
    ("legal_matter", "responsible_solicitor"): "Leave empty to make it you.",
    ("legal_matter", "hourly_rate"): "Leave empty for the practice's default rate.",
    ("legal_matter", "estimated_costs"): "Costs disclosure is required above $750 (unless pro bono).",
    ("legal_time_entry", "timekeeper"): "Leave empty to make it you.",
    ("legal_time_entry", "rate"): "Leave empty for the matter's rate.",
    ("legal_time_entry", "units"): "1 unit = 6 minutes (1.5 hours = 15 units).",
    ("matter", "visa_type"): "Fills the fees and creates the document checklist.",
    ("matter", "professional_fee"): "Leave empty to use the visa type's fee.",
    ("matter", "government_fee"): "Leave empty to use the visa type's fee.",
    (
        "service_agreement",
        "consumer_guide_provided",
    ): "Required before the agreement can be sent (Code of Conduct).",
    ("engagement", "financial_year"): "Leave empty: set automatically for the engagement type.",
    ("engagement", "due_date"): "Leave empty to use the practice's due date for this return.",
    ("engagement", "responsible_accountant"): "Leave empty to make it you.",
    ("engagement", "reviewer"): "Someone other than the responsible accountant.",
    ("engagement_time_entry", "staff"): "Leave empty to make it you.",
    ("engagement_time_entry", "rate"): "Leave empty for the practice's charge-out rate.",
    ("engagement_time_entry", "units"): "1 unit = 6 minutes (1.5 hours = 15 units).",
    ("loan_application", "broker"): "Leave empty to make it you.",
    ("loan_application", "security_value"): "The LVR is calculated from the loan amount and this value.",
    ("commission", "amount"): "Always positive: a clawback is recorded as a negative amount.",
}
FIELD_RENAMES: dict[tuple[str, str], str] = {
    ("contact", "lead_source"): "Source",
    ("lead", "lead_source"): "Source",
}

SECTION_RENAMES = {
    "contact": "Contact Information",
    "account": "Account Information",
    "lead": "Lead Information",
}

# Clearer names for the name field of the profession's detail records.
NAME_LABELS = {"checklist_item": "Document", "document_request": "Document", "party": "Party Name"}

# Records the system names (see the hooks): their name is taken off the layout, so forms don't ask for it.
AUTO_NAMED = ("court_date",)


def apply_forms(db: Session, domain: str) -> int:
    """Shape the forms (page layouts) for the profession. Returns the number of objects changed."""
    objects = {o.api_name: o for o in db.scalars(select(ObjectDefinition))}
    fields_by_object: dict[str, list[FieldDefinition]] = {}
    by_id = {o.id: o for o in objects.values()}
    for f in db.scalars(select(FieldDefinition).order_by(FieldDefinition.sort_order)):
        owner = by_id.get(f.object_id)
        if owner is not None:
            fields_by_object.setdefault(owner.api_name, []).append(f)
    pack_objects = {api for api, o in objects.items() if o.pack_key}
    order = _pack_field_order(domain)
    changed = 0

    for api, obj in objects.items():
        if obj.pack_key:
            continue
        fields = {f.api_name: f for f in fields_by_object.get(api, [])}
        hidden = set(HIDDEN_FROM_LAYOUT.get(api, set()))
        if api == "contact" and "date_of_birth" in fields:
            hidden.add("birthdate")  # the profession's Date of Birth replaces the generic Birthdate
        layout = [
            {**sec, "fields": [f for f in sec.get("fields", []) if f not in hidden]}
            for sec in obj.page_layout or []
        ]
        layout = [sec for sec in layout if sec["fields"]]
        # Section headings use the profession's words ("Client Information", not "Contact Information").
        generic = SECTION_RENAMES.get(api)
        if generic:
            layout = [
                {**sec, "label": f"{obj.label} Information"} if sec.get("label") == generic else sec
                for sec in layout
            ]
        placed = _layout_fields_from(layout)
        # Fields the profession added to this standard object, not on the layout yet.
        extra = [
            f.api_name
            for f in fields_by_object.get(api, [])
            if f.api_name not in placed and not f.is_standard
        ]
        links = [n for n in extra if (fields[n].options or {}).get("target") in pack_objects]
        others = sorted((n for n in extra if n not in links), key=lambda n: order.get((api, n), 999))
        # A section added earlier keeps the profession's field order.
        label = PACK_SECTIONS.get((domain, api), "Practice Details")
        layout = [
            {**sec, "fields": sorted(sec["fields"], key=lambda n: order.get((api, n), 999))}
            if sec.get("label") == label
            else sec
            for sec in layout
        ]
        if links and layout:
            first = layout[0]["fields"]
            at = first.index("contact") + 1 if "contact" in first else len(first)
            layout[0] = {**layout[0], "fields": first[:at] + links + first[at:]}
        if others:
            at = next(
                (
                    i
                    for i, sec in enumerate(layout)
                    if sec.get("label") in ("Description", "System Information")
                ),
                len(layout),
            )
            layout.insert(at, {"label": label, "columns": 2, "fields": others})
        if layout != (obj.page_layout or []):
            obj.page_layout = layout
            changed += 1

    # An enquiry is often a person, not a company.
    lead_company = next((f for f in fields_by_object.get("lead", []) if f.api_name == "company"), None)
    if lead_company is not None and lead_company.required:
        lead_company.required = False
        changed += 1

    for api, names in HIDE_ON_CREATE.items():
        for f in fields_by_object.get(api, []):
            if f.api_name in names and not (f.options or {}).get("hide_on_create"):
                f.options = {**(f.options or {}), "hide_on_create": True}
                changed += 1
    for api, fields_ in fields_by_object.items():
        for f in fields_:
            hint = FORM_HINTS.get((api, f.api_name))
            if hint and not f.help_text:
                f.help_text = hint
                changed += 1
            label = FIELD_RENAMES.get((api, f.api_name))
            if label and f.label != label:
                f.label = label
                changed += 1
    for api, label in NAME_LABELS.items():
        obj = objects.get(api)
        if obj is not None and obj.name_label == "Name":
            obj.name_label = label
            changed += 1
    for api in AUTO_NAMED:
        obj = objects.get(api)
        if obj is not None and "name" in _layout_fields_from(obj.page_layout or []):
            obj.page_layout = [
                {**sec, "fields": [f for f in sec.get("fields", []) if f != "name"]}
                for sec in obj.page_layout
            ]
            changed += 1
    return changed


def _pack_field_order(domain: str) -> dict[tuple[str, str], int]:
    """(object, field) -> position, as the profession's pack lists the fields it adds to standard objects."""
    from app import packs

    spec = DOMAINS.get(domain)
    if spec is None or spec.pack_key is None:
        return {}
    try:
        fields = packs.get(spec.pack_key).bundle().get("fields", [])
    except Exception:
        return {}
    return {(f.get("object", ""), f["api_name"]): i for i, f in enumerate(fields)}


def _layout_fields_from(layout: list[dict[str, Any]]) -> set[str]:
    return {f for s in layout for f in s.get("fields", [])}


def upgrade_domain_workspace(db: Session, *, force: bool = False) -> int:
    """Bring a profession workspace's related lists and forms up to date (idempotent). Caller commits."""
    from app.services.settings import get_setting, set_setting

    workspace = dict(get_setting(db, "workspace") or {})
    domain = workspace.get("domain")
    if not domain or (not force and int(workspace.get("forms_version") or 0) >= FORMS_VERSION):
        return 0
    changed = apply_related_lists(db) + repair_double_renames(db) + apply_forms(db, str(domain))
    set_setting(db, "workspace", {**workspace, "forms_version": FORMS_VERSION})
    if changed:
        bump_revision(db)
    return changed


def apply_domain(db: Session, domain: str, actor_id: uuid.UUID | None) -> None:
    """Install the domain's pack and shape the workspace for the profession. Caller commits."""
    from app import packs
    from app.services.settings import get_setting, set_setting

    spec = DOMAINS.get(domain)
    if spec is None or spec.pack_key is None:
        return
    if spec.pack_key not in {p.key for p in packs.available()}:
        return
    packs.install(db, spec.pack_key, actor_id)
    db.flush()
    apply_navigation(db, spec.app_key)
    apply_terminology(db, spec.terminology)
    db.flush()
    apply_related_lists(db)
    apply_forms(db, spec.key)
    set_setting(
        db, "workspace", {"domain": spec.key, "primary_app": spec.app_key, "forms_version": FORMS_VERSION}
    )
    branding: dict[str, Any] = dict(get_setting(db, "branding") or {})
    if not branding.get("primary_color") or branding.get("primary_color") == "#0176d3":
        branding["primary_color"] = spec.color
        set_setting(db, "branding", branding)
    bump_revision(db)
    invalidate_cache()
    audit.record(
        db,
        action=AuditAction.UPDATE,
        entity_type="workspace",
        entity_id=spec.key,
        summary=f"Workspace set up for {spec.label}: {spec.app_key} app first, terminology applied",
        actor_id=actor_id,
    )


def upgrade_all_domain_workspaces(*, force: bool = False) -> dict[str, int]:
    """Run upgrade_domain_workspace in every active workspace (API start-up and `app.cli`). Safe to run from
    several processes at once: each workspace is upgraded under a transaction-level advisory lock."""
    import logging

    from sqlalchemy import text

    from app.db.session import get_sessionmaker
    from app.tenancy import active_tenants, bind_tenant

    results: dict[str, int] = {}
    for tenant in active_tenants():
        try:
            with get_sessionmaker()() as db:
                bind_tenant(db, tenant)
                db.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:s))"), {"s": "forms:" + tenant.schema}
                )
                changed = upgrade_domain_workspace(db, force=force)
                db.commit()
            if changed:
                invalidate_cache()
            results[tenant.slug or tenant.schema] = changed
        except Exception:
            logging.getLogger("app.domains").exception(
                "Workspace upgrade failed", extra={"tenant": tenant.schema}
            )
    return results

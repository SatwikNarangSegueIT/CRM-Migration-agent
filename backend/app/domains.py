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

from app.domain_content import apply_content
from app.engine.meta import bump_revision, invalidate_cache
from app.models import App, FieldDefinition, ListView, ObjectDefinition, Report
from app.pack_upgrade import mark_forms_current, upgrade_pack
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


# Phrases where "account" isn't the CRM's account (organisation): a client's trust money.
KEEP_PHRASES = ("Client Account", "Client Accounts", "Trust Account", "Trust Accounts")


def swap_words(text_value: str, pairs: list[tuple[str, str]]) -> str:
    """Replace several whole words in one pass, so a replacement is never renamed again
    ("Contacts" -> "Contact People" must not then become "Contact Person People")."""
    mapping = {old.lower(): new for old, new in pairs}
    if not mapping:
        return text_value
    keep = {p.lower() for p in KEEP_PHRASES}
    pattern = "|".join(re.escape(old) for old in sorted(set(mapping) | keep, key=len, reverse=True))

    def repl(m: re.Match[str]) -> str:
        if m.group(0).lower() in keep:
            return m.group(0)
        new = mapping[m.group(0).lower()]
        return new if m.group(0)[0].isupper() else new[0].lower() + new[1:]

    return re.sub(rf"\b(?:{pattern})\b", repl, text_value, flags=re.IGNORECASE)


# Labels written by the earlier two-pass rename; repaired by `app.cli refresh-domain-layouts`.
DOUBLE_RENAMES = (
    ("Contact Person People", "Contact People"),
    ("contact Person People", "contact People"),
    ("Client Organisation Balances", "Client Account Balances"),
)


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
FORMS_VERSION = 8

# Sales-oriented fields that a profession workspace doesn't use. They're taken off the page layouts (so off
# the forms and record pages), not deleted: an administrator can put them back in Object Manager.
HIDDEN_FROM_LAYOUT: dict[str, set[str]] = {
    "lead": {
        "rating",
        "campaign",
        "industry",
        "annual_revenue",
        "employees",
        "title",
        "website",
        "converted_opportunity",
    },
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
    "matter": {
        "stage",
        "status",
        "immi_trn",
        "decision_date",
        "outcome",
        "grant_number",
        "visa_expiry",
        "information_due",
        "bridging_visa",
        "nomination_approved_date",
    },
    "trust_reconciliation": {"status"},
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
    ("invoice", "account"): "Leave empty to bill an individual client in their own name.",
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
AUTO_NAMED = ("court_date", "trust_reconciliation")


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

    # An enquiry is often a person, not a company; an invoice for an individual is billed through the
    # client (the organisation in their name is filled in by the system).
    for api, name in (("lead", "company"), ("invoice", "account")):
        optional = next((f for f in fields_by_object.get(api, []) if f.api_name == name), None)
        if optional is not None and optional.required:
            optional.required = False
            changed += 1

    for api, names in HIDE_ON_CREATE.items():
        for f in fields_by_object.get(api, []):
            if f.api_name in names and not (f.options or {}).get("hide_on_create"):
                f.options = {**(f.options or {}), "hide_on_create": True}
                changed += 1
    for api, fields_ in fields_by_object.items():
        for f in fields_:
            hint: str | None = FORM_HINTS.get((api, f.api_name))
            if hint and not f.help_text:
                f.help_text = hint
                changed += 1
            new_label = FIELD_RENAMES.get((api, f.api_name))
            if new_label and f.label != new_label:
                f.label = new_label
                changed += 1
    for api, label in NAME_LABELS.items():
        named = objects.get(api)
        if named is not None and named.name_label == "Name":
            named.name_label = label
            changed += 1
    for api in AUTO_NAMED:
        auto = objects.get(api)
        if auto is not None and "name" in _layout_fields_from(auto.page_layout or []):
            auto.page_layout = [
                {**sec, "fields": [f for f in sec.get("fields", []) if f != "name"]}
                for sec in auto.page_layout
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


# The profession's top profile runs the practice: it edits every record of the profession, not only the ones
# it owns (clearing a solicitor's conflict check, writing off their time). Version 1 packs gave View All
# without Modify All.
PRINCIPAL_MODIFY_ALL: dict[str, tuple[str, tuple[str, ...]]] = {
    "legal": (
        "lp_principal",
        (
            "legal_matter",
            "party",
            "conflict_check",
            "legal_time_entry",
            "court_date",
            "invoice",
            "account",
            "contact",
        ),
    ),
    "migration": (
        "ma_practice_manager",
        (
            "matter",
            "matter_applicant",
            "checklist_item",
            "service_agreement",
            "visa_type",
            "contact",
            "account",
        ),
    ),
    "accounting": (
        "ap_partner",
        (
            "engagement",
            "engagement_letter",
            "lodgement_deadline",
            "document_request",
            "engagement_time_entry",
            "invoice",
            "account",
            "contact",
        ),
    ),
    "lending": (
        "lb_principal",
        ("loan_application", "lender", "fact_find", "commission", "contact", "account"),
    ),
}


# Other profiles that work every client's file: a registered migration agent records passport and visa
# details on clients intake created.
EXTRA_MODIFY_ALL: dict[str, list[tuple[str, tuple[str, ...]]]] = {
    "migration": [("ma_registered_agent", ("contact", "account"))],
}


def apply_principal_access(db: Session, domain: str) -> int:
    """Modify All for the top profile on the profession's records, where the grant is still the shipped
    default (read, create, edit, delete) - a grant an administrator narrowed is left alone."""
    from app.models import Profile, ProfileObjectPermission

    specs = [PRINCIPAL_MODIFY_ALL[domain]] if domain in PRINCIPAL_MODIFY_ALL else []
    specs += EXTRA_MODIFY_ALL.get(domain, [])
    changed = 0
    for key, objects in specs:
        profile = db.scalar(select(Profile).where(Profile.key == key))
        if profile is None:
            continue
        for perm in db.scalars(
            select(ProfileObjectPermission).where(
                ProfileObjectPermission.profile_id == profile.id,
                ProfileObjectPermission.object_api_name.in_(objects),
            )
        ):
            if perm.can_read and perm.can_edit and not perm.modify_all:
                perm.view_all, perm.modify_all = True, True
                changed += 1
    return changed


# Rights a shipped profile should always have had (found in the deep pass), added on upgrade. Additive:
# nothing is taken away.
ACCESS_FIXES: dict[str, list[tuple[str, str, str]]] = {
    "migration": [
        ("ma_registered_agent", "invoice_line", "RCED"),
        ("ma_registered_agent", "client_account_transaction", "R VA"),
    ],
    "lending": [("lb_admin", "commission", "RCE VA MA")],
    "accounting": [
        ("ap_practice_admin", "account", "RCE VA"),
        ("ap_practice_admin", "contact", "RCE VA"),
    ],
}


def _grant(db: Session, profile_id: uuid.UUID, obj: str, code: str) -> bool:
    from app.models import ProfileObjectPermission
    from app.security.seed_v1 import _flags

    flags = _flags(code)
    perm = db.get(ProfileObjectPermission, (profile_id, obj))
    if perm is None:
        db.add(ProfileObjectPermission(profile_id=profile_id, object_api_name=obj, **flags))
        return True
    changed = False
    for k, v in flags.items():
        if v and not getattr(perm, k):
            setattr(perm, k, True)
            changed = True
    return changed


PORTAL_REFERENCE: dict[str, tuple[str, tuple[str, ...]]] = {
    "migration": (
        "visa_type",
        ("default_professional_fee", "default_government_fee", "checklist_template", "description"),
    ),
    "lending": (
        "lender",
        (
            "upfront_rate",
            "trail_rate",
            "clawback_months",
            "accreditation_number",
            "bdm_name",
            "bdm_email",
            "bdm_phone",
            "notes",
        ),
    ),
}


def apply_pack_grants(db: Session, domain: str) -> int:
    """Object access a profession pack's profiles ship with that a workspace built earlier lacks (no
    access at all). Rights a profile already has, or an administrator set, are never reduced."""
    import importlib

    from app.models import Profile, ProfileObjectPermission
    from app.security.seed_v1 import _flags

    spec = DOMAINS.get(domain)
    if spec is None or spec.pack_key is None:
        return 0
    definition = importlib.import_module(f"app.packs.{spec.pack_key}.definition")
    profiles = getattr(definition, "PROFILES", None) or []
    changed = 0
    reference = PORTAL_REFERENCE.get(domain)
    if reference is not None:
        # Portal clients read this reference list (names only), so their record shows its visa / lender.
        from app.models import ProfileFieldPermission

        obj, hidden = reference
        portal = db.scalar(select(Profile).where(Profile.key == "customer_portal"))
        if portal is not None and db.get(ProfileObjectPermission, (portal.id, obj)) is None:
            db.add(ProfileObjectPermission(profile_id=portal.id, object_api_name=obj, can_read=True))
            for f in hidden:
                db.merge(
                    ProfileFieldPermission(
                        profile_id=portal.id, object_api_name=obj, field_api_name=f, access="hidden"
                    )
                )
            changed += 1
    for key, _name, _desc, _base, objects, *_rest in profiles:
        profile = db.scalar(select(Profile).where(Profile.key == key))
        if profile is None:
            continue
        for obj, code in objects.items():
            perm = db.get(ProfileObjectPermission, (profile.id, obj))
            flags = _flags(code)
            if perm is not None and perm.can_read:
                # Read everything the pack ships with "VA" (an agent sees each client's account).
                if flags["view_all"] and not perm.view_all:
                    perm.view_all = True
                    changed += 1
                continue
            if not flags["can_read"]:
                continue
            if perm is None:
                db.add(ProfileObjectPermission(profile_id=profile.id, object_api_name=obj, **flags))
            else:
                for k, v in flags.items():
                    setattr(perm, k, v)
            changed += 1
    db.flush()  # rows added above are found by db.get() below
    for key, obj, code in ACCESS_FIXES.get(domain, []):
        profile = db.scalar(select(Profile).where(Profile.key == key))
        if profile is not None and _grant(db, profile.id, obj, code):
            changed += 1
    return changed


PRODUCT_NAME = "Meridian CRM"


def apply_firm_name(db: Session, firm: str | None) -> int:
    """The firm's name on the portal, PDFs and client e-mails where the product's name was seeded."""
    from app.services.settings import get_setting, set_setting

    if not firm:
        return 0
    changed = 0
    for key, attr in (("branding", "name"), ("marketing", "from_name")):
        value = dict(get_setting(db, key) or {})
        if value.get(attr) in (None, "", PRODUCT_NAME):
            value[attr] = firm
            set_setting(db, key, value)
            changed += 1
    return changed


def apply_compact_layouts(db: Session) -> int:
    """Record-header highlights for profession objects installed before their pack shipped one."""
    from app import packs

    wanted: dict[str, list[str]] = {}
    for key in ("legal_practice", "migration_agency", "accounting_practice", "loan_broker"):
        objects_ = packs.get(key).bundle().get("objects", [])
        wanted.update({o["api_name"]: o["compact_layout"] for o in objects_ if o.get("compact_layout")})
    changed = 0
    for obj in db.scalars(select(ObjectDefinition).where(ObjectDefinition.api_name.in_(wanted))):
        if not obj.compact_layout:
            obj.compact_layout = list(wanted[obj.api_name])
            changed += 1
    return changed


def _firm_name(db: Session) -> str | None:
    from app.services.settings import get_setting
    from app.tenancy import current_tenant

    tenant = current_tenant(db)
    if tenant is not None and tenant.id is not None:
        return tenant.name
    return str((get_setting(db, "company") or {}).get("legal_name") or "") or None


def _commission_chart_in_dollars(db: Session) -> int:
    """The broking dashboard's commission chart shows net dollars by type (it counted entries)."""
    from app.models import Dashboard

    changed = 0
    report = db.scalar(select(Report).where(Report.key == "lb_commission_by_type"))
    if report is not None:
        aggs = list((report.definition or {}).get("aggregates", []))
        if aggs and aggs[-1].get("op") == "count":
            report.definition = {**report.definition, "aggregates": aggs[::-1], "chart": {"type": "bar"}}
            changed += 1
    dash = db.scalar(select(Dashboard).where(Dashboard.key == "lb_broker_dashboard"))
    if dash is not None:
        comps = [dict(c) for c in dash.components or []]
        for c in comps:
            if c.get("report") == "lb_commission_by_type" and c.get("chart") == "donut":
                c.update(chart="bar", title="Net commission by type")
                changed += 1
        dash.components = comps
    return changed


def _share_commissions_with_brokers(db: Session) -> int:
    """Brokers read the commission on their loans (commissions recorded before this was shared)."""
    from app.models import Record, RecordShare

    shared = set(
        db.scalars(
            select(RecordShare.record_id)
            .join(Record, Record.id == RecordShare.record_id)
            .where(Record.object_api_name == "commission", RecordShare.created_by_id.is_(None))
        )
    )
    added = 0
    for c in db.scalars(select(Record).where(Record.object_api_name == "commission")):
        broker = (c.data or {}).get("broker")
        if broker and c.id not in shared:
            db.add(
                RecordShare(
                    record_id=c.id,
                    principal_type="user",
                    principal_id=uuid.UUID(str(broker)),
                    access="read",
                    created_by_id=None,
                )
            )
            added += 1
    return added


def seed_starter_records(db: Session, domain: str, actor_id: uuid.UUID | None = None) -> int:
    """Reference data a profession can't start without (a migration agency's visa types)."""
    if domain == "lending":
        return _share_commissions_with_brokers(db) + _commission_chart_in_dollars(db)
    if domain != "migration":
        return 0
    from app.packs.migration_agency import seed_visa_types

    return seed_visa_types(db, actor_id)


def upgrade_domain_workspace(db: Session, *, force: bool = False) -> int:
    """Bring a profession workspace's related lists and forms up to date (idempotent). Caller commits."""
    from app.services.settings import get_setting, set_setting

    workspace = dict(get_setting(db, "workspace") or {})
    domain = workspace.get("domain")
    if not domain or (not force and int(workspace.get("forms_version") or 0) >= FORMS_VERSION):
        return 0
    spec = DOMAINS.get(str(domain))
    changed = upgrade_pack(db, spec.pack_key if spec else None)
    changed += (
        apply_related_lists(db)
        + repair_double_renames(db)
        + apply_forms(db, str(domain))
        + apply_principal_access(db, str(domain))
        + apply_pack_grants(db, str(domain))
        + apply_compact_layouts(db)
        + apply_content(db, str(domain))
        + apply_firm_name(db, _firm_name(db))
    )
    db.flush()
    invalidate_cache()
    changed += seed_starter_records(db, str(domain))
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
    mark_forms_current(db, spec.pack_key)
    apply_navigation(db, spec.app_key)
    apply_terminology(db, spec.terminology)
    db.flush()
    apply_related_lists(db)
    apply_forms(db, spec.key)
    apply_content(db, spec.key)
    set_setting(
        db, "workspace", {"domain": spec.key, "primary_app": spec.app_key, "forms_version": FORMS_VERSION}
    )
    branding: dict[str, Any] = dict(get_setting(db, "branding") or {})
    if not branding.get("primary_color") or branding.get("primary_color") == "#0176d3":
        branding["primary_color"] = spec.color
        set_setting(db, "branding", branding)
    apply_firm_name(db, _firm_name(db))
    bump_revision(db)
    invalidate_cache()
    db.flush()
    seed_starter_records(db, spec.key, actor_id)
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

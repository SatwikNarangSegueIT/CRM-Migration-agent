"""Role -> permission matrix. Single source of truth for authorisation.

Mirrors section 7 of docs/Implementation_Plan_v2.pdf. Each grant carries a scope:

* ``all``     - every record
* ``own``     - only records the user owns / is assigned to (enforced in queries by services)
* ``billing`` - reports limited to billing reports (ACCOUNTS)

A permission that is absent for a role is denied.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Final, Literal

Scope = Literal["all", "own", "billing"]


class Role(StrEnum):
    ADMIN = "ADMIN"
    PRACTICE_MANAGER = "PRACTICE_MANAGER"
    MIGRATION_AGENT = "MIGRATION_AGENT"
    CASE_OFFICER = "CASE_OFFICER"
    INTAKE_CONSULTANT = "INTAKE_CONSULTANT"
    ACCOUNTS = "ACCOUNTS"
    AUDITOR = "AUDITOR"
    CLIENT = "CLIENT"


ROLE_LABELS: Final[dict[Role, str]] = {
    Role.ADMIN: "Administrator",
    Role.PRACTICE_MANAGER: "Practice Manager",
    Role.MIGRATION_AGENT: "Registered Migration Agent",
    Role.CASE_OFFICER: "Case Officer",
    Role.INTAKE_CONSULTANT: "Intake Consultant",
    Role.ACCOUNTS: "Accounts",
    Role.AUDITOR: "Auditor (read-only)",
    Role.CLIENT: "Client",
}

STAFF_ROLES: Final[frozenset[Role]] = frozenset(r for r in Role if r is not Role.CLIENT)


class Permission(StrEnum):
    DASHBOARD_VIEW = "dashboard.view"
    SEARCH_GLOBAL = "search.global"

    LEAD_READ = "lead.read"
    LEAD_CREATE = "lead.create"
    LEAD_UPDATE = "lead.update"
    LEAD_ASSIGN = "lead.assign"
    LEAD_CONVERT = "lead.convert"
    LEAD_DELETE = "lead.delete"

    CONTACT_READ = "contact.read"
    CONTACT_CREATE = "contact.create"
    CONTACT_UPDATE = "contact.update"
    CONTACT_DELETE = "contact.delete"
    CONTACT_PORTAL_INVITE = "contact.portal_invite"

    ORGANISATION_READ = "organisation.read"
    ORGANISATION_CREATE = "organisation.create"
    ORGANISATION_UPDATE = "organisation.update"
    ORGANISATION_DELETE = "organisation.delete"

    MATTER_READ = "matter.read"
    MATTER_CREATE = "matter.create"
    MATTER_UPDATE = "matter.update"
    MATTER_ASSIGN = "matter.assign"
    MATTER_LODGE = "matter.lodge"
    MATTER_OVERRIDE = "matter.override"
    MATTER_DELETE = "matter.delete"

    TASK_READ = "task.read"
    TASK_CREATE = "task.create"
    TASK_UPDATE = "task.update"
    TASK_DELETE = "task.delete"
    ACTIVITY_CREATE = "activity.create"

    DOCUMENT_READ = "document.read"
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_DELETE = "document.delete"

    MESSAGE_READ = "message.read"
    MESSAGE_SEND = "message.send"

    AGREEMENT_READ = "agreement.read"
    AGREEMENT_MANAGE = "agreement.manage"
    AGREEMENT_SIGN = "agreement.sign"
    INVOICE_READ = "invoice.read"
    INVOICE_MANAGE = "invoice.manage"
    PAYMENT_RECORD = "payment.record"
    TRUST_READ = "trust.read"
    TRUST_MANAGE = "trust.manage"

    REPORT_VIEW = "report.view"
    REPORT_EXPORT = "report.export"
    VISA_MANAGE = "visa.manage"
    USER_MANAGE = "user.manage"
    SETTINGS_MANAGE = "settings.manage"
    AUDIT_READ = "audit.read"
    PORTAL_ACCESS = "portal.access"


P = Permission


def _grants(
    all_: Sequence[Permission] = (),
    own: Sequence[Permission] = (),
    billing: Sequence[Permission] = (),
) -> dict[Permission, Scope]:
    grants: dict[Permission, Scope] = {}
    groups: tuple[tuple[Scope, Sequence[Permission]], ...] = (
        ("all", all_),
        ("own", own),
        ("billing", billing),
    )
    for scope, perms in groups:
        for perm in perms:
            if perm in grants:
                raise ValueError(f"Duplicate grant for {perm}")
            grants[perm] = scope
    return grants


# Permissions every non-client role has on all records.
_ALL_STAFF_READ = [P.DASHBOARD_VIEW, P.CONTACT_READ, P.ORGANISATION_READ]

_ADMIN_ONLY = {P.USER_MANAGE, P.SETTINGS_MANAGE, P.MATTER_OVERRIDE, P.MATTER_DELETE}
_CLIENT_ONLY = {P.AGREEMENT_SIGN, P.PORTAL_ACCESS}

ROLE_PERMISSIONS: Final[dict[Role, dict[Permission, Scope]]] = {
    Role.ADMIN: _grants(all_=[p for p in Permission if p not in _CLIENT_ONLY]),
    Role.PRACTICE_MANAGER: _grants(all_=[p for p in Permission if p not in _CLIENT_ONLY | _ADMIN_ONLY]),
    Role.MIGRATION_AGENT: _grants(
        all_=[
            *_ALL_STAFF_READ,
            P.SEARCH_GLOBAL,
            P.LEAD_READ,
            P.LEAD_CREATE,
            P.LEAD_UPDATE,
            P.LEAD_ASSIGN,
            P.LEAD_CONVERT,
            P.CONTACT_CREATE,
            P.CONTACT_UPDATE,
            P.CONTACT_PORTAL_INVITE,
            P.ORGANISATION_CREATE,
            P.ORGANISATION_UPDATE,
            P.MATTER_READ,
            P.MATTER_CREATE,
            P.MATTER_UPDATE,
            P.MATTER_ASSIGN,
            P.MATTER_LODGE,
            P.TASK_READ,
            P.TASK_CREATE,
            P.TASK_UPDATE,
            P.TASK_DELETE,
            P.ACTIVITY_CREATE,
            P.DOCUMENT_READ,
            P.DOCUMENT_UPLOAD,
            P.DOCUMENT_DELETE,
            P.MESSAGE_READ,
            P.MESSAGE_SEND,
            P.AGREEMENT_READ,
            P.AGREEMENT_MANAGE,
            P.INVOICE_READ,
            P.INVOICE_MANAGE,
            P.TRUST_READ,
            P.REPORT_VIEW,
        ],
    ),
    Role.CASE_OFFICER: _grants(
        all_=[*_ALL_STAFF_READ, P.CONTACT_CREATE, P.CONTACT_UPDATE],
        own=[
            P.SEARCH_GLOBAL,
            P.CONTACT_PORTAL_INVITE,
            P.MATTER_READ,
            P.MATTER_UPDATE,
            P.TASK_READ,
            P.TASK_CREATE,
            P.TASK_UPDATE,
            P.ACTIVITY_CREATE,
            P.DOCUMENT_READ,
            P.DOCUMENT_UPLOAD,
            P.MESSAGE_READ,
            P.MESSAGE_SEND,
            P.AGREEMENT_READ,
        ],
    ),
    Role.INTAKE_CONSULTANT: _grants(
        all_=[
            *_ALL_STAFF_READ,
            P.CONTACT_CREATE,
            P.CONTACT_UPDATE,
            P.ORGANISATION_CREATE,
            P.ORGANISATION_UPDATE,
        ],
        own=[
            P.SEARCH_GLOBAL,
            P.LEAD_READ,
            P.LEAD_CREATE,
            P.LEAD_UPDATE,
            P.LEAD_CONVERT,
            P.TASK_READ,
            P.TASK_CREATE,
            P.TASK_UPDATE,
            P.ACTIVITY_CREATE,
        ],
    ),
    Role.ACCOUNTS: _grants(
        all_=[
            *_ALL_STAFF_READ,
            P.SEARCH_GLOBAL,
            P.MATTER_READ,
            P.ACTIVITY_CREATE,
            P.AGREEMENT_READ,
            P.INVOICE_READ,
            P.INVOICE_MANAGE,
            P.PAYMENT_RECORD,
            P.TRUST_READ,
            P.TRUST_MANAGE,
        ],
        own=[P.TASK_READ, P.TASK_CREATE, P.TASK_UPDATE],
        billing=[P.REPORT_VIEW, P.REPORT_EXPORT],
    ),
    Role.AUDITOR: _grants(
        all_=[
            *_ALL_STAFF_READ,
            P.SEARCH_GLOBAL,
            P.LEAD_READ,
            P.MATTER_READ,
            P.TASK_READ,
            P.DOCUMENT_READ,
            P.MESSAGE_READ,
            P.AGREEMENT_READ,
            P.INVOICE_READ,
            P.TRUST_READ,
            P.REPORT_VIEW,
            P.REPORT_EXPORT,
            P.AUDIT_READ,
        ],
    ),
    Role.CLIENT: _grants(
        all_=[P.PORTAL_ACCESS],
        own=[
            P.CONTACT_READ,
            P.MATTER_READ,
            P.DOCUMENT_READ,
            P.DOCUMENT_UPLOAD,
            P.MESSAGE_READ,
            P.MESSAGE_SEND,
            P.AGREEMENT_READ,
            P.AGREEMENT_SIGN,
            P.INVOICE_READ,
        ],
    ),
}


def parse_role(value: str) -> Role | None:
    try:
        return Role(value)
    except ValueError:
        return None


def scope_of(role: str, permission: Permission) -> Scope | None:
    """The scope a role holds for a permission, or None when denied."""
    parsed = parse_role(role)
    if parsed is None:
        return None
    return ROLE_PERMISSIONS[parsed].get(permission)


def can(role: str, permission: Permission) -> bool:
    return scope_of(role, permission) is not None


def permissions_for(role: str) -> dict[str, Scope]:
    parsed = parse_role(role)
    if parsed is None:
        return {}
    return {perm.value: scope for perm, scope in ROLE_PERMISSIONS[parsed].items()}


def is_staff(role: str) -> bool:
    parsed = parse_role(role)
    return parsed is not None and parsed in STAFF_ROLES

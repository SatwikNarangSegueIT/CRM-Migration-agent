"""The code matrix must equal the approved plan (docs/Implementation_Plan_v2.pdf, section 7).

The table below is transcribed from the plan independently of app/permissions/matrix.py.
Columns: ADMIN, PRACTICE_MANAGER, MIGRATION_AGENT, CASE_OFFICER, INTAKE_CONSULTANT, ACCOUNTS, AUDITOR, CLIENT.
Cells: A = all records, O = own records, B = billing reports only, . = denied.
"""

from __future__ import annotations

import pytest

from app.permissions.matrix import (
    ROLE_PERMISSIONS,
    Permission,
    Role,
    can,
    is_staff,
    permissions_for,
    scope_of,
)

ROLE_ORDER = [
    Role.ADMIN,
    Role.PRACTICE_MANAGER,
    Role.MIGRATION_AGENT,
    Role.CASE_OFFICER,
    Role.INTAKE_CONSULTANT,
    Role.ACCOUNTS,
    Role.AUDITOR,
    Role.CLIENT,
]

PLAN_TABLE = """
dashboard.view          A A A A A A A .
search.global           A A A O O A A .
lead.read               A A A . O . A .
lead.create             A A A . O . . .
lead.update             A A A . O . . .
lead.assign             A A A . . . . .
lead.convert            A A A . O . . .
lead.delete             A A . . . . . .
contact.read            A A A A A A A O
contact.create          A A A A A . . .
contact.update          A A A A A . . .
contact.delete          A A . . . . . .
contact.portal_invite   A A A O . . . .
organisation.read       A A A A A A A .
organisation.create     A A A . A . . .
organisation.update     A A A . A . . .
organisation.delete     A A . . . . . .
matter.read             A A A O . A A O
matter.create           A A A . . . . .
matter.update           A A A O . . . .
matter.assign           A A A . . . . .
matter.lodge            A A A . . . . .
matter.override         A . . . . . . .
matter.delete           A . . . . . . .
task.read               A A A O O O A .
task.create             A A A O O O . .
task.update             A A A O O O . .
task.delete             A A A . . . . .
activity.create         A A A O O A . .
document.read           A A A O . . A O
document.upload         A A A O . . . O
document.delete         A A A . . . . .
message.read            A A A O . . A O
message.send            A A A O . . . O
agreement.read          A A A O . A A O
agreement.manage        A A A . . . . .
agreement.sign          . . . . . . . O
invoice.read            A A A . . A A O
invoice.manage          A A A . . A . .
payment.record          A A . . . A . .
trust.read              A A A . . A A .
trust.manage            A A . . . A . .
report.view             A A A . . B A .
report.export           A A . . . B A .
visa.manage             A A . . . . . .
user.manage             A . . . . . . .
settings.manage         A . . . . . . .
audit.read              A A . . . . A .
portal.access           . . . . . . . A
"""

CELL = {"A": "all", "O": "own", "B": "billing", ".": None}


def _plan() -> dict[str, list[str | None]]:
    rows: dict[str, list[str | None]] = {}
    for line in PLAN_TABLE.strip().splitlines():
        name, *cells = line.split()
        assert len(cells) == len(ROLE_ORDER), line
        rows[name] = [CELL[c] for c in cells]
    return rows


def test_plan_lists_every_permission_exactly_once() -> None:
    assert set(_plan()) == {p.value for p in Permission}


@pytest.mark.parametrize("role", ROLE_ORDER, ids=lambda r: r.value)
def test_role_grants_match_plan(role: Role) -> None:
    column = ROLE_ORDER.index(role)
    expected = {perm: cells[column] for perm, cells in _plan().items() if cells[column] is not None}
    actual = {perm.value: scope for perm, scope in ROLE_PERMISSIONS[role].items()}
    assert actual == expected


def test_helpers() -> None:
    assert can("ADMIN", Permission.USER_MANAGE)
    assert not can("PRACTICE_MANAGER", Permission.USER_MANAGE)
    assert scope_of("CASE_OFFICER", Permission.MATTER_READ) == "own"
    assert scope_of("ACCOUNTS", Permission.REPORT_VIEW) == "billing"
    assert scope_of("NOT_A_ROLE", Permission.DASHBOARD_VIEW) is None
    assert not can("", Permission.DASHBOARD_VIEW)
    assert permissions_for("NOT_A_ROLE") == {}
    assert permissions_for("CLIENT")["portal.access"] == "all"
    assert is_staff("AUDITOR") and not is_staff("CLIENT") and not is_staff("bogus")


def test_only_admin_has_admin_only_permissions() -> None:
    for perm in (Permission.USER_MANAGE, Permission.SETTINGS_MANAGE, Permission.MATTER_DELETE):
        assert [r for r in Role if can(r.value, perm)] == [Role.ADMIN]


def test_auditor_is_read_only() -> None:
    write_words = (
        "create",
        "update",
        "delete",
        "manage",
        "assign",
        "convert",
        "lodge",
        "send",
        "upload",
        "record",
        "invite",
        "override",
        "sign",
    )
    granted = permissions_for(Role.AUDITOR.value)
    assert not [p for p in granted if any(w in p for w in write_words)]

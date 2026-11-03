"""The shipped profiles must equal the approved plan (docs/Implementation_Plan_v3.pdf, section 10).

The tables below are transcribed from the plan independently of app/security/seed_v1.py and are compared
with what the migration actually wrote to the database (via the access policy each user gets).
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.security.catalog import ObjectAccess, SystemPermission
from app.security.policy import load_policy
from tests.conftest import make_user

PROFILES = [
    "system_administrator",
    "sales_manager",
    "sales_representative",
    "service_agent",
    "marketing_user",
    "finance",
    "read_only",
    "customer_portal",
]

# Plan section 10 "Object permissions" (portal "own" scoping is applied by sharing, not the profile).
OBJECT_TABLE = """
account              | RCED VA MA | RCED | RCE  | RE   | R    | R         | R VA | R
contact              | RCED VA MA | RCED | RCE  | RCE  | RCE  | R         | R VA | RE
lead                 | RCED VA MA | RCED | RCE  | -    | RCED | -         | R VA | -
opportunity          | RCED VA MA | RCED | RCE  | R    | R    | R VA      | R VA | -
opportunity_product  | RCED VA MA | RCED | RCE  | R    | R    | R VA      | R VA | -
product              | RCED VA MA | R    | R    | R    | R    | RCED      | R VA | -
price_book           | RCED VA MA | R    | R    | R    | R    | RCED      | R VA | -
quote                | RCED VA MA | RCED | RCE  | -    | -    | R VA      | R VA | -
invoice              | RCED VA MA | R    | R    | R    | -    | RCE VA MA | R VA | R
payment              | RCED VA MA | R    | R    | R    | -    | RCE VA MA | R VA | R
tax_rate             | RCED VA MA | R    | R    | -    | -    | RCED      | R VA | -
case                 | RCED VA MA | R    | R    | RCE  | -    | R         | R VA | RC
campaign             | RCED VA MA | R    | R    | -    | RCED | -         | R VA | -
segment              | RCED VA MA | R    | R    | -    | RCED | -         | R VA | -
email_template       | RCED VA MA | R    | R    | -    | RCED | -         | R VA | -
email_send           | RCED VA MA | R    | -    | -    | RCE  | -         | R VA | -
consent              | RCED VA MA | R    | -    | -    | RCE  | -         | R VA | -
task                 | RCED VA MA | RCED | RCED | RCED | RCED | RCED      | R VA | -
event                | RCED VA MA | RCED | RCED | RCED | RCED | RCED      | R VA | -
note                 | RCED VA MA | RCED | RCED | RCED | RCED | RCED      | R VA | RC
file                 | RCED VA MA | RCED | RCED | RCED | RCED | RCED      | R VA | RC
report               | RCED VA MA | RCED | RC   | RC   | RCED | RCED      | R VA | -
dashboard            | RCED VA MA | RCED | RC   | RC   | RCED | RCED      | R VA | -
"""

# Plan section 10 "System permissions by profile" (X = granted).
SYSTEM_TABLE = """
manage_users             X . . . . . . .
customize_application    X . . . . . . .
manage_profiles_sharing  X . . . . . . .
manage_billing_settings  X . . . . X . .
manage_industry_packs    X . . . . . . .
view_setup               X . . . . . X .
view_audit_log           X . . . . . X .
import_data              X X . . X X . .
export_data              X X . . X X X .
send_mass_email          X . . . X . . .
manage_public_reports    X X . . X X . .
transfer_records         X X . . . . . .
manage_portal_users      X . . X . . . .
api_access               X . . . . . . .
"""


def _object_table() -> dict[str, list[ObjectAccess]]:
    rows: dict[str, list[ObjectAccess]] = {}
    for line in OBJECT_TABLE.strip().splitlines():
        name, *cells = (c.strip() for c in line.split("|"))
        assert len(cells) == len(PROFILES), line
        rows[name] = [ObjectAccess.parse(c) for c in cells]
    return rows


def _system_table() -> dict[str, list[bool]]:
    rows: dict[str, list[bool]] = {}
    for line in SYSTEM_TABLE.strip().splitlines():
        name, *cells = line.split()
        assert len(cells) == len(PROFILES), line
        rows[name] = [c == "X" for c in cells]
    return rows


def test_system_table_covers_every_permission() -> None:
    assert set(_system_table()) == {p.value for p in SystemPermission}


@pytest.mark.parametrize("profile", PROFILES)
def test_profile_matches_plan(profile: str, db: Session) -> None:
    column = PROFILES.index(profile)
    policy = load_policy(db, make_user(db, profile=profile))
    for obj, accesses in _object_table().items():
        assert policy.object(obj) == accesses[column], f"{profile} / {obj}"
    for perm, granted in _system_table().items():
        assert policy.has(SystemPermission(perm)) is granted[column], f"{profile} / {perm}"


def test_read_only_profile_changes_nothing(db: Session) -> None:
    policy = load_policy(db, make_user(db, profile="read_only"))
    for access in policy.objects.values():
        assert not (access.create or access.edit or access.delete or access.modify_all)


def test_object_access_notation_roundtrip() -> None:
    for code in ("RCED VA MA", "RCE", "R VA", "RC", "-"):
        assert ObjectAccess.parse(code).code() == code
    with pytest.raises(ValueError, match="Invalid object access code"):
        ObjectAccess.parse("RX")
    with pytest.raises(ValueError, match="require read access"):
        ObjectAccess(create=True).validate()

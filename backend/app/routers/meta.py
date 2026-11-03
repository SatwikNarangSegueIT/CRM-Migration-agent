"""/meta: reference data for the UI."""

from __future__ import annotations

from fastapi import APIRouter

from app.auth.deps import StaffAuth
from app.permissions.matrix import Role, permissions_for
from app.schemas.users import RoleInfo

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/roles", response_model=list[RoleInfo])
def roles(_: StaffAuth) -> list[RoleInfo]:
    """Roles with their permission grants (scope per permission)."""
    return [RoleInfo.for_role(role, dict(permissions_for(role))) for role in Role]

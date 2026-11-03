from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints, computed_field

from app.permissions.matrix import ROLE_LABELS, Role, is_staff
from app.schemas.common import ORMModel

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None
Phone = Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None
MaraNumber = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{7}$")] | None


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    name: str
    role: Role
    is_active: bool
    title: str | None
    phone: str | None
    mara_number: str | None
    mfa_enabled: bool
    last_login_at: datetime | None
    locked_until: datetime | None
    created_at: datetime
    updated_at: datetime
    has_password: bool

    @computed_field  # type: ignore[prop-decorator]
    @property
    def role_label(self) -> str:
        return ROLE_LABELS[self.role]


class UserSummary(ORMModel):
    id: uuid.UUID
    email: str
    name: str
    role: Role


class UserCreate(BaseModel):
    email: EmailStr
    name: Name
    role: Role
    title: OptionalText = None
    phone: Phone = None
    mara_number: MaraNumber = Field(default=None, description="7-digit MARA registration number")


class UserUpdate(BaseModel):
    """Partial update. `updated_at` must match the stored value (optimistic concurrency)."""

    updated_at: datetime
    name: Name | None = None
    role: Role | None = None
    title: OptionalText = None
    phone: Phone = None
    mara_number: MaraNumber = None
    is_active: bool | None = None


class RoleInfo(BaseModel):
    value: Role
    label: str
    is_staff: bool
    permissions: dict[str, str]

    @classmethod
    def for_role(cls, role: Role, permissions: dict[str, str]) -> RoleInfo:
        return cls(value=role, label=ROLE_LABELS[role], is_staff=is_staff(role), permissions=permissions)

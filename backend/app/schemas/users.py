from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, EmailStr, StringConstraints

from app.schemas.common import ORMModel


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
OptionalText = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None,
    BeforeValidator(_blank_to_none),
]
Phone = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None,
    BeforeValidator(_blank_to_none),
]
# A professional registration number (MARN, tax agent number, credit representative number, practising
# certificate). The profession's own format is checked by the user service.
MaraNumber = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9-]{3,20}$")] | None,
    BeforeValidator(_blank_to_none),
]


class ProfileRef(ORMModel):
    id: uuid.UUID
    name: str
    is_portal: bool


class RoleRef(ORMModel):
    id: uuid.UUID
    name: str


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    name: str
    profile: ProfileRef
    role: RoleRef | None
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


class UserCreate(BaseModel):
    email: EmailStr
    name: Name
    profile_id: uuid.UUID
    role_id: uuid.UUID | None = None
    title: OptionalText = None
    phone: Phone = None
    mara_number: MaraNumber = None


class UserUpdate(BaseModel):
    """Partial update. `updated_at` must match the stored value (optimistic concurrency).
    Send `role_id: null` to remove the user from the role hierarchy."""

    updated_at: datetime
    name: Name | None = None
    profile_id: uuid.UUID | None = None
    role_id: uuid.UUID | None = None
    title: OptionalText = None
    phone: Phone = None
    mara_number: MaraNumber = None
    is_active: bool | None = None

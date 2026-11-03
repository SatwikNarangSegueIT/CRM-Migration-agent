from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.schemas.common import ORMModel
from app.security.catalog import FieldAccess, ShareLevel, SharingAccess, SystemPermission

LabelText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
ObjectApiName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,76}(__c)?$")]
FieldApiName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,76}(__c)?$")]


# ---------------------------------------------------------------- catalog


class CatalogItem(BaseModel):
    value: str
    label: str


class StandardObjectOut(BaseModel):
    api_name: str
    label: str
    plural: str
    app: str
    default_sharing: SharingAccess


class CatalogOut(BaseModel):
    system_permissions: list[CatalogItem]
    objects: list[StandardObjectOut]
    sharing_access: list[str]
    field_access: list[str]


# ---------------------------------------------------------------- profiles


class ObjectPermissionIn(BaseModel):
    read: bool = False
    create: bool = False
    edit: bool = False
    delete: bool = False
    view_all: bool = False
    modify_all: bool = False


class ObjectPermissionOut(ObjectPermissionIn):
    object_api_name: str


class FieldPermissionOut(BaseModel):
    object_api_name: str
    field_api_name: str
    access: FieldAccess


class ProfileSummary(ORMModel):
    id: uuid.UUID
    key: str | None
    name: str
    description: str | None
    is_locked: bool
    is_portal: bool
    user_count: int = 0
    updated_at: datetime


class ProfileDetail(ProfileSummary):
    system_permissions: list[SystemPermission]
    object_permissions: list[ObjectPermissionOut]
    field_permissions: list[FieldPermissionOut]


class ProfileCreate(BaseModel):
    name: LabelText
    description: Description = None
    clone_from_id: uuid.UUID | None = Field(default=None, description="Copy permissions from this profile")
    is_portal: bool = False


class ProfileUpdate(BaseModel):
    name: LabelText | None = None
    description: Description = None


class SystemPermissionsIn(BaseModel):
    permissions: list[SystemPermission]


class ObjectPermissionsIn(BaseModel):
    """Upsert per object. Send all flags false to remove access to an object."""

    objects: dict[ObjectApiName, ObjectPermissionIn]


class FieldPermissionIn(BaseModel):
    object_api_name: ObjectApiName
    field_api_name: FieldApiName
    access: FieldAccess | None = Field(description="null removes the override (field default applies)")


class FieldPermissionsIn(BaseModel):
    fields: list[FieldPermissionIn] = Field(max_length=2000)


# ---------------------------------------------------------------- roles


class RoleOut(ORMModel):
    id: uuid.UUID
    key: str | None
    name: str
    description: str | None
    parent_id: uuid.UUID | None
    depth: int
    user_count: int


class RoleCreate(BaseModel):
    name: LabelText
    description: Description = None
    parent_id: uuid.UUID | None = None


class RoleUpdate(BaseModel):
    """Send `parent_id: null` to make the role a top-level role."""

    name: LabelText | None = None
    description: Description = None
    parent_id: uuid.UUID | None = None


# ---------------------------------------------------------------- sharing defaults


class SharingDefaultOut(BaseModel):
    object_api_name: str
    access: SharingAccess
    grant_access_using_hierarchy: bool


class SharingDefaultIn(BaseModel):
    access: SharingAccess
    grant_access_using_hierarchy: bool = True


# ---------------------------------------------------------------- groups & queues


class GroupRoleMember(BaseModel):
    role_id: uuid.UUID
    include_subordinates: bool = False


class GroupMembersIn(BaseModel):
    user_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5000)
    roles: list[GroupRoleMember] = Field(default_factory=list, max_length=500)


class GroupIn(BaseModel):
    name: LabelText
    description: Description = None


class GroupOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    user_ids: list[uuid.UUID]
    roles: list[GroupRoleMember]


class QueueIn(BaseModel):
    name: LabelText
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=254)] | None = None
    object_api_names: list[ObjectApiName] = Field(default_factory=list, max_length=50)


class QueueOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str | None
    object_api_names: list[str]
    user_ids: list[uuid.UUID]


class QueueMembersIn(BaseModel):
    user_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5000)


# ---------------------------------------------------------------- sharing rules

CriterionOperator = Literal[
    "eq", "ne", "lt", "lte", "gt", "gte", "in", "not_in", "contains", "starts_with", "is_null", "is_not_null"
]


class Criterion(BaseModel):
    field: FieldApiName
    op: CriterionOperator
    value: Any = None

    @field_validator("value")
    @classmethod
    def _value_shape(cls, v: Any) -> Any:
        if isinstance(v, dict):
            raise ValueError("value must be a scalar or a list")
        return v


class Criteria(BaseModel):
    logic: Literal["and", "or"] = "and"
    conditions: list[Criterion] = Field(min_length=1, max_length=25)


class SharingRuleIn(BaseModel):
    object_api_name: ObjectApiName
    name: LabelText
    description: Description = None
    rule_type: Literal["owner", "criteria"]
    source_type: Literal["role", "role_and_subordinates", "group", "queue"] | None = None
    source_id: uuid.UUID | None = None
    criteria: Criteria | None = None
    target_type: Literal["role", "role_and_subordinates", "group"]
    target_id: uuid.UUID
    access: ShareLevel


class SharingRuleOut(SharingRuleIn):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

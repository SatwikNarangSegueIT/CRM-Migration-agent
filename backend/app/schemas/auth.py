from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

Password = Annotated[str, Field(min_length=1, max_length=256)]
# Sign-in identifiers are matched, not validated: any stored address must be able to sign in.
LoginEmail = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=254)]
Token = Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=200)]


class LoginRequest(BaseModel):
    email: LoginEmail
    password: Password
    # Workspace address chosen in the picker when the e-mail belongs to several firms.
    workspace: Annotated[str, StringConstraints(max_length=41)] | None = None


class WorkspaceRef(BaseModel):
    slug: str
    name: str
    domain: str


class LoginResponse(BaseModel):
    state: Literal["authenticated", "mfa_required", "mfa_setup_required", "choose_workspace"]
    workspaces: list[WorkspaceRef] | None = None


class MfaCodeRequest(BaseModel):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=6, max_length=20)]


class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_svg_data_uri: str


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


class PasswordConfirmRequest(BaseModel):
    password: Password


class ChangePasswordRequest(BaseModel):
    current_password: Password
    new_password: Password


class ForgotPasswordRequest(BaseModel):
    email: LoginEmail


class ResetPasswordRequest(BaseModel):
    token: Token
    new_password: Password


class InvitationInspectRequest(BaseModel):
    token: Token


class InvitationInfo(BaseModel):
    email: str
    name: str


class InvitationAcceptRequest(BaseModel):
    token: Token
    password: Password


class NamedRef(BaseModel):
    id: uuid.UUID
    name: str


class MeUser(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    profile: NamedRef
    role: NamedRef | None
    is_staff: bool
    title: str | None
    mara_number: str | None
    mfa_enabled: bool


class ObjectAccessOut(BaseModel):
    read: bool
    create: bool
    edit: bool
    delete: bool
    view_all: bool
    modify_all: bool


class MeSession(BaseModel):
    mfa_verified: bool
    mfa_setup_required: bool
    expires_at: datetime
    recovery_codes_remaining: int | None


class MeResponse(BaseModel):
    user: MeUser
    session: MeSession
    # Both empty until the session is fully authenticated.
    system_permissions: list[str]
    object_permissions: dict[str, ObjectAccessOut]
    is_system_admin: bool

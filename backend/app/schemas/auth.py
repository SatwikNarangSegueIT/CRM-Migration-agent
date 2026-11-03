from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.permissions.matrix import Role

Password = Annotated[str, Field(min_length=1, max_length=256)]
# Sign-in identifiers are matched, not validated: any stored address must be able to sign in.
LoginEmail = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=254)]
Token = Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=200)]


class LoginRequest(BaseModel):
    email: LoginEmail
    password: Password


class LoginResponse(BaseModel):
    state: Literal["authenticated", "mfa_required", "mfa_setup_required"]


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


class MeUser(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: Role
    role_label: str
    is_staff: bool
    title: str | None
    mara_number: str | None
    mfa_enabled: bool


class MeSession(BaseModel):
    mfa_verified: bool
    mfa_setup_required: bool
    expires_at: datetime
    recovery_codes_remaining: int | None


class MeResponse(BaseModel):
    user: MeUser
    session: MeSession
    # Empty until the session is fully authenticated.
    permissions: dict[str, str]

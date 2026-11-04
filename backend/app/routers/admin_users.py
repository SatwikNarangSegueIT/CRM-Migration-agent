"""/admin/users: user administration (ADMIN only, permission user.manage)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.auth.deps import AuthContext, DbSession, require
from app.core.config import get_settings
from app.models import User
from app.schemas.common import Message, Page, PageParams
from app.schemas.users import UserCreate, UserOut, UserUpdate
from app.security.catalog import SystemPermission
from app.services import users as users_service
from app.services.audit import RequestMeta
from app.services.email import app_link, queue_email
from app.services.settings import get_setting
from app.tenancy import qualify_token

router = APIRouter(prefix="/admin/users", tags=["admin: users"])
Admin = Annotated[AuthContext, Depends(require(SystemPermission.MANAGE_USERS))]


def _send_invitation(db: Session, user: User, token: str, inviter: str) -> None:
    hours = get_settings().invitation_hours
    firm = str((get_setting(db, "branding") or {}).get("name") or "Meridian CRM")
    queue_email(
        user.email,
        f"You're invited to {firm}",
        f"Hello {user.name},\n\n{inviter} has created your account in {firm}'s workspace.\n"
        f"Set your password with this link (valid for {hours} hours, single use):\n\n"
        f"{app_link('/accept-invitation#token=' + token)}\n",
    )


@router.get("", response_model=Page[UserOut])
def list_users(
    db: DbSession,
    _: Admin,
    params: Annotated[PageParams, Depends()],
    q: Annotated[str | None, Query(max_length=100)] = None,
    profile_id: uuid.UUID | None = None,
    role_id: uuid.UUID | None = None,
    is_active: bool | None = None,
) -> Page[UserOut]:
    rows, total = users_service.list_users(
        db, params, q=q, profile_id=profile_id, role_id=role_id, is_active=is_active
    )
    return Page(
        items=[UserOut.model_validate(u) for u in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, request: Request, db: DbSession, auth: Admin) -> UserOut:
    user, token = users_service.create_user(db, auth, body, RequestMeta.from_request(request))
    _send_invitation(db, user, qualify_token(db, token), auth.user.name)
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: uuid.UUID, db: DbSession, _: Admin) -> UserOut:
    return UserOut.model_validate(users_service.get_user(db, user_id))


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID, body: UserUpdate, request: Request, db: DbSession, auth: Admin
) -> UserOut:
    user = users_service.update_user(db, auth, user_id, body, RequestMeta.from_request(request))
    return UserOut.model_validate(user)


@router.post("/{user_id}/resend-invitation", response_model=Message)
def resend_invitation(user_id: uuid.UUID, request: Request, db: DbSession, auth: Admin) -> Message:
    user, token = users_service.resend_invitation(db, auth, user_id, RequestMeta.from_request(request))
    _send_invitation(db, user, qualify_token(db, token), auth.user.name)
    return Message(message=f"Invitation sent to {user.email}.")


@router.post("/{user_id}/reset-mfa", response_model=UserOut)
def reset_mfa(user_id: uuid.UUID, request: Request, db: DbSession, auth: Admin) -> UserOut:
    return UserOut.model_validate(
        users_service.reset_mfa(db, auth, user_id, RequestMeta.from_request(request))
    )


@router.post("/{user_id}/unlock", response_model=UserOut)
def unlock(user_id: uuid.UUID, request: Request, db: DbSession, auth: Admin) -> UserOut:
    return UserOut.model_validate(users_service.unlock(db, auth, user_id, RequestMeta.from_request(request)))


@router.post("/{user_id}/revoke-sessions", response_model=Message)
def revoke_sessions(user_id: uuid.UUID, request: Request, db: DbSession, auth: Admin) -> Message:
    count = users_service.revoke_all_sessions(db, auth, user_id, RequestMeta.from_request(request))
    return Message(message=f"Signed out {count} session(s).")

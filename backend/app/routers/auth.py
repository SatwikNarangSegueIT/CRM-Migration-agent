"""/auth: sign-in, MFA, sessions, passwords and invitations."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.auth.deps import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    AnyAuth,
    Auth,
    AuthContext,
    DbSession,
    OptionalAuth,
    mfa_setup_required,
)
from app.core.config import get_settings
from app.core.rate_limit import check_rate_limit
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    InvitationAcceptRequest,
    InvitationInfo,
    InvitationInspectRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    MeSession,
    MeUser,
    MfaCodeRequest,
    MfaSetupResponse,
    NamedRef,
    ObjectAccessOut,
    PasswordConfirmRequest,
    RecoveryCodesResponse,
    ResetPasswordRequest,
)
from app.schemas.common import Message
from app.security.catalog import STANDARD_OBJECT_NAMES
from app.services import auth as auth_service
from app.services.audit import RequestMeta
from app.services.auth import IssuedSession
from app.services.email import app_link, queue_email

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_auth_cookies(response: Response, issued: IssuedSession) -> None:
    if not issued.token:
        return  # session unchanged
    settings = get_settings()
    max_age = settings.session_absolute_hours * 3600
    common = {"max_age": max_age, "secure": settings.secure_cookies, "samesite": "lax", "path": "/"}
    response.set_cookie(SESSION_COOKIE, issued.token, httponly=True, **common)  # type: ignore[arg-type]
    # Readable by the SPA, which echoes it in the X-CSRF-Token header.
    response.set_cookie(CSRF_COOKIE, issued.csrf_token, httponly=False, **common)  # type: ignore[arg-type]


def _clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", secure=settings.secure_cookies, samesite="lax")


def _me(db: DbSession, auth: AuthContext) -> MeResponse:
    user = auth.user
    verified = auth.session.mfa_verified
    policy = auth.policy if verified else None
    objects: dict[str, ObjectAccessOut] = {}
    if policy is not None:
        names = STANDARD_OBJECT_NAMES | policy.objects.keys()
        for name in sorted(names):
            access = policy.object(name)
            if access.read:
                objects[name] = ObjectAccessOut(
                    read=access.read,
                    create=access.create,
                    edit=access.edit,
                    delete=access.delete,
                    view_all=access.view_all,
                    modify_all=access.modify_all,
                )
    return MeResponse(
        user=MeUser(
            id=user.id,
            email=user.email,
            name=user.name,
            profile=NamedRef(id=user.profile.id, name=user.profile.name),
            role=NamedRef(id=user.role.id, name=user.role.name) if user.role else None,
            is_staff=not user.profile.is_portal,
            title=user.title,
            mara_number=user.mara_number,
            mfa_enabled=user.mfa_enabled,
        ),
        session=MeSession(
            mfa_verified=verified,
            mfa_setup_required=not verified and mfa_setup_required(user),
            expires_at=auth.session.expires_at,
            recovery_codes_remaining=(
                auth_service.remaining_recovery_codes(db, user.id) if user.mfa_enabled and verified else None
            ),
        ),
        system_permissions=policy.system_permissions() if policy else [],
        object_permissions=objects,
        is_system_admin=policy.is_system_admin if policy else False,
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, response: Response, db: DbSession) -> LoginResponse:
    check_rate_limit("login-ip", _client_ip(request), limit=30, window_seconds=300)
    check_rate_limit("login-email", str(body.email), limit=10, window_seconds=300)
    issued, state = auth_service.login(db, str(body.email), body.password, RequestMeta.from_request(request))
    _set_auth_cookies(response, issued)
    return LoginResponse(state=state.value)


@router.post("/logout", response_model=Message)
def logout(request: Request, response: Response, db: DbSession, auth: OptionalAuth) -> Message:
    if auth is not None:
        auth_service.logout(db, auth, RequestMeta.from_request(request))
    _clear_auth_cookies(response)
    return Message(message="Signed out.")


@router.get("/me", response_model=MeResponse)
def me(db: DbSession, auth: AnyAuth) -> MeResponse:
    return _me(db, auth)


@router.post("/mfa/verify", response_model=MeResponse)
def mfa_verify(
    body: MfaCodeRequest, request: Request, response: Response, db: DbSession, auth: AnyAuth
) -> MeResponse:
    check_rate_limit("mfa", str(auth.user.id), limit=10, window_seconds=300)
    issued = auth_service.verify_mfa(db, auth, body.code, RequestMeta.from_request(request))
    _set_auth_cookies(response, issued)
    return _me(db, AuthContext(user=auth.user, session=issued.session, db=db))


@router.post("/mfa/setup", response_model=MfaSetupResponse)
def mfa_setup(db: DbSession, auth: AnyAuth) -> MfaSetupResponse:
    setup = auth_service.begin_mfa_setup(db, auth)
    return MfaSetupResponse(
        secret=setup.secret, otpauth_uri=setup.otpauth_uri, qr_svg_data_uri=setup.qr_svg_data_uri
    )


@router.post("/mfa/enable", response_model=RecoveryCodesResponse)
def mfa_enable(
    body: MfaCodeRequest, request: Request, response: Response, db: DbSession, auth: AnyAuth
) -> RecoveryCodesResponse:
    check_rate_limit("mfa", str(auth.user.id), limit=10, window_seconds=300)
    issued, codes = auth_service.complete_mfa_setup(db, auth, body.code, RequestMeta.from_request(request))
    _set_auth_cookies(response, issued)
    return RecoveryCodesResponse(recovery_codes=codes)


@router.post("/mfa/recovery-codes", response_model=RecoveryCodesResponse)
def regenerate_recovery_codes(
    body: PasswordConfirmRequest, request: Request, db: DbSession, auth: Auth
) -> RecoveryCodesResponse:
    codes = auth_service.regenerate_recovery_codes(db, auth, body.password, RequestMeta.from_request(request))
    return RecoveryCodesResponse(recovery_codes=codes)


@router.post("/password/change", response_model=Message)
def change_password(body: ChangePasswordRequest, request: Request, db: DbSession, auth: Auth) -> Message:
    auth_service.change_password(
        db, auth, body.current_password, body.new_password, RequestMeta.from_request(request)
    )
    return Message(message="Password changed. Other sessions have been signed out.")


@router.post("/password/forgot", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def forgot_password(body: ForgotPasswordRequest, request: Request, db: DbSession) -> Message:
    check_rate_limit("forgot-ip", _client_ip(request), limit=10, window_seconds=900)
    check_rate_limit("forgot-email", str(body.email), limit=3, window_seconds=900)
    result = auth_service.request_password_reset(db, str(body.email), RequestMeta.from_request(request))
    if result is not None:
        user, token = result
        minutes = get_settings().password_reset_minutes
        queue_email(
            user.email,
            "Reset your MigrateCRM password",
            f"Hello {user.name},\n\nUse this link to choose a new password. It expires in {minutes} minutes "
            f"and can be used once:\n\n{app_link('/reset-password#token=' + token)}\n\n"
            "If you did not ask for this, ignore this e-mail; your password stays the same.\n",
        )
    # Same answer whether or not the account exists.
    return Message(message="If an account exists for that e-mail, a reset link has been sent.")


@router.post("/password/reset", response_model=Message)
def reset_password(body: ResetPasswordRequest, request: Request, db: DbSession) -> Message:
    check_rate_limit("token-ip", _client_ip(request), limit=20, window_seconds=900)
    auth_service.reset_password(db, body.token, body.new_password, RequestMeta.from_request(request))
    return Message(message="Password updated. You can now sign in.")


@router.post("/invitation/inspect", response_model=InvitationInfo)
def inspect_invitation(body: InvitationInspectRequest, request: Request, db: DbSession) -> InvitationInfo:
    check_rate_limit("token-ip", _client_ip(request), limit=20, window_seconds=900)
    user = auth_service.inspect_invitation(db, body.token)
    return InvitationInfo(email=user.email, name=user.name)


@router.post("/invitation/accept", response_model=Message)
def accept_invitation(body: InvitationAcceptRequest, request: Request, db: DbSession) -> Message:
    check_rate_limit("token-ip", _client_ip(request), limit=20, window_seconds=900)
    auth_service.accept_invitation(db, body.token, body.password, RequestMeta.from_request(request))
    return Message(message="Your account is ready. Sign in to continue.")

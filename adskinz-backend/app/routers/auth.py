"""Authentication endpoints.

Paths are fixed by the frontend contract and must not be renamed:
    POST /auth/register
    POST /auth/login
    POST /admin/auth/request-code
    POST /admin/auth/verify-code
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.deps import (
    ClientIPHashDep,
    CurrentUserDep,
    SessionDep,
    login_rate_limit,
)
from app.core.enums import Role
from app.schemas.auth import (
    AdminRequestCodeResponse,
    AdminSessionResponse,
    AdminVerifyCodeRequest,
    ChangePasswordRequest,
    EmailVerifyRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    SettingsUpdateRequest,
    TokenRefreshResponse,
    TokenResponse,
    UserProfile,
)
from app.schemas.common import MessageResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
admin_auth_router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(login_rate_limit)],
    summary="Create an advertiser or publisher account",
)
async def register(
    payload: RegisterRequest,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> RegisterResponse:
    return await auth_service.register(
        session,
        email=payload.email,
        password=payload.password,
        role=Role(payload.role),
        display_name=payload.display_name,
        telegram_username=payload.telegram_username,
        referral_code=payload.referral_code,
        ip_hash=ip_hash,
    )


@router.post(
    "/verify-email",
    response_model=TokenResponse,
    dependencies=[Depends(login_rate_limit)],
    summary="Verify a 6-digit email code and start the session",
)
async def verify_email(
    payload: EmailVerifyRequest,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> TokenResponse:
    return await auth_service.verify_email(
        session,
        email=payload.email,
        code=payload.code,
        ip_hash=ip_hash,
    )


@router.post(
    "/resend-verification",
    response_model=RegisterResponse,
    dependencies=[Depends(login_rate_limit)],
    summary="Resend the email verification code",
)
async def resend_verification(
    payload: ResendVerificationRequest,
    session: SessionDep,
) -> RegisterResponse:
    return await auth_service.resend_verification(
        session,
        email=payload.email,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(login_rate_limit)],
    summary="Log in as an advertiser or publisher",
)
async def login(
    payload: LoginRequest,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> TokenResponse:
    return await auth_service.login(
        session,
        email=payload.email,
        password=payload.password,
        role=Role(payload.role),
        ip_hash=ip_hash,
    )


@router.get("/me", response_model=UserProfile, summary="Current account profile")
async def me(user: CurrentUserDep) -> UserProfile:
    from app.models.accounts import Advertiser

    entity = user.entity
    balance = (
        entity.balance_usd
        if isinstance(entity, Advertiser)
        else entity.available_balance_usd
    )
    return UserProfile(
        id=entity.id,
        email=entity.email,
        role=user.role,
        display_name=entity.display_name,
        telegram_username=entity.telegram_username,
        country=entity.country,
        balance=balance,
        created_at=entity.created_at,
    )


@router.patch("/me", response_model=UserProfile, summary="Update account settings")
async def update_me(
    payload: SettingsUpdateRequest,
    user: CurrentUserDep,
    session: SessionDep,
) -> UserProfile:
    entity = user.entity
    if payload.display_name is not None:
        entity.display_name = payload.display_name
    if payload.telegram_username is not None:
        handle = payload.telegram_username.strip()
        entity.telegram_username = handle if handle.startswith("@") else f"@{handle}"
    if payload.country is not None:
        entity.country = payload.country
    await session.commit()
    await session.refresh(entity)
    return await me(user)


@router.post(
    "/password",
    response_model=MessageResponse,
    summary="Change the account password",
)
async def change_password(
    payload: ChangePasswordRequest,
    user: CurrentUserDep,
    session: SessionDep,
) -> MessageResponse:
    await auth_service.change_password(
        session,
        account=user.entity,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return MessageResponse(message="Password updated.")


@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    summary="Exchange a refresh token for a new access token",
)
async def refresh(
    payload: RefreshTokenRequest,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> TokenRefreshResponse:
    result = await auth_service.refresh_access_token(
        session,
        refresh_token=payload.refresh_token,
        ip_hash=ip_hash,
    )
    return TokenRefreshResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
        role=result.role,
    )


# --------------------------------------------------------------------------- #
# Admin: emailed code + fixed console password
# --------------------------------------------------------------------------- #
@admin_auth_router.post(
    "/request-code",
    response_model=AdminRequestCodeResponse,
    dependencies=[Depends(login_rate_limit)],
    summary="Admin step 1 — email a fresh 8-digit sign-in code",
)
async def admin_request_code(session: SessionDep) -> AdminRequestCodeResponse:
    """Sends the code to the fixed console email (never entered by the
    user). No request body — just click "Ask code"."""
    return await auth_service.admin_request_login_code(session)


@admin_auth_router.post(
    "/verify-code",
    response_model=AdminSessionResponse,
    dependencies=[Depends(login_rate_limit)],
    summary="Admin step 2 — emailed code + console password, returns the session token",
)
async def admin_verify_code(
    payload: AdminVerifyCodeRequest,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> AdminSessionResponse:
    return await auth_service.admin_verify_login_code(
        session,
        code=payload.code,
        password=payload.password,
        ip_hash=ip_hash,
    )

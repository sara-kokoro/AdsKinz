"""Authentication endpoints.

Paths are fixed by the frontend contract and must not be renamed:
    POST /auth/register
    POST /auth/login
    POST /admin/auth/login
    POST /admin/auth/totp
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
    AdminLoginRequest,
    AdminPartialTokenResponse,
    AdminSessionResponse,
    AdminTotpRequest,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    SettingsUpdateRequest,
    TokenResponse,
    UserProfile,
)
from app.schemas.common import MessageResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
admin_auth_router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(login_rate_limit)],
    summary="Create an advertiser or publisher account",
)
async def register(
    payload: RegisterRequest,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> TokenResponse:
    return await auth_service.register(
        session,
        email=payload.email,
        password=payload.password,
        role=Role(payload.role),
        display_name=payload.display_name,
        telegram_username=payload.telegram_username,
        ip_hash=ip_hash,
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


# --------------------------------------------------------------------------- #
# Admin: two-step login
# --------------------------------------------------------------------------- #
@admin_auth_router.post(
    "/login",
    response_model=AdminPartialTokenResponse,
    dependencies=[Depends(login_rate_limit)],
    summary="Admin step 1 — password, returns a partial token",
)
async def admin_login(
    payload: AdminLoginRequest,
    session: SessionDep,
) -> AdminPartialTokenResponse:
    """Validates the password only.

    The returned partial token grants no access; it is only accepted by
    ``POST /admin/auth/totp``.
    """
    return await auth_service.admin_login(
        session, email=payload.email, password=payload.password
    )


@admin_auth_router.post(
    "/totp",
    response_model=AdminSessionResponse,
    dependencies=[Depends(login_rate_limit)],
    summary="Admin step 2 — TOTP code, returns the real session token",
)
async def admin_totp(
    payload: AdminTotpRequest,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> AdminSessionResponse:
    return await auth_service.admin_verify_totp(
        session,
        partial_token=payload.partial_token,
        code=payload.code,
        ip_hash=ip_hash,
    )

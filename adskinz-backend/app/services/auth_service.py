"""Account registration, login and the two-step admin authentication."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Role
from app.core.errors import (
    AccountBlockedError,
    AuthenticationError,
    ConflictError,
    TokenError,
)
from app.core.security import (
    create_access_token,
    create_admin_partial_token,
    create_admin_session_token,
    decode_token,
    hash_password,
    needs_rehash,
    token_expiry_seconds,
    verify_password,
)
from app.models.accounts import AdminUser, Advertiser, Publisher
from app.schemas.auth import (
    AdminPartialTokenResponse,
    AdminSessionResponse,
    TokenResponse,
    UserProfile,
)

logger = logging.getLogger(__name__)

Account = Advertiser | Publisher

# Same wording for "unknown email" and "wrong password" so the endpoint cannot
# be used to enumerate registered accounts.
_INVALID_CREDENTIALS = "Invalid email or password."


def _profile(account: Account, role: Role) -> UserProfile:
    balance = (
        account.balance_usd
        if isinstance(account, Advertiser)
        else account.available_balance_usd
    )
    return UserProfile(
        id=account.id,
        email=account.email,
        role=role,
        display_name=account.display_name,
        telegram_username=account.telegram_username,
        country=account.country,
        balance=balance,
        created_at=account.created_at,
    )


def _token_response(account: Account, role: Role) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(account.id, role),
        expires_in=token_expiry_seconds("access"),
        role=role,
        user=_profile(account, role),
    )


async def _email_taken(session: AsyncSession, email: str) -> bool:
    for model in (Advertiser, Publisher, AdminUser):
        found = (
            await session.execute(select(model.id).where(model.email == email))
        ).scalar_one_or_none()
        if found is not None:
            return True
    return False


async def register(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    role: Role,
    display_name: str | None = None,
    telegram_username: str | None = None,
    ip_hash: str | None = None,
) -> TokenResponse:
    """Create an advertiser or publisher account and return a session token.

    Admin accounts are never created through this path — they are provisioned
    manually with ``scripts/create_admin.py``.
    """
    email = email.strip().lower()
    if role not in (Role.ADVERTISER, Role.PUBLISHER):
        raise ConflictError("Only advertiser and publisher accounts can self-register.")

    if await _email_taken(session, email):
        raise ConflictError("An account already exists with this email address.")

    model = Advertiser if role == Role.ADVERTISER else Publisher
    account = model(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name or email.split("@")[0],
        telegram_username=telegram_username,
        last_login_at=datetime.now(UTC),
        last_login_ip_hash=ip_hash,
    )
    session.add(account)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("An account already exists with this email address.") from exc

    await session.commit()
    await session.refresh(account)
    logger.info("account.registered role=%s id=%s", role, account.id)
    return _token_response(account, role)


async def login(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    ip_hash: str | None = None,
) -> TokenResponse:
    """Authenticate an advertiser or publisher by email and password."""
    email = email.strip().lower()

    account: Account | None = None
    role = Role.ADVERTISER

    advertiser = (
        await session.execute(select(Advertiser).where(Advertiser.email == email))
    ).scalar_one_or_none()
    if advertiser is not None:
        account, role = advertiser, Role.ADVERTISER
    else:
        publisher = (
            await session.execute(select(Publisher).where(Publisher.email == email))
        ).scalar_one_or_none()
        if publisher is not None:
            account, role = publisher, Role.PUBLISHER

    if account is None:
        # Burn a comparable amount of CPU so timing does not leak existence.
        verify_password(password, hash_password("timing-equaliser"))
        raise AuthenticationError(_INVALID_CREDENTIALS)

    if not verify_password(password, account.password_hash):
        raise AuthenticationError(_INVALID_CREDENTIALS)

    if account.is_blocked:
        raise AccountBlockedError(
            account.blocked_reason
            or "This account has been suspended. Contact support for assistance."
        )

    if needs_rehash(account.password_hash):
        account.password_hash = hash_password(password)

    account.last_login_at = datetime.now(UTC)
    account.last_login_ip_hash = ip_hash
    await session.commit()
    await session.refresh(account)

    return _token_response(account, role)


# --------------------------------------------------------------------------- #
# Admin: two-step login
# --------------------------------------------------------------------------- #
async def admin_login(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> AdminPartialTokenResponse:
    """Step 1. Validates the password and returns a short-lived partial token.

    The partial token grants no access at all: it is only accepted by
    ``admin_verify_totp``.
    """
    email = email.strip().lower()
    admin = (
        await session.execute(select(AdminUser).where(AdminUser.email == email))
    ).scalar_one_or_none()

    if admin is None:
        verify_password(password, hash_password("timing-equaliser"))
        raise AuthenticationError(_INVALID_CREDENTIALS)

    if not verify_password(password, admin.password_hash):
        raise AuthenticationError(_INVALID_CREDENTIALS)

    if not admin.is_active:
        raise AccountBlockedError("This admin account is disabled.")

    if not admin.totp_secret:
        raise AuthenticationError(
            "This admin account has no authenticator configured. Run the "
            "create_admin script to provision one."
        )

    return AdminPartialTokenResponse(
        partial_token=create_admin_partial_token(admin.id),
        expires_in=token_expiry_seconds("admin_partial"),
    )


async def admin_verify_totp(
    session: AsyncSession,
    *,
    partial_token: str,
    code: str,
    ip_hash: str | None = None,
) -> AdminSessionResponse:
    """Step 2. Validates the 6-digit code and issues the real admin session."""
    payload = decode_token(partial_token, expected_kind="admin_partial")
    subject = payload.get("sub")
    if not subject:
        raise TokenError("Malformed partial token.")

    admin = (
        await session.execute(select(AdminUser).where(AdminUser.id == subject))
    ).scalar_one_or_none()
    if admin is None or not admin.is_active:
        raise AuthenticationError("Admin account is not active.")

    # pyotp counters advance every 30 seconds; refusing a counter we have
    # already accepted blocks replay of a code captured on the wire.
    import pyotp  # imported lazily so tests can stub it

    totp = pyotp.TOTP(admin.totp_secret)
    if not totp.verify(code, valid_window=1):
        raise AuthenticationError("Invalid authentication code.")

    counter = int(datetime.now(UTC).timestamp()) // 30
    if admin.last_totp_counter is not None and counter <= admin.last_totp_counter:
        raise AuthenticationError("This authentication code has already been used.")

    admin.last_totp_counter = counter
    admin.totp_confirmed = True
    admin.last_login_at = datetime.now(UTC)
    admin.last_login_ip_hash = ip_hash
    await session.commit()

    logger.info("admin.login id=%s", admin.id)
    return AdminSessionResponse(
        access_token=create_admin_session_token(admin.id),
        expires_in=token_expiry_seconds("admin_session"),
        admin_id=admin.id,
        email=admin.email,
    )


async def change_password(
    session: AsyncSession,
    *,
    account: Account,
    current_password: str,
    new_password: str,
) -> None:
    if not verify_password(current_password, account.password_hash):
        raise AuthenticationError("Current password is incorrect.")
    account.password_hash = hash_password(new_password)
    await session.commit()

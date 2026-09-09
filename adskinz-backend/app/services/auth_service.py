"""Account registration, login and the admin console sign-in."""

from __future__ import annotations

import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.enums import Role
from app.core.errors import (
    AccountBlockedError,
    AuthenticationError,
    ConflictError,
    EmailNotVerifiedError,
    TokenError,
)
from app.core.security import (
    create_access_token,
    create_admin_session_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    token_expiry_seconds,
    verify_password,
)
from app.models.accounts import AdminUser, Advertiser, Publisher, RefreshToken
from app.schemas.auth import (
    AdminRequestCodeResponse,
    AdminSessionResponse,
    RegisterResponse,
    TokenResponse,
    UserProfile,
)
from app.services import email_service

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


async def _create_refresh_token_row(
    session: AsyncSession,
    account: Account | AdminUser,
    role: Role,
) -> str:
    token = create_refresh_token(account.id, role)
    payload = decode_token(token, expected_kind="refresh")
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        raise RuntimeError("Refresh token missing jti or exp.")
    account_type = "admin" if isinstance(account, AdminUser) else role.value
    record = RefreshToken(
        account_type=account_type,
        account_id=account.id,
        jti=jti,
        expires_at=datetime.fromtimestamp(exp, tz=UTC),
    )
    session.add(record)
    await session.flush()
    return token


def _token_response(account: Account, role: Role, refresh_token: str) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(account.id, role),
        refresh_token=refresh_token,
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


def _generate_verification_code() -> str:
    """Cryptographically random 6-digit code."""
    import secrets

    return f"{secrets.randbelow(1_000_000):06d}"


async def _set_verification_code(session: AsyncSession, account: Account) -> str:
    code = _generate_verification_code()
    account.email_verification_code = code
    account.email_verification_expires_at = datetime.now(UTC) + timedelta(hours=3)
    return code


async def register(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    role: Role,
    display_name: str | None = None,
    telegram_username: str | None = None,
    referral_code: str | None = None,
    ip_hash: str | None = None,
) -> RegisterResponse:
    """Create an unverified advertiser or publisher account.

    The account cannot log in until ``verify_email`` confirms the 6-digit code
    sent to the email address. Admin accounts are never created here.
    """
    from app.config import settings
    from app.services import referral_service
    from app.services.email_service import send_verification_code

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
        last_login_ip_hash=ip_hash,
    )
    if referral_code:
        referrer = await referral_service.find_by_referral_code(session, model, referral_code)
        if referrer is not None:
            account.referred_by_id = referrer.id
    session.add(account)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("An account already exists with this email address.") from exc

    await referral_service.ensure_referral_code(session, account)

    code = await _set_verification_code(session, account)
    await session.commit()
    await session.refresh(account)

    sent = await send_verification_code(email, code=code)
    logger.info("account.registered role=%s id=%s email=%s sent=%s", role, account.id, email, sent)
    return RegisterResponse(
        email=email,
        verification_code=code if not settings.is_production else None,
    )


async def verify_email(
    session: AsyncSession,
    *,
    email: str,
    code: str,
    ip_hash: str | None = None,
) -> TokenResponse:
    """Confirm a 6-digit verification code and issue the first session."""
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
        raise AuthenticationError("Invalid email or verification code.")

    if account.email_verified:
        raise ConflictError("This email is already verified. Please sign in.")

    if (
        account.email_verification_code is None
        or account.email_verification_code != code
        or account.email_verification_expires_at is None
        or account.email_verification_expires_at < datetime.now(UTC)
    ):
        raise AuthenticationError("Invalid or expired verification code.")

    account.email_verified = True
    account.email_verification_code = None
    account.email_verification_expires_at = None
    account.last_login_at = datetime.now(UTC)
    account.last_login_ip_hash = ip_hash
    refresh_token = await _create_refresh_token_row(session, account, role)
    await session.commit()
    await session.refresh(account)

    logger.info("account.verified role=%s id=%s", role, account.id)
    return _token_response(account, role, refresh_token)


async def resend_verification(
    session: AsyncSession,
    *,
    email: str,
) -> RegisterResponse:
    """Regenerate and resend the verification code for an unverified account."""
    from app.config import settings
    from app.services.email_service import send_verification_code

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
        # Don't reveal whether the email exists.
        return RegisterResponse(email=email)

    if account.email_verified:
        raise ConflictError("This email is already verified. Please sign in.")

    code = await _set_verification_code(session, account)
    await session.commit()
    await session.refresh(account)

    await send_verification_code(email, code=code)
    logger.info("account.verification_resent role=%s id=%s", role, account.id)
    return RegisterResponse(
        email=email,
        verification_code=code if not settings.is_production else None,
    )


async def login(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    role: Role,
    ip_hash: str | None = None,
) -> TokenResponse:
    """Authenticate an advertiser or publisher by email and password.

    ``role`` is the workspace the user is trying to enter. If the account exists
    but belongs to the other role, we return a dedicated error so the frontend
    can explain that the credential is for the other portal.
    """
    email = email.strip().lower()

    account: Account | None = None
    actual_role: Role | None = None

    advertiser = (
        await session.execute(select(Advertiser).where(Advertiser.email == email))
    ).scalar_one_or_none()
    if advertiser is not None:
        account, actual_role = advertiser, Role.ADVERTISER
    else:
        publisher = (
            await session.execute(select(Publisher).where(Publisher.email == email))
        ).scalar_one_or_none()
        if publisher is not None:
            account, actual_role = publisher, Role.PUBLISHER

    if account is None:
        # Burn a comparable amount of CPU so timing does not leak existence.
        verify_password(password, hash_password("timing-equaliser"))
        raise AuthenticationError(_INVALID_CREDENTIALS)

    if not verify_password(password, account.password_hash):
        raise AuthenticationError(_INVALID_CREDENTIALS)

    if actual_role != role:
        portal = "advertiser" if actual_role == Role.ADVERTISER else "publisher"
        other = "https://adskinz.io" if actual_role == Role.ADVERTISER else "https://partner.adskinz.io"
        raise AuthenticationError(
            f"These credentials belong to the {portal} portal. "
            f"Please sign in at {other}."
        )

    if not account.email_verified:
        raise EmailNotVerifiedError()

    if account.is_blocked:
        raise AccountBlockedError(
            account.blocked_reason
            or "This account has been suspended. Contact support for assistance."
        )

    if needs_rehash(account.password_hash):
        account.password_hash = hash_password(password)

    account.last_login_at = datetime.now(UTC)
    account.last_login_ip_hash = ip_hash
    refresh_token = await _create_refresh_token_row(session, account, role)
    await session.commit()
    await session.refresh(account)

    return _token_response(account, role, refresh_token)


# --------------------------------------------------------------------------- #
# Admin: emailed code + fixed console password
# --------------------------------------------------------------------------- #
async def _get_or_create_console_admin(session: AsyncSession) -> AdminUser:
    """The console has exactly one operator account, identified by
    ``settings.ADMIN_LOGIN_EMAIL``. It is auto-provisioned on first use so
    there is nothing to run manually before the console works."""
    email = settings.ADMIN_LOGIN_EMAIL.strip().lower()
    admin = (
        await session.execute(select(AdminUser).where(AdminUser.email == email))
    ).scalar_one_or_none()
    if admin is None:
        admin = AdminUser(
            email=email,
            # Unused by this login flow (the real check is the fixed
            # console password in settings), stored only because the
            # column is required.
            password_hash=hash_password(secrets.token_urlsafe(32)),
            is_active=True,
        )
        session.add(admin)
        await session.flush()
    return admin


async def admin_request_login_code(session: AsyncSession) -> AdminRequestCodeResponse:
    """Step 1 — "Ask code". Emails a fresh one-time 8-digit code and
    discards any code requested earlier."""
    admin = await _get_or_create_console_admin(session)
    if not admin.is_active:
        raise AccountBlockedError("This admin account is disabled.")

    code = f"{secrets.randbelow(10**8):08d}"
    admin.login_code_hash = hash_password(code)
    admin.login_code_expires_at = datetime.now(UTC) + timedelta(
        seconds=settings.ADMIN_LOGIN_CODE_TTL_SECONDS
    )
    await session.commit()

    await email_service.send_admin_login_code(settings.ADMIN_LOGIN_EMAIL, code=code)
    logger.info("admin.login_code_requested")

    return AdminRequestCodeResponse(expiresIn=settings.ADMIN_LOGIN_CODE_TTL_SECONDS)


async def admin_verify_login_code(
    session: AsyncSession,
    *,
    code: str,
    password: str,
    ip_hash: str | None = None,
) -> AdminSessionResponse:
    """Step 2 — the emailed code plus the fixed console password.

    Both must match; either alone grants nothing. The code is single-use
    and expires (``ADMIN_LOGIN_CODE_TTL_SECONDS``), so a leaked email does
    not help without the password, and a leaked password does not help
    without a fresh code.
    """
    admin = await _get_or_create_console_admin(session)
    if not admin.is_active:
        raise AccountBlockedError("This admin account is disabled.")

    # Constant-time comparison: the console password never varies in
    # length in practice, but this avoids leaking timing information.
    password_ok = hmac.compare_digest(password, settings.ADMIN_LOGIN_PASSWORD)

    code_ok = False
    if admin.login_code_hash and admin.login_code_expires_at:
        if datetime.now(UTC) <= admin.login_code_expires_at:
            code_ok = verify_password(code, admin.login_code_hash)

    if not (password_ok and code_ok):
        raise AuthenticationError("Invalid or expired code/password. Ask for a new code and try again.")

    # One-time use: burn the code the moment it succeeds.
    admin.login_code_hash = None
    admin.login_code_expires_at = None
    admin.last_login_at = datetime.now(UTC)
    admin.last_login_ip_hash = ip_hash

    logger.info("admin.login id=%s", admin.id)
    refresh_token = await _create_refresh_token_row(session, admin, Role.ADMIN)
    await session.commit()
    await session.refresh(admin)
    return AdminSessionResponse(
        access_token=create_admin_session_token(admin.id),
        refresh_token=refresh_token,
        expires_in=token_expiry_seconds("admin_session"),
        admin_id=admin.id,
        email=admin.email,
    )


async def refresh_access_token(
    session: AsyncSession,
    *,
    refresh_token: str,
    ip_hash: str | None = None,
) -> TokenResponse:
    """Exchange a valid refresh token for a new access/refresh token pair."""
    from uuid import UUID

    from sqlalchemy import delete, select

    payload = decode_token(refresh_token, expected_kind="refresh")
    subject = payload.get("sub")
    role_raw = payload.get("role")
    jti = payload.get("jti")
    if not subject or not role_raw or not jti:
        raise TokenError("Malformed refresh token.")

    role = Role(role_raw)
    account_id = UUID(str(subject))

    # Reject unknown or already-used refresh tokens.
    token_row = (
        await session.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    ).scalar_one_or_none()
    if token_row is None:
        raise AuthenticationError("Invalid refresh token.")
    if token_row.expires_at < datetime.now(UTC):
        await session.execute(delete(RefreshToken).where(RefreshToken.jti == jti))
        await session.commit()
        raise AuthenticationError("Refresh token expired.")

    # Load the matching account and enforce block status.
    account: Account | AdminUser | None = None
    if role == Role.ADMIN:
        account = await session.get(AdminUser, account_id)
        if account is None or not account.is_active:
            raise AuthenticationError("Account is not active.")
    else:
        model: type[Advertiser] | type[Publisher] = (
            Advertiser if role == Role.ADVERTISER else Publisher
        )
        account = await session.get(model, account_id)
        if account is None:
            raise AuthenticationError("Account no longer exists.")
        if getattr(account, "is_blocked", False):
            raise AccountBlockedError(
                account.blocked_reason
                or "This account has been suspended. Contact support for assistance."
            )

    # Single-use: delete the consumed token and issue a fresh pair.
    await session.execute(delete(RefreshToken).where(RefreshToken.jti == jti))
    new_refresh_token = await _create_refresh_token_row(session, account, role)
    account.last_login_at = datetime.now(UTC)
    account.last_login_ip_hash = ip_hash
    await session.commit()
    await session.refresh(account)

    if role == Role.ADMIN:
        # Admins use a separate response shape, but the frontend expects the
        # same TokenResponse contract on /auth/refresh. We map admin here too.
        return TokenResponse(
            access_token=create_admin_session_token(account.id),
            refresh_token=new_refresh_token,
            expires_in=token_expiry_seconds("admin_session"),
            role=role,
            user=_profile(account, role) if isinstance(account, (Advertiser, Publisher)) else None,
        )
    return _token_response(account, role, new_refresh_token)


async def change_password(
    session: AsyncSession,
    *,
    account: Account,
    current_password: str,
    new_password: str,
) -> None:
    from sqlalchemy import delete

    if not verify_password(current_password, account.password_hash):
        raise AuthenticationError("Current password is incorrect.")
    account.password_hash = hash_password(new_password)
    role = Role.ADVERTISER if isinstance(account, Advertiser) else Role.PUBLISHER
    await session.execute(
        delete(RefreshToken).where(
            RefreshToken.account_id == account.id,
            RefreshToken.account_type == role.value,
        )
    )
    await session.commit()

"""FastAPI dependencies: authentication, current actor resolution, rate limits."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.enums import Role
from app.core.errors import (
    AccountBlockedError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)
from app.core.security import decode_token, hash_ip
from app.database import get_session
from app.models.accounts import AdminUser, Advertiser, Publisher
from app.redis_client import rate_limit_hit

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@dataclass(slots=True)
class CurrentUser:
    """The authenticated advertiser or publisher behind a request."""

    id: uuid.UUID
    email: str
    role: Role
    entity: Advertiser | Publisher

    @property
    def is_advertiser(self) -> bool:
        return self.role == Role.ADVERTISER

    @property
    def is_publisher(self) -> bool:
        return self.role == Role.PUBLISHER

    @property
    def advertiser(self) -> Advertiser:
        if not isinstance(self.entity, Advertiser):
            raise PermissionDeniedError("This endpoint is reserved for advertiser accounts.")
        return self.entity

    @property
    def publisher(self) -> Publisher:
        if not isinstance(self.entity, Publisher):
            raise PermissionDeniedError("This endpoint is reserved for publisher accounts.")
        return self.entity


@dataclass(slots=True)
class CurrentAdmin:
    id: uuid.UUID
    email: str
    entity: AdminUser
    role: Literal[Role.ADMIN] = Role.ADMIN


# --------------------------------------------------------------------------- #
# Client metadata
# --------------------------------------------------------------------------- #
def client_ip(request: Request) -> str:
    """Best-effort client IP, honouring the proxy headers Koyeb sets."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return request.client.host if request.client else "0.0.0.0"


def client_ip_hash(request: Request) -> str:
    """Salted HMAC of the client IP. The raw IP is never persisted."""
    return hash_ip(client_ip(request))


ClientIPDep = Annotated[str, Depends(client_ip)]
ClientIPHashDep = Annotated[str, Depends(client_ip_hash)]


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise AuthenticationError("Authentication required.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationError("Invalid authorization header.")
    return token.strip()


# --------------------------------------------------------------------------- #
# Actor resolution
# --------------------------------------------------------------------------- #
async def get_current_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    """Resolve the advertiser or publisher carrying a valid access token."""
    token = _extract_bearer(authorization)
    payload = decode_token(token, expected_kind="access")

    role_raw = payload.get("role")
    subject = payload.get("sub")
    if not role_raw or not subject:
        raise AuthenticationError("Malformed token payload.")

    try:
        user_id = uuid.UUID(str(subject))
        role = Role(role_raw)
    except ValueError as exc:
        raise AuthenticationError("Malformed token payload.") from exc

    if role == Role.ADVERTISER:
        model: type[Advertiser] | type[Publisher] = Advertiser
    elif role == Role.PUBLISHER:
        model = Publisher
    else:
        raise PermissionDeniedError("Admin tokens cannot be used on this endpoint.")

    entity = await session.get(model, user_id)
    if entity is None:
        raise AuthenticationError("Account no longer exists.")
    if getattr(entity, "is_blocked", False):
        raise AccountBlockedError(
            "This account has been suspended. Contact support for more information."
        )

    return CurrentUser(id=entity.id, email=entity.email, role=role, entity=entity)


async def get_current_advertiser(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> Advertiser:
    return user.advertiser


async def get_current_publisher(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> Publisher:
    return user.publisher


async def get_current_admin(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentAdmin:
    """Only full admin session tokens are accepted.

    A partial token issued by ``/admin/auth/login`` is deliberately rejected
    here: it is only valid on ``/admin/auth/totp``.
    """
    token = _extract_bearer(authorization)
    payload = decode_token(token, expected_kind="admin_session")

    subject = payload.get("sub")
    try:
        admin_id = uuid.UUID(str(subject))
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Malformed admin token.") from exc

    admin = await session.get(AdminUser, admin_id)
    if admin is None or not admin.is_active:
        raise AuthenticationError("Admin account is not active.")

    return CurrentAdmin(id=admin.id, email=admin.email, entity=admin)


async def get_optional_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser | None:
    """Same as ``get_current_user`` but tolerates anonymous requests."""
    if not authorization:
        return None
    try:
        return await get_current_user(session, authorization)
    except (AuthenticationError, PermissionDeniedError, AccountBlockedError):
        return None


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
CurrentAdvertiserDep = Annotated[Advertiser, Depends(get_current_advertiser)]
CurrentPublisherDep = Annotated[Publisher, Depends(get_current_publisher)]
CurrentAdminDep = Annotated[CurrentAdmin, Depends(get_current_admin)]
OptionalUserDep = Annotated[CurrentUser | None, Depends(get_optional_user)]


# --------------------------------------------------------------------------- #
# Rate limiting
# --------------------------------------------------------------------------- #
class RateLimiter:
    """Redis-backed fixed-window limiter.

    Degrades to a no-op when Redis is unavailable so an outage of the cache
    layer never takes the API down.
    """

    def __init__(self, bucket: str, limit: int, window_seconds: int) -> None:
        self.bucket = bucket
        self.limit = limit
        self.window_seconds = window_seconds

    async def __call__(self, request: Request) -> None:
        identifier = hash_ip(client_ip(request))
        allowed, remaining = await rate_limit_hit(
            self.bucket, identifier or "unknown", self.limit, self.window_seconds
        )
        request.state.rate_limit_remaining = remaining
        if not allowed:
            raise RateLimitError(
                "Too many requests. Please slow down and try again shortly.",
                context={"retry_after": self.window_seconds},
            )


login_rate_limit = RateLimiter(
    "login", settings.RATE_LIMIT_LOGIN, settings.RATE_LIMIT_LOGIN_WINDOW
)
serve_rate_limit = RateLimiter(
    "serve", settings.RATE_LIMIT_SERVE, settings.RATE_LIMIT_SERVE_WINDOW
)
generate_rate_limit = RateLimiter(
    "generate", settings.RATE_LIMIT_GENERATE, settings.RATE_LIMIT_GENERATE_WINDOW
)
verify_deposit_rate_limit = RateLimiter("verify_deposit", 1, 20)


# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class Pagination:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def pagination(page: int = 1, page_size: int = 50) -> Pagination:
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    return Pagination(page=page, page_size=page_size)


PaginationDep = Annotated[Pagination, Depends(pagination)]


async def lookup_account_by_email(
    session: AsyncSession, email: str
) -> tuple[Advertiser | Publisher, Role] | None:
    """Find an account by email across both actor tables."""
    normalised = email.strip().lower()
    advertiser = (
        await session.execute(select(Advertiser).where(Advertiser.email == normalised))
    ).scalar_one_or_none()
    if advertiser is not None:
        return advertiser, Role.ADVERTISER
    publisher = (
        await session.execute(select(Publisher).where(Publisher.email == normalised))
    ).scalar_one_or_none()
    if publisher is not None:
        return publisher, Role.PUBLISHER
    return None

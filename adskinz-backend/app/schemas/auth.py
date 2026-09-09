"""Auth request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import EmailStr, Field, computed_field, field_validator

from app.core.enums import Role
from app.schemas.common import APIModel, RequestModel

PASSWORD_MIN = 8
PASSWORD_MAX = 72  # bcrypt hard limit, in bytes


def _validate_password(value: str) -> str:
    if len(value) < PASSWORD_MIN:
        raise ValueError(f"Password must be at least {PASSWORD_MIN} characters long.")
    if len(value.encode("utf-8")) > PASSWORD_MAX:
        raise ValueError("Password must not exceed 72 bytes.")
    if value.isdigit() or value.isalpha():
        raise ValueError("Password must mix letters and at least one digit or symbol.")
    return value


class RegisterRequest(RequestModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN)
    password_confirm: str = Field(min_length=PASSWORD_MIN)
    role: Literal["advertiser", "publisher"] = "advertiser"
    display_name: str | None = Field(default=None, max_length=120)
    telegram_username: str | None = Field(default=None, max_length=64)
    referral_code: str | None = Field(default=None, max_length=16, alias="ref")

    _check_password = field_validator("password")(_validate_password)

    @field_validator("password_confirm")
    @classmethod
    def _passwords_match(cls, value: str, info) -> str:
        password = info.data.get("password")
        if password is not None and value != password:
            raise ValueError("Passwords do not match.")
        return value

    @field_validator("telegram_username")
    @classmethod
    def _normalise_handle(cls, value: str | None) -> str | None:
        if not value:
            return None
        return value if value.startswith("@") else f"@{value}"


class RegisterResponse(APIModel):
    """Registration creates an unverified account; the client must confirm the
    email with the 6-digit code before a session is issued.

    ``verification_code`` is only populated in non-production environments when
    outgoing email is disabled, so front-end smoke tests can complete the flow
    without a real mailbox.
    """

    message: str = "Check your email for a 6-digit verification code."
    email: str
    requires_verification: bool = True
    verification_code: str | None = None


class LoginRequest(RequestModel):
    email: EmailStr
    password: str = Field(min_length=1)
    # Required so the backend can reject advertiser credentials on the publisher
    # portal (and vice-versa) with a clear error instead of silently succeeding.
    role: Literal["advertiser", "publisher"]


class EmailVerifyRequest(RequestModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendVerificationRequest(RequestModel):
    email: EmailStr


class AdminRequestCodeResponse(APIModel):
    """Returned by POST /admin/auth/request-code."""

    sent: Literal[True] = True
    expiresIn: int


class AdminVerifyCodeRequest(RequestModel):
    """Step 2 — the 8-digit emailed code plus the fixed console password."""

    code: str = Field(min_length=8, max_length=8, pattern=r"^\d{8}$")
    password: str = Field(min_length=1, max_length=200)


class UserProfile(APIModel):
    id: uuid.UUID
    email: EmailStr
    role: Role
    display_name: str | None = None
    telegram_username: str | None = None
    country: str | None = None
    balance: Decimal = Decimal("0.00")
    created_at: datetime | None = None


class TokenResponse(APIModel):
    """Session token for an advertiser or publisher.

    The value is exposed under three keys so the frontend can read whichever
    convention it uses: ``access_token`` (OAuth style), ``accessToken`` and the
    short ``token``. They always hold the same string.
    """

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    role: Role
    user: UserProfile | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def token(self) -> str:
        return self.access_token

    @computed_field  # type: ignore[prop-decorator]
    @property
    def accessToken(self) -> str:  # noqa: N802 - camelCase is the frontend contract
        return self.access_token

    @computed_field  # type: ignore[prop-decorator]
    @property
    def expiresIn(self) -> int:  # noqa: N802
        return self.expires_in


class RefreshTokenRequest(RequestModel):
    refresh_token: str = Field(min_length=10)


class TokenRefreshResponse(APIModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    role: Role


class AdminSessionResponse(APIModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    role: Literal["admin"] = "admin"
    admin_id: uuid.UUID
    email: EmailStr

    @computed_field  # type: ignore[prop-decorator]
    @property
    def token(self) -> str:
        return self.access_token

    @computed_field  # type: ignore[prop-decorator]
    @property
    def accessToken(self) -> str:  # noqa: N802
        return self.access_token

    @computed_field  # type: ignore[prop-decorator]
    @property
    def adminId(self) -> str:  # noqa: N802
        return str(self.admin_id)


class ChangePasswordRequest(RequestModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=PASSWORD_MIN)

    _check_password = field_validator("new_password")(_validate_password)


class SettingsUpdateRequest(RequestModel):
    display_name: str | None = Field(default=None, max_length=120)
    telegram_username: str | None = Field(default=None, max_length=64)
    country: str | None = Field(default=None, max_length=64)

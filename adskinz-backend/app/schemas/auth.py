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
    role: Literal["advertiser", "publisher"] = "advertiser"
    display_name: str | None = Field(default=None, max_length=120)
    telegram_username: str | None = Field(default=None, max_length=64)

    _check_password = field_validator("password")(_validate_password)

    @field_validator("telegram_username")
    @classmethod
    def _normalise_handle(cls, value: str | None) -> str | None:
        if not value:
            return None
        return value if value.startswith("@") else f"@{value}"


class LoginRequest(RequestModel):
    email: EmailStr
    password: str = Field(min_length=1)
    # Optional hint; the server still resolves the account by email.
    role: Literal["advertiser", "publisher"] | None = None


class AdminLoginRequest(RequestModel):
    email: EmailStr
    password: str = Field(min_length=1)


class AdminTotpRequest(RequestModel):
    """Second factor. ``partial_token`` comes from /admin/auth/login."""

    partial_token: str = Field(min_length=10)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


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


class AdminPartialTokenResponse(APIModel):
    """Returned by /admin/auth/login. Not a usable session token.

    It only unlocks ``POST /admin/auth/totp``; every protected admin route
    rejects it.
    """

    partial_token: str
    expires_in: int
    totp_required: Literal[True] = True
    message: str = "Enter the 6-digit code from your authenticator app."

    @computed_field  # type: ignore[prop-decorator]
    @property
    def partialToken(self) -> str:  # noqa: N802
        return self.partial_token

    @computed_field  # type: ignore[prop-decorator]
    @property
    def totpRequired(self) -> bool:  # noqa: N802
        return self.totp_required


class AdminSessionResponse(APIModel):
    access_token: str
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

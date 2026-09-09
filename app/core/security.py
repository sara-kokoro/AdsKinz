"""Password hashing, JWT issuance/verification, TOTP, and hashing helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt
import pyotp

from app.config import settings
from app.core.enums import Role
from app.core.errors import TokenError

TokenKind = Literal["access", "refresh", "admin_partial", "admin_session"]

# bcrypt is used directly rather than through passlib: recent bcrypt releases
# dropped the internal attributes passlib probes at import time, which makes the
# passlib backend raise on perfectly valid passwords.
BCRYPT_ROUNDS = 12
BCRYPT_MAX_BYTES = 72


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(plain: str) -> str:
    """Hash a password with bcrypt.

    bcrypt silently truncates anything past 72 bytes, which would let a user
    log in with a shorter prefix of their own password. Reject instead.
    """
    encoded = plain.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_BYTES:
        raise ValueError("Password must not exceed 72 bytes.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        encoded = plain.encode("utf-8")
        if len(encoded) > BCRYPT_MAX_BYTES:
            return False
        return bcrypt.checkpw(encoded, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def needs_rehash(hashed: str) -> bool:
    """True when a stored hash uses fewer rounds than the current policy."""
    try:
        rounds = int(hashed.split("$")[2])
    except (IndexError, ValueError):
        return True
    return rounds < BCRYPT_ROUNDS


def generate_password(length: int = 20) -> str:
    return secrets.token_urlsafe(length)[:length]


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def _encode(payload: dict[str, Any], expires_delta: timedelta, kind: TokenKind) -> str:
    now = datetime.now(UTC)
    body = {
        **payload,
        "kind": kind,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": uuid.uuid4().hex,
        "iss": "adskinz-api",
    }
    return jwt.encode(body, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: uuid.UUID | str, role: Role) -> str:
    """Session token for advertisers and publishers."""
    return _encode(
        {"sub": str(subject), "role": role.value},
        timedelta(days=settings.ACCESS_TOKEN_TTL_DAYS),
        "access",
    )


def create_refresh_token(subject: uuid.UUID | str, role: Role) -> str:
    """Long-lived refresh token used to obtain a new access token."""
    return _encode(
        {"sub": str(subject), "role": role.value},
        timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
        "refresh",
    )


def create_admin_partial_token(subject: uuid.UUID | str) -> str:
    """Short-lived token issued after password check, before TOTP validation."""
    return _encode(
        {"sub": str(subject), "role": Role.ADMIN.value},
        timedelta(seconds=settings.ADMIN_PARTIAL_TOKEN_TTL_SECONDS),
        "admin_partial",
    )


def create_admin_session_token(subject: uuid.UUID | str) -> str:
    """Full admin session token, issued only after a valid TOTP code."""
    return _encode(
        {"sub": str(subject), "role": Role.ADMIN.value},
        timedelta(hours=settings.ADMIN_SESSION_TTL_HOURS),
        "admin_session",
    )


def decode_token(token: str, expected_kind: TokenKind | None = None) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer="adskinz-api",
            options={"require": ["exp", "sub", "kind"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Session expired. Please sign in again.", code="token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError() from exc

    if expected_kind and payload.get("kind") != expected_kind:
        raise TokenError("Token type not accepted on this endpoint.", code="wrong_token_kind")
    return payload


def token_expiry_seconds(kind: TokenKind) -> int:
    return {
        "access": settings.ACCESS_TOKEN_TTL_DAYS * 86_400,
        "refresh": settings.REFRESH_TOKEN_TTL_DAYS * 86_400,
        "admin_partial": settings.ADMIN_PARTIAL_TOKEN_TTL_SECONDS,
        "admin_session": settings.ADMIN_SESSION_TTL_HOURS * 3_600,
    }[kind]


# --------------------------------------------------------------------------- #
# TOTP
# --------------------------------------------------------------------------- #
def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=settings.TOTP_ISSUER)


def verify_totp(secret: str, code: str, valid_window: int = 1) -> bool:
    """Validate a 6-digit code, tolerating one 30s step of clock drift."""
    cleaned = (code or "").strip().replace(" ", "")
    if not cleaned.isdigit() or len(cleaned) != 6:
        return False
    try:
        return pyotp.TOTP(secret).verify(cleaned, valid_window=valid_window)
    except Exception:  # pragma: no cover - malformed secret
        return False


# --------------------------------------------------------------------------- #
# Hashing helpers
# --------------------------------------------------------------------------- #
def hash_ip(ip: str | None) -> str | None:
    """One-way, salted hash. Raw IP addresses are never persisted."""
    if not ip:
        return None
    return hmac.new(
        settings.IP_HASH_SALT.encode("utf-8"),
        ip.strip().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def short_hash(value: str, length: int = 10) -> str:
    """Deterministic short token, used for TON deposit memos."""
    digest = hashlib.sha256(f"{settings.IP_HASH_SALT}:{value}".encode()).hexdigest()
    return digest[:length]


def generate_kinz_key(live: bool = False) -> str:
    prefix = "kinz_live" if live else "kinz_test"
    return f"{prefix}_{secrets.token_hex(4)}"


# Alphanumeric, mixed-case, no separators — pairs with settings.tracking_link()
# to produce short links like https://tr.adskinz.me/+HlziUi818Jzka.
_TRACKING_ID_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
TRACKING_ID_LENGTH = 13


def generate_tracking_id() -> str:
    return "".join(secrets.choice(_TRACKING_ID_ALPHABET) for _ in range(TRACKING_ID_LENGTH))


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

"""Typed application errors and their HTTP translation.

Error payloads returned to the frontend always follow the same shape::

    {"detail": {"code": "insufficient_balance", "message": "..."}}

Messages are in English on purpose: the frontend owns display translation via
i18next and keys off the machine-readable ``code``.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Base class for every business error raised by services and routers."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    message: str = "The request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.context = context or {}
        super().__init__(self.message)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.context:
            payload["context"] = self.context
        return payload


# --------------------------------------------------------------------------- #
# 400 family
# --------------------------------------------------------------------------- #
class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_error"
    message = "One or more fields are invalid."


class BusinessRuleError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "business_rule_violation"
    message = "This action breaks a platform rule."


class InsufficientBalanceError(AppError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    code = "insufficient_balance"
    message = "Your balance is not sufficient for this operation."


class WithdrawalCooldownError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "withdrawal_cooldown"
    message = "Withdrawals unlock after the cooldown period following your first channel approval."


# --------------------------------------------------------------------------- #
# 401 / 403
# --------------------------------------------------------------------------- #
class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "authentication_failed"
    message = "Invalid credentials."


class EmailNotVerifiedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "email_not_verified"
    message = (
        "Please verify your email before signing in. "
        "Enter the 6-digit code sent to your inbox, or request a new one."
    )


class TokenError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "invalid_token"
    message = "The session token is missing, malformed or expired."


class TotpRequiredError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "totp_required"
    message = "A valid TOTP code is required to complete admin sign-in."


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"
    message = "You are not allowed to perform this action."


class AccountBlockedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "account_blocked"
    message = "This account has been blocked. Contact support."


# --------------------------------------------------------------------------- #
# 404 / 409 / 429
# --------------------------------------------------------------------------- #
class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "The requested resource does not exist."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "The resource already exists or is in a conflicting state."


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "Too many requests. Please slow down."


# --------------------------------------------------------------------------- #
# 5xx / upstream
# --------------------------------------------------------------------------- #
class UpstreamError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "upstream_error"
    message = "An upstream provider failed to respond."


class ConfigurationError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "not_configured"
    message = "This feature is not configured on the server."


class NoInventoryError(AppError):
    """No eligible campaign for a serve request — a normal, expected outcome."""

    status_code = status.HTTP_204_NO_CONTENT
    code = "no_inventory"
    message = "No eligible campaign for this placement right now."


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.to_payload()})


async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        payload = detail
    else:
        payload = {"code": _code_for_status(exc.status_code), "message": str(detail)}
    return JSONResponse(status_code=exc.status_code, content={"detail": payload})


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [
        {
            "field": ".".join(str(p) for p in err.get("loc", []) if p != "body"),
            "message": err.get("msg", "Invalid value."),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": {
                "code": "validation_error",
                "message": "One or more fields are invalid.",
                "fields": fields,
            }
        },
    )


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    import logging

    logging.getLogger(__name__).exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": {
                "code": "internal_error",
                "message": "An unexpected error occurred.",
            }
        },
    )


def _code_for_status(code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
        502: "upstream_error",
        503: "service_unavailable",
    }.get(code, "error")


def register_exception_handlers(app) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

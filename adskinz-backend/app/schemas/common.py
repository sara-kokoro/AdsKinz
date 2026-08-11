"""Shared Pydantic building blocks."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_serializer

T = TypeVar("T")


class APIModel(BaseModel):
    """Base for every response model.

    ``from_attributes`` lets routers build responses straight from ORM objects,
    and Decimals are serialised as JSON numbers so the frontend's
    ``fmtMoney``/``num`` helpers receive real numbers, not strings.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        ser_json_timedelta="float",
        str_strip_whitespace=True,
        protected_namespaces=(),
    )

    @field_serializer("*", when_used="json", check_fields=False)
    def _serialize_decimal(self, value):  # noqa: ANN001, ANN202
        if isinstance(value, Decimal):
            return float(value)
        return value


class RequestModel(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        populate_by_name=True,
        protected_namespaces=(),
    )


class Page(APIModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 50
    has_more: bool = False

    @classmethod
    def build(cls, items: list[T], total: int, page: int, page_size: int) -> "Page[T]":
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=page * page_size < total,
        )


class MessageResponse(APIModel):
    message: str
    code: str | None = None


class OkResponse(APIModel):
    ok: bool = True


class HealthResponse(APIModel):
    status: str = "ok"
    version: str
    environment: str
    database: bool
    redis: bool
    scheduler: bool
    time: datetime


class ErrorDetail(APIModel):
    code: str
    message: str
    context: dict | None = None


class SparklinePoint(APIModel):
    date: str
    value: float


class MoneyAmount(APIModel):
    amount: Decimal = Field(ge=0)
    currency: str = "USDT"

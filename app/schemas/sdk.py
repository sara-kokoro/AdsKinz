"""Schemas for the public Kinz-ID SDK endpoint (/sdk/serve)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel

ServeFormat = Literal["interstitial", "popInterstitial"]


class ServeCreative(APIModel):
    """The payload the Mini App SDK renders."""

    text: str
    button_label: str = Field(alias="buttonLabel")
    tracking_url: str = Field(alias="trackingUrl")
    image_url: str | None = Field(default=None, alias="imageUrl")


class ServeResponse(APIModel):
    """A filled ad slot.

    ``ad_id`` is the campaign id, ``tracking_id`` identifies this specific
    impression so a later click can be attributed to it.
    """

    filled: Literal[True] = True
    ad_id: str = Field(alias="adId")
    tracking_id: str = Field(alias="trackingId")
    format: ServeFormat
    lang: str
    creative: ServeCreative
    ttl: int = 30


class NoFillResponse(APIModel):
    """No eligible campaign. The SDK must silently skip the slot."""

    filled: Literal[False] = False
    reason: str = "no_inventory"
    retry_after: int = Field(default=60, alias="retryAfter")


class ServeErrorResponse(APIModel):
    filled: Literal[False] = False
    reason: str
    message: str

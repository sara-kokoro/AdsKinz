"""Public Kinz-ID SDK endpoint used by Mini Apps.

    GET /sdk/serve?key=<kinz-id>&lang=<code>&format=interstitial|popInterstitial

This route is unauthenticated by design: the Kinz-ID key identifies the Mini
App. It is rate limited per key and never returns an error the SDK cannot
recover from — an empty slot is a normal, successful answer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Query, Response
from sqlalchemy import select

from app.config import settings
from app.core.deps import ClientIPHashDep, SessionDep
from app.core.enums import AD_LANGUAGES, MiniAppStatus
from app.core.security import generate_tracking_id
from app.models.placements import MiniApp
from app.models.tracking import Impression, TrackingLink
from app.redis_client import rate_limit_hit
from app.schemas.sdk import NoFillResponse, ServeCreative, ServeResponse
from app.services import ad_selection_service, billing_service

router = APIRouter(prefix="/sdk", tags=["sdk"])

_MINIAPP_PLACEMENT = "miniapp"


@router.get(
    "/serve",
    response_model=ServeResponse | NoFillResponse,
    summary="Serve one ad to a Mini App slot",
)
async def serve(
    response: Response,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
    key: str = Query(..., min_length=8, max_length=64, description="Kinz-ID key"),
    lang: str = Query("en", max_length=8),
    format: Literal["interstitial", "popInterstitial"] = Query("interstitial"),
) -> ServeResponse | NoFillResponse:
    """Return a creative, or ``filled: false`` when no campaign is eligible.

    The impression is billed at serve time: for Mini Apps there is no later
    view signal to reconcile against, unlike channel posts.
    """
    response.headers["Cache-Control"] = "no-store"

    lang = (lang or "en").lower()
    if lang not in AD_LANGUAGES:
        lang = "en"

    allowed, _ = await rate_limit_hit(
        "sdk_serve", key, settings.SDK_SERVE_RATE_LIMIT, settings.SDK_SERVE_RATE_WINDOW
    )
    if not allowed:
        return NoFillResponse(reason="rate_limited", retryAfter=30)

    mini_app = (
        await session.execute(select(MiniApp).where(MiniApp.kinz_key == key))
    ).scalar_one_or_none()

    if mini_app is None:
        return NoFillResponse(reason="unknown_key", retryAfter=600)
    if mini_app.status != MiniAppStatus.ACTIVE.value:
        return NoFillResponse(reason="placement_inactive", retryAfter=600)
    if format not in (mini_app.formats_enabled or []):
        return NoFillResponse(reason="format_disabled", retryAfter=600)

    campaign = await ad_selection_service.select_for_mini_app(
        session, lang=lang, serve_format=format
    )
    if campaign is None:
        return NoFillResponse(reason="no_inventory", retryAfter=60)

    text, button_label, lang_used = await ad_selection_service.resolve_creative(
        session, campaign, lang
    )

    tracking_id = generate_tracking_id()
    session.add(
        TrackingLink(
            tracking_id=tracking_id,
            campaign_id=campaign.id,
            placement_type=_MINIAPP_PLACEMENT,
            placement_id=mini_app.id,
            destination_url=campaign.destination_url,
            expires_at=datetime.now(UTC) + timedelta(days=settings.TRACKING_LINK_TTL_DAYS),
        )
    )

    cost = billing_service.impression_cost(campaign.cpm_bid, 1)
    result = await billing_service.charge_campaign(
        session,
        campaign=campaign,
        amount=cost,
        units=1,
        event_type="impression",
        placement_type=_MINIAPP_PLACEMENT,
        placement_id=mini_app.id,
    )

    session.add(
        Impression(
            campaign_id=campaign.id,
            tracking_id=tracking_id,
            placement_type=_MINIAPP_PLACEMENT,
            placement_id=mini_app.id,
            format=format,
            lang_served=lang_used,
            billed=result.charged,
            billed_amount_usd=result.amount,
            ip_hash=ip_hash,
        )
    )

    if not mini_app.integration_detected:
        # First real serve: the publisher has wired the SDK correctly.
        mini_app.integration_detected = True
        mini_app.first_serve_at = datetime.now(UTC)

    await session.commit()

    return ServeResponse(
        adId=str(campaign.id),
        trackingId=str(tracking_id),
        format=format,
        lang=lang_used,
        creative=ServeCreative(
            text=text,
            buttonLabel=button_label,
            trackingUrl=settings.tracking_link(tracking_id),
            imageUrl=campaign.image_url,
        ),
        ttl=settings.SDK_CREATIVE_TTL,
    )


@router.get("/kinz.js", summary="Kinz-ID browser SDK")
async def kinz_js(response: Response) -> Response:
    """Tiny loader served from the API so Mini Apps only embed one script tag."""
    script = _SDK_SOURCE.replace("__API_BASE__", settings.API_BASE_URL)
    return Response(
        content=script,
        media_type="application/javascript; charset=utf-8",
        headers={"Cache-Control": "public, max-age=300"},
    )


_SDK_SOURCE = """/* AdsKinz Mini App SDK */
(function () {
  var API = "__API_BASE__";
  var script = document.currentScript;
  var key = script && script.getAttribute("data-kinz-id");

  function lang() {
    try {
      var tg = window.Telegram && window.Telegram.WebApp;
      var code = (tg && tg.initDataUnsafe && tg.initDataUnsafe.user
        && tg.initDataUnsafe.user.language_code) || navigator.language || "en";
      return String(code).slice(0, 2).toLowerCase();
    } catch (e) { return "en"; }
  }

  function request(format) {
    var url = API + "/sdk/serve?key=" + encodeURIComponent(key)
      + "&lang=" + encodeURIComponent(lang())
      + "&format=" + encodeURIComponent(format || "interstitial");
    return fetch(url, { credentials: "omit" }).then(function (r) { return r.json(); });
  }

  function render(ad) {
    if (!ad || !ad.filled) return null;
    var overlay = document.createElement("div");
    overlay.setAttribute("data-adskinz", ad.trackingId);
    overlay.style.cssText = "position:fixed;inset:0;z-index:2147483000;display:flex;"
      + "align-items:center;justify-content:center;background:rgba(8,10,20,.82);"
      + "backdrop-filter:blur(6px);font-family:system-ui,-apple-system,sans-serif";

    var card = document.createElement("div");
    card.style.cssText = "max-width:340px;width:88%;background:#12141f;color:#f4f5fb;"
      + "border-radius:18px;padding:22px;box-shadow:0 24px 60px rgba(0,0,0,.5);text-align:center";

    if (ad.creative.imageUrl) {
      var img = document.createElement("img");
      img.src = ad.creative.imageUrl;
      img.style.cssText = "width:100%;border-radius:12px;margin-bottom:14px;display:block";
      card.appendChild(img);
    }

    var text = document.createElement("p");
    text.textContent = ad.creative.text;
    text.style.cssText = "margin:0 0 18px;font-size:15px;line-height:1.5";
    card.appendChild(text);

    var cta = document.createElement("a");
    cta.href = ad.creative.trackingUrl;
    cta.target = "_blank";
    cta.rel = "noopener";
    cta.textContent = ad.creative.buttonLabel;
    cta.style.cssText = "display:block;padding:13px;border-radius:12px;background:#4f7cff;"
      + "color:#fff;font-weight:600;text-decoration:none";
    card.appendChild(cta);

    var close = document.createElement("button");
    close.textContent = "\\u00d7";
    close.setAttribute("aria-label", "Close");
    close.style.cssText = "position:absolute;top:18px;right:20px;background:transparent;"
      + "border:0;color:#fff;font-size:30px;line-height:1;cursor:pointer;opacity:.75";
    close.onclick = function () { overlay.remove(); };
    overlay.appendChild(close);

    overlay.appendChild(card);
    document.body.appendChild(overlay);
    return overlay;
  }

  window.AdsKinz = {
    key: key,
    fetchAd: request,
    show: function (format) { return request(format).then(render); },
    showInterstitial: function () { return this.show("interstitial"); },
    showPopInterstitial: function () { return this.show("popInterstitial"); }
  };
})();
"""

"""Click tracking and redirection.

    GET /+{tracking_id}   → HTTP 302 to the campaign destination

Served from tr.adskinz.me — a dedicated short-link host that points at this
API, never at the frontend. Fraud scoring decides whether the click is
billed, never whether the end user reaches the advertiser: blocking a real
person because a heuristic misfired would be far worse than skipping one
billable click.

The redirect itself only ever waits on ONE fast, indexed lookup (the
tracking link). Everything else — fraud scoring, the Click row, billing —
runs as a background task *after* the 302 has already been sent, via its
own database session (never the request's, which FastAPI tears down once
the response finishes). That's the fix for the 4-10s redirect delay: the
whole scoring+billing chain used to run in the request path itself, so the
visitor's browser sat waiting on all of it before it ever got redirected.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.config import settings
from app.core.deps import ClientIPHashDep, SessionDep
from app.database import session_scope
from app.models.campaigns import Campaign
from app.models.tracking import Click, TrackingLink
from app.services import billing_service, fraud_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tracking"])

_REDIRECT_STATUS = 302
_NO_STORE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}
# The id is a 13-char alphanumeric code (see core.security.generate_tracking_id).
# The range is kept a little loose so the length can change later without a
# router edit.
_TRACKING_ID_RE = re.compile(r"^[A-Za-z0-9]{6,36}$")


@router.get(
    "/+{tracking_id}",
    status_code=_REDIRECT_STATUS,
    response_class=RedirectResponse,
    summary="Track a click and redirect to the advertiser",
    include_in_schema=True,
)
async def track_click(
    tracking_id: str,
    request: Request,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
    background_tasks: BackgroundTasks,
) -> RedirectResponse:
    fallback = RedirectResponse(
        url=settings.PUBLIC_BASE_URL, status_code=_REDIRECT_STATUS, headers=_NO_STORE
    )

    if not _TRACKING_ID_RE.match(tracking_id):
        return fallback

    # The only DB work the visitor actually waits on: one indexed lookup to
    # find out where to send them.
    link = (
        await session.execute(
            select(TrackingLink).where(TrackingLink.tracking_id == tracking_id)
        )
    ).scalar_one_or_none()
    if link is None:
        return fallback

    destination = link.destination_url or settings.PUBLIC_BASE_URL
    redirect = RedirectResponse(
        url=destination, status_code=_REDIRECT_STATUS, headers=_NO_STORE
    )

    if link.expires_at is not None and link.expires_at < datetime.now(UTC):
        # The link still resolves for the user, it is simply no longer billable.
        return redirect

    # Scoring, the Click row, and billing all happen after this response is
    # already on its way to the browser — the visitor never waits on any of
    # it. Pass plain values, not the request-scoped `link`/`session`
    # objects: both are torn down once this function returns, before the
    # background task actually runs.
    background_tasks.add_task(
        _record_click_background,
        link_id=link.id,
        tracking_id=tracking_id,
        ip_hash=ip_hash,
        user_agent=request.headers.get("user-agent"),
        referer=request.headers.get("referer"),
    )

    return redirect


async def _record_click_background(
    *,
    link_id,
    tracking_id: str,
    ip_hash: str | None,
    user_agent: str | None,
    referer: str | None,
) -> None:
    """Runs after the redirect has already been sent — its own session,
    never the request's. A failure here must never surface to the visitor;
    it already has its page."""
    try:
        async with session_scope() as session:
            link = await session.get(TrackingLink, link_id)
            if link is None:
                return
            await _record_click(
                session,
                link=link,
                tracking_id=tracking_id,
                ip_hash=ip_hash,
                user_agent=user_agent,
                referer=referer,
            )
    except Exception:  # noqa: BLE001 - a tracking failure must never propagate
        logger.exception("tracking.record_failed tracking_id=%s", tracking_id)


async def _record_click(
    session,
    *,
    link: TrackingLink,
    tracking_id: str,
    ip_hash: str | None,
    user_agent: str | None,
    referer: str | None,
) -> None:
    """Score, store and conditionally bill a click."""
    campaign = await session.get(Campaign, link.campaign_id)
    if campaign is None:
        return

    score, reasons = await fraud_service.score_click(
        session,
        tracking_id=tracking_id,
        ip_hash=ip_hash,
        user_agent=user_agent,
        referer=referer,
    )
    billable = fraud_service.should_bill(score)

    click = Click(
        tracking_id=tracking_id,
        campaign_id=campaign.id,
        scheduled_post_id=link.scheduled_post_id,
        placement_type=link.placement_type,
        placement_id=link.placement_id,
        ip_hash=ip_hash,
        user_agent=(user_agent or "")[:1000] or None,
        referer=(referer or "")[:1000] or None,
        fraud_score=score,
        fraud_reasons=reasons or None,
        clicked_at=datetime.now(UTC),
    )

    if billable and campaign.is_servable():
        # Flat, advertiser-chosen cost per click (Campaign.cpc_bid, $0.01-
        # $0.03) — not derived from cpm_bid, which used to make the
        # per-click price swing with the CPM bid (a high-CPM campaign could
        # be charged $0.83+ per click nobody had actually chosen).
        cost = billing_service.q6(campaign.cpc_bid)
        result = await billing_service.charge_campaign(
            session,
            campaign=campaign,
            amount=cost,
            units=1,
            event_type="click",
            placement_type=link.placement_type,
            placement_id=link.placement_id,
        )
        click.billed = result.ok
        click.billed_amount_usd = result.charged
    else:
        click.billed = False

    link.click_count = (link.click_count or 0) + 1
    session.add(click)
    await session.commit()


@router.get("/health", tags=["ops"], summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/deep", tags=["ops"], summary="Dependency probe")
async def health_deep(session: SessionDep) -> dict[str, object]:
    """Reports the state of every external dependency without leaking secrets."""
    from sqlalchemy import text

    from app.redis_client import redis_healthy

    database_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        database_ok = False

    return {
        "status": "ok" if database_ok else "degraded",
        "database": database_ok,
        "redis": await redis_healthy(),
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
    }


# Ignore favicon requests hitting the API host so they do not pollute the logs.
@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> RedirectResponse:
    return RedirectResponse(url=f"{settings.PUBLIC_BASE_URL}/favicon.ico", status_code=301)

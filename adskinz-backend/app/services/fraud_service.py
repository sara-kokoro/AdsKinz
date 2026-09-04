"""Click fraud scoring and anomaly detection.

Scoring is deliberately conservative and *never* blocks a user: a suspicious
click is still redirected to the advertiser's destination, it is simply not
billed. Blocking real people to save a fraction of a cent would cost the
advertiser far more than the fraud itself.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.tracking import Anomaly, Click
from app.redis_client import claim_once, click_velocity

logger = logging.getLogger(__name__)

# Signals, each contributing to a 0..1 score.
_W_VELOCITY_HIGH = Decimal("0.45")
_W_VELOCITY_EXTREME = Decimal("0.75")
_W_BOT_UA = Decimal("0.60")
_W_MISSING_UA = Decimal("0.30")
_W_DUPLICATE = Decimal("0.80")
_W_NO_REFERER = Decimal("0.05")
_W_HEADLESS = Decimal("0.50")

_BOT_UA_RE = re.compile(
    r"(bot|crawl|spider|scrap|curl|wget|python-requests|httpx|axios|okhttp|"
    r"java/|go-http|libwww|phantomjs|headless)",
    re.IGNORECASE,
)
_KNOWN_BROWSER_RE = re.compile(
    r"(Mozilla/5\.0|Telegram|TelegramBot|Safari|Chrome|Firefox|Edg/)", re.IGNORECASE
)

VELOCITY_WINDOW_SECONDS = 300
VELOCITY_HIGH = 8
VELOCITY_EXTREME = 20


async def score_click(
    session: AsyncSession,
    *,
    tracking_id: str,
    ip_hash: str | None,
    user_agent: str | None,
    referer: str | None = None,
) -> tuple[Decimal, list[str]]:
    """Return ``(score, reasons)`` in the 0..1 range.

    A score at or above ``FRAUD_SCORE_BILLING_THRESHOLD`` means "do not bill".
    """
    score = Decimal("0")
    reasons: list[str] = []

    # 1. Duplicate click on the same tracking id — the strongest signal.
    #    Redis handles the hot path; the database is the fallback.
    first_time = await claim_once(f"click:{tracking_id}", ttl=3600)
    if not first_time:
        score += _W_DUPLICATE
        reasons.append("duplicate_tracking_id")
    else:
        already = (
            await session.execute(
                select(func.count())
                .select_from(Click)
                .where(Click.tracking_id == tracking_id)
            )
        ).scalar_one()
        if already:
            score += _W_DUPLICATE
            reasons.append("duplicate_tracking_id")

    # 2. Click velocity from the same hashed IP.
    if ip_hash:
        hits = await click_velocity(ip_hash, window=VELOCITY_WINDOW_SECONDS)
        if hits < 0:  # Redis unavailable, fall back to a database count
            since = datetime.now(UTC) - timedelta(seconds=VELOCITY_WINDOW_SECONDS)
            hits = (
                await session.execute(
                    select(func.count())
                    .select_from(Click)
                    .where(Click.ip_hash == ip_hash, Click.clicked_at >= since)
                )
            ).scalar_one()
        if hits >= VELOCITY_EXTREME:
            score += _W_VELOCITY_EXTREME
            reasons.append(f"extreme_velocity:{hits}")
        elif hits >= VELOCITY_HIGH:
            score += _W_VELOCITY_HIGH
            reasons.append(f"high_velocity:{hits}")

    # 3. User agent heuristics.
    ua = (user_agent or "").strip()
    if not ua:
        score += _W_MISSING_UA
        reasons.append("missing_user_agent")
    elif _BOT_UA_RE.search(ua):
        score += _W_BOT_UA
        reasons.append("bot_user_agent")
    elif not _KNOWN_BROWSER_RE.search(ua):
        score += _W_HEADLESS
        reasons.append("unrecognised_user_agent")

    # 4. Missing referer is weak on its own; Telegram in-app browsers often
    #    omit it, so it only nudges the score.
    if not referer:
        score += _W_NO_REFERER
        reasons.append("no_referer")

    final = min(Decimal("1.00"), score).quantize(Decimal("0.01"))
    return final, reasons


def should_bill(score: Decimal) -> bool:
    return score < settings.FRAUD_SCORE_BILLING_THRESHOLD


async def record_anomaly(
    session: AsyncSession,
    *,
    kind: str,
    subject_id: uuid.UUID | None,
    subject_label: str,
    reason: str,
    score: Decimal,
    details: dict | None = None,
) -> Anomaly | None:
    """Persist a finding, de-duplicated over a 24 hour window."""
    since = datetime.now(UTC) - timedelta(hours=24)
    existing = (
        await session.execute(
            select(Anomaly).where(
                Anomaly.kind == kind,
                Anomaly.subject_id == subject_id,
                Anomaly.reason == reason,
                Anomaly.detected_at >= since,
                Anomaly.resolved.is_(False),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.score = max(existing.score, score)
        return existing

    anomaly = Anomaly(
        kind=kind,
        subject_id=subject_id,
        subject_label=subject_label,
        reason=reason,
        score=score,
        details=details,
    )
    session.add(anomaly)
    logger.info("anomaly.detected kind=%s subject=%s reason=%s", kind, subject_label, reason)
    return anomaly


async def scan_campaign_ctr(session: AsyncSession) -> int:
    """Flag campaigns whose CTR is implausibly high for Telegram inventory.

    A genuine channel ad rarely exceeds a few percent; anything above 25% over a
    meaningful volume is worth a human look.
    """
    from app.models.campaigns import Campaign

    rows = (
        await session.execute(
            select(Campaign).where(Campaign.impressions >= 1000, Campaign.clicks > 0)
        )
    ).scalars().unique().all()

    flagged = 0
    for campaign in rows:
        ctr = campaign.clicks / campaign.impressions
        if ctr >= 0.25:
            await record_anomaly(
                session,
                kind="campaign",
                subject_id=campaign.id,
                subject_label=campaign.name,
                reason=f"Abnormally high CTR ({ctr * 100:.1f}%)",
                score=Decimal("0.80"),
                details={"ctr": round(ctr, 4), "clicks": campaign.clicks,
                         "impressions": campaign.impressions},
            )
            flagged += 1
    return flagged


async def scan_channel_view_spikes(session: AsyncSession) -> int:
    """Flag channels whose ad views far exceed their declared subscriber count."""
    from app.models.placements import Channel
    from app.models.tracking import ScheduledPost

    since = datetime.now(UTC) - timedelta(days=7)
    rows = (
        await session.execute(
            select(
                Channel,
                func.coalesce(func.max(ScheduledPost.last_view_count), 0).label("peak"),
            )
            .join(ScheduledPost, ScheduledPost.channel_id == Channel.id)
            .where(ScheduledPost.posted_at >= since)
            .group_by(Channel.id)
        )
    ).all()

    flagged = 0
    for channel, peak in rows:
        if channel.subscriber_count and peak > channel.subscriber_count * 3:
            await record_anomaly(
                session,
                kind="channel",
                subject_id=channel.id,
                subject_label=channel.name,
                reason=(
                    f"Ad views ({peak}) far exceed the declared subscriber count "
                    f"({channel.subscriber_count})"
                ),
                score=Decimal("0.70"),
                details={"peak_views": int(peak), "subscribers": channel.subscriber_count},
            )
            flagged += 1
    return flagged


async def scan_unbilled_click_ratio(session: AsyncSession) -> int:
    """Flag campaigns where most recent clicks were rejected as fraudulent."""
    from app.models.campaigns import Campaign

    since = datetime.now(UTC) - timedelta(hours=24)
    rows = (
        await session.execute(
            select(
                Click.campaign_id,
                func.count().label("total"),
                func.sum(func.cast(Click.billed, Integer)).label("billed"),
            )
            .where(Click.clicked_at >= since)
            .group_by(Click.campaign_id)
            .having(func.count() >= 50)
        )
    ).all()

    flagged = 0
    for campaign_id, total, billed in rows:
        billed = int(billed or 0)
        rejected_ratio = 1 - (billed / total)
        if rejected_ratio >= 0.5:
            campaign = await session.get(Campaign, campaign_id)
            await record_anomaly(
                session,
                kind="campaign",
                subject_id=campaign_id,
                subject_label=campaign.name if campaign else str(campaign_id),
                reason=f"{rejected_ratio * 100:.0f}% of clicks rejected as invalid in 24h",
                score=Decimal("0.65"),
                details={"clicks": int(total), "billed": billed},
            )
            flagged += 1
    return flagged

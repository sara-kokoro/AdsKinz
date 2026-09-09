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
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

from app.config import settings
from app.models.tracking import Anomaly, Click, ScheduledPost, ViewSnapshot
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

# --- Purchased-views signals (a post whose views were bought, not earned) ---
# A post needs this many billed views before its own CTR is statistically
# meaningful enough to compare against anything.
MIN_VIEWS_FOR_CTR_CHECK = 200
# A channel needs at least this many qualifying posts before its own click
# behaviour is trusted as a "baseline" to compare a single post against.
MIN_POSTS_FOR_BASELINE = 5
# A post's CTR at or below this fraction of its channel's baseline CTR is
# flagged — bought views don't click, so a real fraud case collapses far
# below this, not just "a bit under average".
CTR_COLLAPSE_RATIO = Decimal("0.20")

# A post needs at least this many view-poll snapshots before "is one of
# them a burst?" is meaningful.
MIN_SNAPSHOTS_FOR_BURST_CHECK = 4
# One interval's delta must clear both of these to count as a burst: an
# absolute floor (so a tiny channel's normal noise never trips it) and a
# multiple of the post's own typical interval (so it's relative to what's
# normal for that post, not a global constant).
BURST_MIN_ABSOLUTE_VIEWS = 150
BURST_MULTIPLIER = Decimal("6")


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
            .options(lazyload(Channel.publisher))
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


async def scan_channel_ctr_baseline(session: AsyncSession) -> int:
    """Flag a post whose CTR collapses far below its own channel's baseline.

    This is the strongest purchased-views signal: a channel's audience has a
    fairly stable click behaviour post to post. Bought views never click, so
    a post padded with an SMM panel order shows a CTR that craters relative
    to everything else on the *same* channel — not just "below average" for
    the platform, which varies a lot channel to channel.
    """
    from app.models.placements import Channel

    since = datetime.now(UTC) - timedelta(days=30)

    posts = (
        await session.execute(
            select(ScheduledPost).where(
                ScheduledPost.posted_at >= since,
                ScheduledPost.billed_views >= MIN_VIEWS_FOR_CTR_CHECK,
            )
        )
    ).scalars().unique().all()
    if not posts:
        return 0

    post_ids = [p.id for p in posts]
    clicks_by_post: dict[uuid.UUID, int] = dict(
        (await session.execute(
            select(Click.scheduled_post_id, func.count().label("n"))
            .where(Click.scheduled_post_id.in_(post_ids))
            .group_by(Click.scheduled_post_id)
        )).all()
    )

    by_channel: dict[uuid.UUID, list[ScheduledPost]] = defaultdict(list)
    for post in posts:
        by_channel[post.channel_id].append(post)

    flagged = 0
    for channel_id, channel_posts in by_channel.items():
        if len(channel_posts) < MIN_POSTS_FOR_BASELINE:
            continue
        total_views = sum(p.billed_views for p in channel_posts)
        total_clicks = sum(clicks_by_post.get(p.id, 0) for p in channel_posts)
        if total_views == 0 or total_clicks == 0:
            continue
        baseline_ctr = total_clicks / total_views

        for post in channel_posts:
            post_clicks = clicks_by_post.get(post.id, 0)
            post_ctr = post_clicks / post.billed_views
            if post_ctr > baseline_ctr * float(CTR_COLLAPSE_RATIO):
                continue
            channel = await session.get(Channel, channel_id)
            await record_anomaly(
                session,
                kind="channel",
                subject_id=channel_id,
                subject_label=channel.name if channel else str(channel_id),
                reason=(
                    f"A post's CTR ({post_ctr * 100:.2f}%) collapsed to "
                    f"{(post_ctr / baseline_ctr * 100) if baseline_ctr else 0:.0f}% of this "
                    f"channel's own baseline ({baseline_ctr * 100:.2f}%) — consistent with "
                    f"purchased views that don't click"
                ),
                score=Decimal("0.80"),
                details={
                    "scheduled_post_id": str(post.id),
                    "tracking_id": post.tracking_id,
                    "post_views": post.billed_views,
                    "post_clicks": post_clicks,
                    "channel_baseline_ctr": round(baseline_ctr, 5),
                    "channel_posts_sampled": len(channel_posts),
                },
            )
            flagged += 1
    return flagged


async def scan_view_bursts(session: AsyncSession) -> int:
    """Flag a single 15-minute poll that added an implausible view burst.

    Organic Telegram views trickle in as subscribers open the app over
    hours; any one poll interval usually adds a small, fairly steady slice
    of a post's eventual total. An SMM panel instead delivers its order in
    one or two batches, so one snapshot's delta dwarfs every other snapshot
    for the same post — a shape genuine traffic essentially never produces.
    """
    since = datetime.now(UTC) - timedelta(hours=48)
    snapshots = (
        await session.execute(
            select(ViewSnapshot)
            .where(ViewSnapshot.polled_at >= since)
            .order_by(ViewSnapshot.scheduled_post_id, ViewSnapshot.polled_at)
        )
    ).scalars().all()

    by_post: dict[uuid.UUID, list[ViewSnapshot]] = defaultdict(list)
    for snap in snapshots:
        by_post[snap.scheduled_post_id].append(snap)

    flagged = 0
    for post_id, rows in by_post.items():
        if len(rows) < MIN_SNAPSHOTS_FOR_BURST_CHECK:
            continue
        latest = rows[-1]
        if latest.delta < BURST_MIN_ABSOLUTE_VIEWS:
            continue
        prior_deltas = [r.delta for r in rows[:-1] if r.delta > 0]
        if not prior_deltas:
            continue
        avg_prior = sum(prior_deltas) / len(prior_deltas)
        if avg_prior <= 0 or latest.delta < avg_prior * float(BURST_MULTIPLIER):
            continue

        post = await session.get(ScheduledPost, post_id)
        if post is None:
            continue
        channel = post.channel
        await record_anomaly(
            session,
            kind="channel",
            subject_id=post.channel_id,
            subject_label=channel.name if channel else str(post.channel_id),
            reason=(
                f"One 15-minute poll added {latest.delta} views — "
                f"{latest.delta / avg_prior:.1f}x this post's typical interval "
                f"({avg_prior:.0f} views) — consistent with a bulk view-delivery service"
            ),
            score=Decimal("0.70"),
            details={
                "scheduled_post_id": str(post_id),
                "tracking_id": post.tracking_id,
                "burst_delta": latest.delta,
                "typical_delta": round(avg_prior, 1),
                "polled_at": latest.polled_at.isoformat(),
            },
        )
        flagged += 1
    return flagged

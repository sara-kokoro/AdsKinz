"""Ad selection: which campaign wins a given slot.

The auction is a simple CPM-descending first-price selection among eligible
campaigns. Eligibility is a database read only — translations were generated
once at approval time, so serving an ad never calls an LLM.

The winning selection for a Mini App slot is cached in Redis for a few seconds:
the same key/lang/format combination is requested extremely often and the
eligible set changes slowly.
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.enums import CampaignFormat, CampaignStatus, WEEKDAY_KEYS
from app.models.accounts import Advertiser
from app.models.campaigns import Campaign, CampaignTranslation, utc_today
from app.models.placements import Channel
from app.models.tracking import ScheduledPost
from app.redis_client import cache_get, cache_set, get_channel_daily_posts

logger = logging.getLogger(__name__)

# Formats that can fill a Mini App slot.
_MINIAPP_FORMATS = {
    "interstitial": CampaignFormat.INTERSTITIAL.value,
    "popInterstitial": CampaignFormat.POP_INTERSTITIAL.value,
}

DEFAULT_FALLBACK_LANG = "en"


# --------------------------------------------------------------------------- #
# Creative resolution
# --------------------------------------------------------------------------- #
async def resolve_creative(
    session: AsyncSession, campaign: Campaign, lang: str
) -> tuple[str, str, str]:
    """Return ``(text, button_label, lang_used)`` for a campaign in a language.

    Falls back to the campaign's own copy when no translation exists, then to
    English. Never generates anything on the fly.
    """
    lang = (lang or DEFAULT_FALLBACK_LANG).lower()

    if lang == campaign.target_language or campaign.target_language == "all":
        pass  # still try a translation below, the original may not match

    rows = (
        (
            await session.execute(
                select(CampaignTranslation).where(
                    CampaignTranslation.campaign_id == campaign.id,
                    CampaignTranslation.lang_code.in_([lang, DEFAULT_FALLBACK_LANG]),
                )
            )
        )
        .scalars()
        .all()
    )
    by_lang = {row.lang_code: row for row in rows}

    chosen = by_lang.get(lang)
    if chosen is not None:
        return (
            chosen.translated_text,
            chosen.translated_button_label or campaign.button_label,
            lang,
        )

    if campaign.target_language in (lang, "all"):
        return campaign.ad_text, campaign.button_label, campaign.target_language

    fallback = by_lang.get(DEFAULT_FALLBACK_LANG)
    if fallback is not None:
        return (
            fallback.translated_text,
            fallback.translated_button_label or campaign.button_label,
            DEFAULT_FALLBACK_LANG,
        )

    return campaign.ad_text, campaign.button_label, campaign.target_language


# --------------------------------------------------------------------------- #
# Eligibility
# --------------------------------------------------------------------------- #
def _eligible_query(*, formats: list[str], lang: str | None):
    """Base query for campaigns that may currently be served."""
    stmt = (
        select(Campaign)
        .join(Advertiser, Advertiser.id == Campaign.advertiser_id)
        .where(
            Campaign.status == CampaignStatus.ACTIVE.value,
            Campaign.format.in_(formats),
            Campaign.spent_usd < Campaign.total_budget,
            Advertiser.is_blocked.is_(False),
            Advertiser.balance_usd > 0,
        )
    )
    if lang:
        stmt = stmt.where(Campaign.target_language.in_([lang, "all"]))
    return stmt.order_by(Campaign.cpm_bid.desc(), Campaign.created_at.asc())


async def _filter_daily_budget(
    session: AsyncSession, campaigns: list[Campaign]
) -> list[Campaign]:
    """Drop campaigns that already hit their daily cap."""
    from app.models.campaigns import CampaignDailySpend

    capped = [c for c in campaigns if c.daily_budget]
    if not capped:
        return campaigns

    rows = dict(
        (
            await session.execute(
                select(CampaignDailySpend.campaign_id, CampaignDailySpend.amount_usd).where(
                    CampaignDailySpend.campaign_id.in_([c.id for c in capped]),
                    CampaignDailySpend.spend_date == utc_today(),
                )
            )
        ).all()
    )

    keep: list[Campaign] = []
    for campaign in campaigns:
        if campaign.daily_budget:
            spent_today = Decimal(rows.get(campaign.id, 0) or 0)
            if spent_today >= Decimal(campaign.daily_budget):
                continue
        keep.append(campaign)
    return keep


# --------------------------------------------------------------------------- #
# Mini App slots
# --------------------------------------------------------------------------- #
async def select_for_mini_app(
    session: AsyncSession, *, lang: str, serve_format: str
) -> Campaign | None:
    """Pick the winning campaign for a Mini App slot.

    Uses a short Redis cache keyed by language and format. The cache stores the
    winner's id only; the campaign row is still loaded so budget and status are
    re-checked before the impression is recorded.
    """
    internal_format = _MINIAPP_FORMATS.get(serve_format)
    if internal_format is None:
        return None

    cache_key = settings.ns("adsel", internal_format, lang)
    cached_id = await cache_get(cache_key)
    if cached_id:
        try:
            campaign = await session.get(Campaign, uuid.UUID(str(cached_id)))
        except ValueError:
            campaign = None
        if campaign is not None and campaign.is_servable() and campaign.matches_language(lang):
            return campaign

    candidates = (
        (await session.execute(_eligible_query(formats=[internal_format], lang=lang)))
        .scalars()
        .unique()
        .all()
    )
    candidates = await _filter_daily_budget(session, list(candidates))
    if not candidates:
        return None

    winner = _pick_winner(candidates)
    await cache_set(cache_key, str(winner.id), ttl=settings.AD_SELECTION_CACHE_TTL)
    return winner


def _pick_winner(candidates: list[Campaign]) -> Campaign:
    """First-price CPM auction with a tie-break.

    Campaigns sharing the top bid rotate randomly so one advertiser cannot
    monopolise a slot purely by having registered first.
    """
    top_bid = candidates[0].cpm_bid
    tied = [c for c in candidates if c.cpm_bid == top_bid]
    return random.choice(tied) if len(tied) > 1 else candidates[0]


# --------------------------------------------------------------------------- #
# Channel slots (native posting)
# --------------------------------------------------------------------------- #
async def ads_posted_today(session: AsyncSession, channel_id: uuid.UUID) -> int:
    """How many ads a channel already received today (UTC)."""
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    cached = await get_channel_daily_posts(channel_id, day)
    if cached is not None:
        return cached

    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        await session.execute(
            select(func.count())
            .select_from(ScheduledPost)
            .where(
                ScheduledPost.channel_id == channel_id,
                ScheduledPost.posted_at >= start,
            )
        )
    ).scalar_one()


async def select_for_channel(
    session: AsyncSession, channel: Channel, *, exclude: set[uuid.UUID] | None = None
) -> Campaign | None:
    """Pick the winning campaign for a native post in ``channel``.

    Only campaigns of format ``channel_native`` compete, filtered on the
    channel's declared language.
    """
    candidates = (
        (
            await session.execute(
                _eligible_query(
                    formats=[CampaignFormat.NATIVE_POST.value],
                    lang=channel.declared_language,
                )
            )
        )
        .scalars()
        .unique()
        .all()
    )
    candidates = await _filter_daily_budget(session, list(candidates))

    if exclude:
        candidates = [c for c in candidates if c.id not in exclude]

    # Do not post the same campaign twice in a row in the same channel.
    recent = (
        (
            await session.execute(
                select(ScheduledPost.campaign_id)
                .where(
                    ScheduledPost.channel_id == channel.id,
                    ScheduledPost.posted_at >= datetime.now(UTC) - timedelta(hours=24),
                )
                .order_by(ScheduledPost.posted_at.desc())
                .limit(3)
            )
        )
        .scalars()
        .all()
    )
    recent_set = set(recent)
    fresh = [c for c in candidates if c.id not in recent_set]

    # If every remaining candidate already ran in this channel recently,
    # skip the slot instead of falling back to a repeat: that fallback used
    # to silently defeat the whole point of `recent_set` whenever a channel
    # only had one eligible campaign, letting the same ad post over and
    # over in the same channel every dispatch cycle.
    return _pick_winner(fresh) if fresh else None


async def channel_has_slot(session: AsyncSession, channel: Channel) -> bool:
    """Whether the channel can still receive an ad today.

    The trust window cap is computed live from ``started_at``; it is never
    stored on the row.
    """
    if not channel.accepts_delivery():
        return False
    quota = channel.effective_max_ads_per_day()
    if quota <= 0:
        return False

    # Respect the publisher's preferred UTC half-hour slots for today's
    # weekday, when they set any for that day. No entry for today (or an
    # empty list) is the same "no restriction" convention as before.
    # preferred_slots stores UTC minute-of-day on a 30-minute grid (see
    # app/schemas/publisher.py:validate_preferred_slots) — floor "now" onto
    # that same grid before comparing, rather than comparing to the raw
    # hour, which never matches now that slots are half-hour granular.
    if channel.preferred_slots:
        now = datetime.now(UTC)
        weekday_key = WEEKDAY_KEYS[now.weekday()]
        today_slots = channel.preferred_slots.get(weekday_key)
        now_slot = now.hour * 60 + (now.minute // 30) * 30
        if today_slots and now_slot not in today_slots:
            return False

    return await ads_posted_today(session, channel.id) < quota


async def eligible_channels(session: AsyncSession) -> list[Channel]:
    """Channels currently able to receive a native ad."""
    from app.core.enums import ChannelStatus

    rows = (
        (
            await session.execute(
                select(Channel).where(
                    Channel.status.in_(
                        [
                            ChannelStatus.ACTIVE.value,
                            ChannelStatus.ACTIVE_BUILDING_TRUST.value,
                        ]
                    ),
                    Channel.bot_admin_verified.is_(True),
                    Channel.telegram_chat_id.is_not(None),
                    Channel.max_ads_per_day > 0,
                )
            )
        )
        .scalars()
        .unique()
        .all()
    )

    available: list[Channel] = []
    for channel in rows:
        if await channel_has_slot(session, channel):
            available.append(channel)
    return available

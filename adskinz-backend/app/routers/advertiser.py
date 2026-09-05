"""Advertiser endpoints.

    GET    /advertiser/campaigns
    POST   /advertiser/campaigns
    GET    /advertiser/campaigns/{campaign_id}
    PATCH  /advertiser/campaigns/{campaign_id}
    GET    /advertiser/campaigns/{campaign_id}/translations
    GET    /advertiser/campaigns/{campaign_id}/recent-placements
    GET    /advertiser/stats
    POST   /advertiser/creatives/generate
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select

from app.config import settings
from app.core.deps import (
    ClientIPHashDep,
    CurrentAdvertiserDep,
    SessionDep,
    generate_rate_limit,
)
from app.core.enums import CampaignStatus
from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
)
from app.models.campaigns import (
    Campaign,
    CampaignDailySpend,
    CampaignTranslation,
    campaign_format_from_frontend,
    campaign_format_to_frontend,
    campaign_status_to_frontend,
)
from app.models.placements import Channel
from app.models.tracking import ScheduledPost
from app.schemas.advertiser import (
    AdvertiserStatsResponse,
    CampaignCreateRequest,
    CampaignListResponse,
    CampaignResponse,
    CampaignTranslationsResponse,
    CampaignUpdateRequest,
    GenerateCopyRequest,
    GenerateCopyResponse,
    ImageUploadRequest,
    RecentPlacementItem,
    RecentPlacementsResponse,
    TranslationItem,
)
from app.services import billing_service, openrouter_service, upload_service

router = APIRouter(prefix="/advertiser", tags=["advertiser"])


def _to_response(campaign: Campaign) -> CampaignResponse:
    """Map an ORM campaign onto the exact shape the frontend expects."""
    return CampaignResponse(
        id=str(campaign.id),
        name=campaign.name,
        language=campaign.target_language,
        status=campaign_status_to_frontend(campaign.status),  # type: ignore[arg-type]
        format=campaign_format_to_frontend(campaign.format),  # type: ignore[arg-type]
        cpm=campaign.cpm_bid,
        budget=campaign.total_budget,
        spent=campaign.spent_usd,
        clicks=campaign.clicks,
        impressions=campaign.impressions,
        rejectionReason=campaign.rejection_reason,
        dailyBudget=campaign.daily_budget,
        destinationUrl=campaign.destination_url,
        buttonLabel=campaign.button_label,
        title=campaign.title,
        brandName=campaign.brand_name,
        copy=campaign.ad_text,
        imageUrl=campaign.image_url,
        createdAt=campaign.created_at,
        updatedAt=campaign.updated_at,
        approvedAt=campaign.approved_at,
        aiGenerated=campaign.ai_generated,
    )


async def _owned_campaign(
    session: SessionDep, advertiser_id: uuid.UUID, campaign_id: uuid.UUID
) -> Campaign:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None or campaign.advertiser_id != advertiser_id:
        raise NotFoundError("Campaign not found.")
    return campaign


def _post_link(channel: Channel, telegram_message_id: int | None) -> str | None:
    """Build a clickable Telegram deep link to a specific published post.

    Public channels use the friendly ``t.me/<username>/<id>`` form; a
    channel without a public username (private) still gets a working link
    via the ``t.me/c/<internal_id>/<id>`` form, which resolves for anyone
    who is already a member of that chat.
    """
    if telegram_message_id is None:
        return None
    if channel.telegram_username:
        handle = channel.telegram_username.lstrip("@")
        return f"https://t.me/{handle}/{telegram_message_id}"
    if channel.telegram_chat_id is not None:
        raw = str(channel.telegram_chat_id)
        internal_id = raw[4:] if raw.startswith("-100") else raw.lstrip("-")
        return f"https://t.me/c/{internal_id}/{telegram_message_id}"
    return None


# --------------------------------------------------------------------------- #
# Campaigns
# --------------------------------------------------------------------------- #
@router.get("/campaigns", response_model=CampaignListResponse, summary="List campaigns")
async def list_campaigns(
    advertiser: CurrentAdvertiserDep,
    session: SessionDep,
    status_filter: str | None = None,
) -> CampaignListResponse:
    stmt = (
        select(Campaign)
        .where(Campaign.advertiser_id == advertiser.id)
        .order_by(Campaign.created_at.desc())
    )
    if status_filter and status_filter != "all":
        # Accept the frontend's vocabulary as well as the internal one.
        internal = (
            CampaignStatus.PAUSED_INSUFFICIENT_BALANCE.value
            if status_filter == "paused_balance"
            else status_filter
        )
        stmt = stmt.where(Campaign.status == internal)

    rows = (await session.execute(stmt)).scalars().unique().all()
    return CampaignListResponse(
        items=[_to_response(row) for row in rows], total=len(rows)
    )


@router.post(
    "/campaigns",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a campaign (always starts in review)",
)
async def create_campaign(
    payload: CampaignCreateRequest,
    advertiser: CurrentAdvertiserDep,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> CampaignResponse:
    """A new campaign is always ``pending_review`` and starts with $0 budget.

    The campaign's budget is an isolated pot, separate from the wallet. No
    money moves at creation — the advertiser funds the campaign afterwards
    with a top-up (``PATCH .../campaigns/{id}`` with ``add_budget``), which is
    the only moment money actually leaves the wallet.
    """
    campaign = Campaign(
        advertiser_id=advertiser.id,
        name=payload.name,
        format=campaign_format_from_frontend(payload.format),
        status=CampaignStatus.PENDING_REVIEW.value,
        target_language=payload.target_language,
        image_url=payload.image_url,
        title=payload.title,
        brand_name=payload.brand_name,
        ad_text=payload.ad_text,
        ai_generated=payload.ai_generated,
        button_label=payload.button_label,
        destination_url=payload.destination_url,
        cpm_bid=payload.cpm_bid,
        total_budget=Decimal("0.00"),
        daily_budget=payload.daily_budget,
        submitted_ip_hash=ip_hash,
    )
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return _to_response(campaign)


@router.get(
    "/campaigns/{campaign_id}",
    response_model=CampaignResponse,
    summary="Campaign detail",
)
async def get_campaign(
    campaign_id: uuid.UUID,
    advertiser: CurrentAdvertiserDep,
    session: SessionDep,
) -> CampaignResponse:
    campaign = await _owned_campaign(session, advertiser.id, campaign_id)
    return _to_response(campaign)


@router.patch(
    "/campaigns/{campaign_id}",
    response_model=CampaignResponse,
    summary="Update a campaign",
)
async def update_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignUpdateRequest,
    advertiser: CurrentAdvertiserDep,
    session: SessionDep,
) -> CampaignResponse:
    """Editing creative or targeting sends the campaign back to moderation.

    Pure budget or state changes (pause, resume, top-up) do not, so an
    advertiser can add funds to a running campaign without losing delivery.
    """
    campaign = await _owned_campaign(session, advertiser.id, campaign_id)

    if campaign.status == CampaignStatus.PENDING_REVIEW.value and payload.status:
        raise ConflictError("A campaign under review cannot change state.")

    content_changed = False
    for field, attribute in (
        ("name", "name"),
        ("title", "title"),
        ("brand_name", "brand_name"),
        ("ad_text", "ad_text"),
        ("button_label", "button_label"),
        ("destination_url", "destination_url"),
        ("target_language", "target_language"),
        ("image_url", "image_url"),
    ):
        value = getattr(payload, field)
        if value is not None and value != getattr(campaign, attribute):
            setattr(campaign, attribute, value)
            if field != "name":
                content_changed = True

    if payload.cpm_bid is not None:
        campaign.cpm_bid = payload.cpm_bid
    if payload.daily_budget is not None:
        campaign.daily_budget = payload.daily_budget

    if payload.total_budget is not None:
        if payload.total_budget < campaign.spent_usd:
            raise BusinessRuleError(
                "The new total budget is lower than the amount already spent."
            )
        delta = payload.total_budget - Decimal(campaign.total_budget)
        if delta > 0:
            # Growing the budget this way still moves real money out of the
            # wallet, same as a top-up.
            await billing_service.fund_campaign(
                session, advertiser=advertiser, campaign=campaign, amount=delta
            )
        elif delta < 0:
            # Shrinking it returns the difference — it was never spent.
            await billing_service.refund_campaign(
                session, advertiser=advertiser, campaign=campaign, amount=-delta
            )
        if campaign.remaining_budget >= settings.CAMPAIGN_LOW_BALANCE_THRESHOLD:
            campaign.low_balance_alerted_at = None

    if payload.add_budget is not None:
        # The only "recharge" action: moves money out of the wallet into this
        # campaign's isolated budget. Raises InsufficientBalanceError itself
        # if the wallet can't cover it.
        await billing_service.fund_campaign(
            session, advertiser=advertiser, campaign=campaign, amount=payload.add_budget
        )
        if campaign.status == CampaignStatus.STOPPED.value:
            campaign.status = CampaignStatus.ACTIVE.value
        if campaign.remaining_budget >= settings.CAMPAIGN_LOW_BALANCE_THRESHOLD:
            campaign.low_balance_alerted_at = None

    if payload.status is not None:
        if payload.status == "paused":
            # Pausing keeps the reserved money in the campaign — it isn't
            # refunded, since the advertiser may resume at any time.
            campaign.status = CampaignStatus.PAUSED.value
        elif payload.status == "stopped":
            # Stopping is final: whatever is left of this campaign's isolated
            # budget goes back to the wallet.
            await billing_service.refund_campaign(
                session,
                advertiser=advertiser,
                campaign=campaign,
                amount=campaign.remaining_budget,
            )
            campaign.status = CampaignStatus.STOPPED.value
        elif payload.status == "active":
            if campaign.status not in (
                CampaignStatus.PAUSED.value,
                CampaignStatus.PAUSED_INSUFFICIENT_BALANCE.value,
            ):
                raise ConflictError("Only a paused campaign can be resumed.")
            if campaign.is_exhausted:
                raise BusinessRuleError(
                    "This campaign has spent its whole budget. Add budget to resume it."
                )
            campaign.status = CampaignStatus.ACTIVE.value

    if content_changed and campaign.status in (
        CampaignStatus.ACTIVE.value,
        CampaignStatus.PAUSED.value,
        CampaignStatus.PAUSED_INSUFFICIENT_BALANCE.value,
        CampaignStatus.REJECTED.value,
    ):
        # Creative changed: the campaign must be reviewed again, and the stored
        # translations no longer describe the current copy.
        campaign.status = CampaignStatus.PENDING_REVIEW.value
        campaign.rejection_reason = None
        campaign.translations_generated = False
        campaign.approved_at = None

    await session.commit()
    await session.refresh(campaign)
    return _to_response(campaign)


@router.get(
    "/campaigns/{campaign_id}/translations",
    response_model=CampaignTranslationsResponse,
    summary="Stored translations for a campaign",
)
async def campaign_translations(
    campaign_id: uuid.UUID,
    advertiser: CurrentAdvertiserDep,
    session: SessionDep,
) -> CampaignTranslationsResponse:
    """Translations are generated once at approval, never at serve time."""
    campaign = await _owned_campaign(session, advertiser.id, campaign_id)
    rows = (
        (
            await session.execute(
                select(CampaignTranslation)
                .where(CampaignTranslation.campaign_id == campaign.id)
                .order_by(CampaignTranslation.lang_code)
            )
        )
        .scalars()
        .all()
    )
    return CampaignTranslationsResponse(
        campaign_id=campaign.id,
        source_language=campaign.target_language,
        generated=campaign.translations_generated,
        translations=[
            TranslationItem(
                lang_code=row.lang_code,
                translated_text=row.translated_text,
                translated_button_label=row.translated_button_label,
            )
            for row in rows
        ],
    )


@router.get(
    "/campaigns/{campaign_id}/recent-placements",
    response_model=RecentPlacementsResponse,
    summary="Last 10 channels this campaign's ad was posted into",
)
async def campaign_recent_placements(
    campaign_id: uuid.UUID,
    advertiser: CurrentAdvertiserDep,
    session: SessionDep,
) -> RecentPlacementsResponse:
    """Most recent 10 native posts of this campaign, one row per post.

    Includes posts that have since been auto-deleted (24h lifetime) — the
    advertiser still gets to see where their ad ran, only the live "open
    post" link stops resolving once Telegram has removed the message.
    """
    campaign = await _owned_campaign(session, advertiser.id, campaign_id)

    rows = (
        (
            await session.execute(
                select(ScheduledPost, Channel)
                .join(Channel, Channel.id == ScheduledPost.channel_id)
                .where(
                    ScheduledPost.campaign_id == campaign.id,
                    ScheduledPost.posted_at.is_not(None),
                )
                .order_by(ScheduledPost.posted_at.desc())
                .limit(10)
            )
        )
        .all()
    )

    return RecentPlacementsResponse(
        items=[
            RecentPlacementItem(
                channelName=channel.name,
                channelLink=channel.public_link,
                postLink=_post_link(channel, post.telegram_message_id),
                postedAt=post.posted_at,
            )
            for post, channel in rows
        ],
    )


# --------------------------------------------------------------------------- #
# Stats
# --------------------------------------------------------------------------- #
@router.get("/stats", response_model=AdvertiserStatsResponse, summary="Dashboard stats")
async def stats(
    advertiser: CurrentAdvertiserDep,
    session: SessionDep,
) -> AdvertiserStatsResponse:
    totals = (
        await session.execute(
            select(
                func.coalesce(func.sum(Campaign.impressions), 0),
                func.coalesce(func.sum(Campaign.clicks), 0),
                func.coalesce(func.sum(Campaign.spent_usd), 0),
                func.count(Campaign.id).filter(
                    Campaign.status == CampaignStatus.ACTIVE.value
                ),
                func.count(Campaign.id).filter(
                    Campaign.status == CampaignStatus.PENDING_REVIEW.value
                ),
            ).where(Campaign.advertiser_id == advertiser.id)
        )
    ).one()
    impressions, clicks, spend, active_count, pending_count = totals

    since = (datetime.now(UTC) - timedelta(days=30)).date()
    daily_rows = (
        await session.execute(
            select(
                CampaignDailySpend.spend_date,
                func.coalesce(func.sum(CampaignDailySpend.impressions), 0),
                func.coalesce(func.sum(CampaignDailySpend.clicks), 0),
            )
            .join(Campaign, Campaign.id == CampaignDailySpend.campaign_id)
            .where(
                Campaign.advertiser_id == advertiser.id,
                CampaignDailySpend.spend_date >= since,
            )
            .group_by(CampaignDailySpend.spend_date)
            .order_by(CampaignDailySpend.spend_date)
        )
    ).all()

    impressions_month = sum(int(row[1]) for row in daily_rows)
    clicks_30 = sum(int(row[2]) for row in daily_rows)
    daily = [float(row[1]) for row in daily_rows]

    active_budget = await billing_service.committed_active_budget(session, advertiser.id)
    total_impressions = int(impressions or 0)
    total_clicks = int(clicks or 0)

    return AdvertiserStatsResponse(
        balance=advertiser.balance_usd,
        activeBudget=active_budget,
        totalImpressions=total_impressions,
        impressionsMonth=impressions_month,
        clicks30=clicks_30,
        ctr=round(total_clicks / total_impressions * 100, 2) if total_impressions else 0.0,
        spend=Decimal(spend or 0),
        activeCampaigns=int(active_count or 0),
        pendingCampaigns=int(pending_count or 0),
        daily=daily,
    )


# --------------------------------------------------------------------------- #
# AI creative generation
# --------------------------------------------------------------------------- #
@router.post(
    "/creatives/generate",
    response_model=GenerateCopyResponse,
    dependencies=[Depends(generate_rate_limit)],
    summary="Draft ad copy with AI",
)
async def generate_creative(
    payload: GenerateCopyRequest,
    advertiser: CurrentAdvertiserDep,
) -> GenerateCopyResponse:
    text, model, tokens = await openrouter_service.generate_ad_copy(
        payload.brief, language=payload.language, tone=payload.tone
    )
    return GenerateCopyResponse(copy=text, model=model, tokens_used=tokens)


@router.post(
    "/creatives/upload-url",
    summary="Get a presigned URL to upload a creative image",
)
async def creative_upload_url(
    payload: ImageUploadRequest,
    advertiser: CurrentAdvertiserDep,
) -> dict[str, str]:
    """Return a short-lived signed URL. The browser uploads the file
    directly to R2 with a PUT request — the bytes never pass through
    this API."""
    return upload_service.create_upload_url(
        content_type=payload.content_type, advertiser_id=advertiser.id
    )


@router.get(
    "/languages",
    summary="Supported targeting languages",
)
async def supported_languages() -> dict[str, list[str]]:
    from app.core.enums import AD_LANGUAGES, BUTTON_LABELS

    return {
        "languages": list(AD_LANGUAGES),
        "translated": settings.translation_langs,
        "buttonLabels": list(BUTTON_LABELS),
    }

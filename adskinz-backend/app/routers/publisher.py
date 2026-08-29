"""Publisher endpoints.

    GET/POST /publisher/channels
    GET      /publisher/channels/bot-status
    POST     /publisher/channels/{channel_id}/start
    POST     /publisher/channels/{channel_id}/verify-bot
    POST     /publisher/channels/{channel_id}/suspend
    POST     /publisher/channels/{channel_id}/resume
    POST     /publisher/channels/{channel_id}/archive
    GET      /publisher/channels/{channel_id}/stats
    POST     /publisher/channels/logo-upload-url
    GET/POST /publisher/mini-apps
    GET      /publisher/mini-apps/{mini_app_id}/key
    POST     /publisher/mini-apps/{mini_app_id}/suspend
    POST     /publisher/mini-apps/{mini_app_id}/resume
    POST     /publisher/mini-apps/{mini_app_id}/archive
    GET/POST /publisher/withdrawals
    GET      /publisher/stats
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.config import settings
from app.core.deps import ClientIPHashDep, CurrentPublisherDep, SessionDep
from app.core.enums import ChannelStatus, MiniAppStatus, WithdrawalStatus
from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    InsufficientBalanceError,
    NotFoundError,
    WithdrawalCooldownError,
)
from app.core.security import generate_kinz_key
from app.models.finance import Withdrawal
from app.models.placements import Channel, MiniApp, PlacementDailyStat
from app.models.tracking import Click, Impression, ScheduledPost
from app.schemas.publisher import (
    BotStatusItem,
    BotStatusResponse,
    ChannelCreateRequest,
    ChannelListResponse,
    ChannelResponse,
    ChannelStatsResponse,
    LogoUploadRequest,
    MiniAppCreateRequest,
    MiniAppKeyResponse,
    MiniAppListResponse,
    MiniAppResponse,
    PublisherStatsResponse,
    WithdrawalCreateRequest,
    WithdrawalListResponse,
    WithdrawalResponse,
)
from app.services import ad_selection_service, billing_service, moderation_service, upload_service

router = APIRouter(prefix="/publisher", tags=["publisher"])


# --------------------------------------------------------------------------- #
# Mapping helpers
# --------------------------------------------------------------------------- #
async def _channel_response(session: SessionDep, channel: Channel) -> ChannelResponse:
    now = datetime.now(UTC)
    ads_today = await ad_selection_service.ads_posted_today(session, channel.id)
    return ChannelResponse(
        id=str(channel.id),
        name=channel.name,
        language=channel.declared_language,
        subscribers=channel.subscriber_count,
        subscribersUpdatedAt=channel.subscriber_count_updated_at,
        status=channel.status_for_frontend(now),  # type: ignore[arg-type]
        publicLink=channel.public_link,
        privateLink=channel.private_invite_link or None,
        adminUsername=channel.admin_username or None,
        logoUrl=channel.logo_url or None,
        maxAdsPerDay=channel.max_ads_per_day,
        effectiveMaxAdsPerDay=channel.effective_max_ads_per_day(now),
        preferredHours=channel.preferred_hours_utc,
        rejectionReason=channel.rejection_reason,
        botAdminVerified=channel.bot_admin_verified,
        trustHoursLeft=channel.trust_hours_left(now),
        trustEndsAt=channel.trust_window_ends_at(),
        impressions=channel.lifetime_impressions,
        earnings=channel.lifetime_earnings_usd,
        adsToday=ads_today,
        createdAt=channel.created_at,
        approvedAt=channel.approved_at,
        startedAt=channel.started_at,
    )


# The dashboard labels the second format "pop"; the SDK calls it
# "popInterstitial". Storage uses the SDK spelling, responses use the UI one.
_FORMAT_TO_UI = {"interstitial": "interstitial", "popInterstitial": "pop"}


def _mini_app_response(mini_app: MiniApp, *, reveal_key: bool = True) -> MiniAppResponse:
    return MiniAppResponse(
        id=str(mini_app.id),
        name=mini_app.name,
        url=mini_app.url,
        originalUrl=mini_app.original_url,
        botId=mini_app.bot_id,
        botUsername=mini_app.bot_username,
        botVerificationEnabled=bool(mini_app.bot_token),
        status=mini_app.status,  # type: ignore[arg-type]
        formats=[
            _FORMAT_TO_UI.get(f, f) for f in (mini_app.formats_enabled or [])
        ],
        kinzKey=mini_app.kinz_key if reveal_key else None,
        rejectionReason=mini_app.rejection_reason,
        integrationDetected=mini_app.integration_detected,
        impressions=mini_app.lifetime_impressions,
        earnings=mini_app.lifetime_earnings_usd,
        createdAt=mini_app.created_at,
        archivedAt=mini_app.archived_at,
    )


def _withdrawal_response(row: Withdrawal) -> WithdrawalResponse:
    return WithdrawalResponse(
        id=str(row.id),
        amount=row.amount_usd,
        address=row.destination_address,
        memo=row.memo_comment,
        method=row.method_label,
        status=row.status,  # type: ignore[arg-type]
        rejectionReason=row.rejection_reason,
        txHash=row.tx_hash,
        requestedAt=row.requested_at,
        paidAt=row.paid_at,
    )


# --------------------------------------------------------------------------- #
# Channels
# --------------------------------------------------------------------------- #
@router.get("/channels", response_model=ChannelListResponse, summary="List channels")
async def list_channels(
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> ChannelListResponse:
    rows = (
        (
            await session.execute(
                select(Channel)
                .where(Channel.publisher_id == publisher.id)
                .order_by(Channel.created_at.desc())
            )
        )
        .scalars()
        .unique()
        .all()
    )
    items = [await _channel_response(session, row) for row in rows]
    return ChannelListResponse(items=items, total=len(items))


@router.post(
    "/channels",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a channel for moderation",
)
async def create_channel(
    payload: ChannelCreateRequest,
    publisher: CurrentPublisherDep,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> ChannelResponse:
    """Register a channel. It starts in ``pending_moderation``.

    The subscriber count is read live from Telegram — publishers never
    self-declare it. Whether @AdsKinzBot is already an admin of the channel
    is checked and stored, but a missing admin right never blocks
    submission: the publisher can add the bot at any time afterwards and
    re-check from the channel's settings.
    """
    duplicate = (
        await session.execute(
            select(Channel.id).where(Channel.public_link == payload.public_link)
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise ConflictError("This channel has already been submitted.")

    from app.bot.aiogram_bot import fetch_chat_photo_bytes, resolve_chat, verify_bot_is_admin

    telegram_chat_id: int | None = None
    telegram_username: str | None = None
    subscriber_count = settings.MIN_CHANNEL_SUBSCRIBERS
    bot_admin_verified = False
    bot_checked_at: datetime | None = None
    logo_url = payload.logo_url

    try:
        chat_id, username, members, _ = await resolve_chat(payload.public_link)
        if chat_id is not None:
            telegram_chat_id = chat_id
            telegram_username = username
            if members is not None:
                if members < settings.MIN_CHANNEL_SUBSCRIBERS:
                    raise BusinessRuleError(
                        f"This channel has {members} subscribers on Telegram — "
                        f"AdsKinz requires at least {settings.MIN_CHANNEL_SUBSCRIBERS}."
                    )
                subscriber_count = members
            is_admin, can_post, can_delete, _ = await verify_bot_is_admin(chat_id)
            bot_admin_verified = bool(is_admin and can_post and can_delete)
            bot_checked_at = datetime.now(UTC)

            # The channel's logo is its own public Telegram photo — the bot
            # fetches and re-hosts it automatically, the publisher never
            # uploads one themselves.
            if not logo_url:
                photo_bytes = await fetch_chat_photo_bytes(chat_id)
                if photo_bytes:
                    logo_url = upload_service.upload_channel_logo_bytes(
                        publisher_id=publisher.id, data=photo_bytes
                    )
    except BusinessRuleError:
        raise
    except Exception:  # noqa: BLE001 - Telegram being unreachable must not block submission
        pass

    channel = Channel(
        publisher_id=publisher.id,
        name=payload.name,
        public_link=payload.public_link,
        private_invite_link=payload.private_invite_link,
        admin_username=payload.admin_username,
        logo_url=logo_url,
        description=payload.description,
        declared_language=payload.declared_language,
        subscriber_count=subscriber_count,
        max_ads_per_day=payload.max_ads_per_day,
        preferred_hours_utc=payload.preferred_hours_utc,
        submitted_ip_hash=ip_hash,
        telegram_chat_id=telegram_chat_id,
        telegram_username=telegram_username,
        bot_admin_verified=bot_admin_verified,
        bot_admin_last_checked_at=bot_checked_at,
    )

    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return await _channel_response(session, channel)


@router.get(
    "/channels/bot-status",
    response_model=BotStatusResponse,
    summary="Check @AdsKinzBot admin rights on every channel",
)
async def bot_status(
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> BotStatusResponse:
    rows = (
        (
            await session.execute(
                select(Channel).where(Channel.publisher_id == publisher.id)
            )
        )
        .scalars()
        .unique()
        .all()
    )

    items: list[BotStatusItem] = []
    all_ok = True
    for channel in rows:
        is_admin = can_post = can_delete = False
        error: str | None = None
        try:
            from app.bot.aiogram_bot import verify_bot_is_admin

            target = channel.telegram_chat_id or channel.public_link
            is_admin, can_post, can_delete, error = await verify_bot_is_admin(target)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)

        channel.bot_admin_verified = bool(is_admin and can_post and can_delete)
        channel.bot_admin_last_checked_at = datetime.now(UTC)
        all_ok = all_ok and channel.bot_admin_verified

        items.append(
            BotStatusItem(
                channelId=str(channel.id),
                name=channel.name,
                isAdmin=is_admin,
                canPost=can_post,
                canDelete=can_delete,
                checkedAt=channel.bot_admin_last_checked_at,
                error=error,
            )
        )

    await session.commit()
    return BotStatusResponse(
        botUsername=settings.BOT_USERNAME, items=items, allVerified=all_ok and bool(items)
    )


@router.post(
    "/channels/{channel_id}/verify-bot",
    response_model=ChannelResponse,
    summary="Re-check @AdsKinzBot admin rights on one channel",
)
async def verify_channel_bot(
    channel_id: uuid.UUID,
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> ChannelResponse:
    """Manual re-check triggered from the channel's settings ('Verify now').

    A negative result never changes the channel's moderation/delivery
    status — it only refreshes the badge so the publisher knows whether
    @AdsKinzBot still needs to be (re-)added as admin.
    """
    channel = await session.get(Channel, channel_id)
    if channel is None or channel.publisher_id != publisher.id:
        raise NotFoundError("Channel not found.")

    from app.bot.aiogram_bot import fetch_chat_photo_bytes, verify_bot_is_admin

    target = channel.telegram_chat_id or channel.public_link
    try:
        is_admin, can_post, can_delete, _ = await verify_bot_is_admin(target)
    except Exception:  # noqa: BLE001 - Telegram being unreachable must not break the check
        is_admin = can_post = can_delete = False

    channel.bot_admin_verified = bool(is_admin and can_post and can_delete)
    channel.bot_admin_last_checked_at = datetime.now(UTC)

    # Piggyback a logo refresh onto the manual re-check — a natural moment
    # to pick up a channel photo that wasn't set yet at submission time.
    if channel.telegram_chat_id is not None:
        try:
            photo_bytes = await fetch_chat_photo_bytes(channel.telegram_chat_id)
            if photo_bytes:
                channel.logo_url = upload_service.upload_channel_logo_bytes(
                    publisher_id=publisher.id, data=photo_bytes
                )
        except Exception:  # noqa: BLE001 - a logo refresh failure must not break the bot check
            pass

    await session.commit()
    await session.refresh(channel)
    return await _channel_response(session, channel)


@router.post(
    "/channels/{channel_id}/suspend",
    response_model=ChannelResponse,
    summary="Pause delivery on a channel without deleting it",
)
async def suspend_channel(
    channel_id: uuid.UUID,
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> ChannelResponse:
    """Stops new ads from being placed. Already-live posts keep running
    their normal 24h lifetime — this only stops new ones going up."""
    channel = await session.get(Channel, channel_id)
    if channel is None or channel.publisher_id != publisher.id:
        raise NotFoundError("Channel not found.")
    if channel.status == ChannelStatus.ARCHIVED.value:
        raise BusinessRuleError("Un-archive this channel before suspending it.")
    channel.status = ChannelStatus.SUSPENDED.value
    channel.suspended_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(channel)
    return await _channel_response(session, channel)


@router.post(
    "/channels/{channel_id}/resume",
    response_model=ChannelResponse,
    summary="Resume a suspended channel",
)
async def resume_channel(
    channel_id: uuid.UUID,
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> ChannelResponse:
    channel = await session.get(Channel, channel_id)
    if channel is None or channel.publisher_id != publisher.id:
        raise NotFoundError("Channel not found.")
    if channel.status != ChannelStatus.SUSPENDED.value:
        raise BusinessRuleError("Only a suspended channel can be resumed.")
    channel.status = (
        ChannelStatus.ACTIVE.value if channel.approved_at else ChannelStatus.APPROVED_NOT_STARTED.value
    )
    channel.suspended_at = None
    await session.commit()
    await session.refresh(channel)
    return await _channel_response(session, channel)


@router.post(
    "/channels/{channel_id}/archive",
    response_model=ChannelResponse,
    summary="Archive a channel (suspend + hide from the active list)",
)
async def archive_channel(
    channel_id: uuid.UUID,
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> ChannelResponse:
    """Archiving never deletes anything — history, stats and payouts already
    earned stay intact. It just stops delivery and moves the channel out of
    the way. There is no un-archive: re-adding the same channel later is a
    fresh submission, same as any platform that treats archive as final."""
    channel = await session.get(Channel, channel_id)
    if channel is None or channel.publisher_id != publisher.id:
        raise NotFoundError("Channel not found.")
    channel.status = ChannelStatus.ARCHIVED.value
    channel.archived_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(channel)
    return await _channel_response(session, channel)


@router.get(
    "/channels/{channel_id}/stats",
    response_model=ChannelStatsResponse,
    summary="Real-time stats for one channel",
)
async def channel_stats(
    channel_id: uuid.UUID,
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> ChannelStatsResponse:
    channel = await session.get(Channel, channel_id)
    if channel is None or channel.publisher_id != publisher.id:
        raise NotFoundError("Channel not found.")

    now = datetime.now(UTC)
    since_24h = now - timedelta(hours=24)

    lifetime_clicks = (
        await session.execute(
            select(func.count(Click.id)).where(
                Click.placement_type == "channel", Click.placement_id == channel.id
            )
        )
    ).scalar_one()

    last_24h_impressions_row = (
        await session.execute(
            select(func.count(Impression.id), func.coalesce(func.sum(Impression.billed_amount_usd), 0)).where(
                Impression.placement_type == "channel",
                Impression.placement_id == channel.id,
                Impression.served_at >= since_24h,
            )
        )
    ).one()
    last_24h_clicks_row = (
        await session.execute(
            select(func.count(Click.id), func.coalesce(func.sum(Click.billed_amount_usd), 0)).where(
                Click.placement_type == "channel",
                Click.placement_id == channel.id,
                Click.clicked_at >= since_24h,
            )
        )
    ).one()

    live_posts_count = (
        await session.execute(
            select(func.count(ScheduledPost.id)).where(
                ScheduledPost.channel_id == channel.id,
                ScheduledPost.deleted.is_(False),
                ScheduledPost.posted_at.is_not(None),
            )
        )
    ).scalar_one()

    impressions = channel.lifetime_impressions
    ctr = round((lifetime_clicks / impressions) * 100, 2) if impressions else 0.0
    effective_cpm = (
        (channel.lifetime_earnings_usd / impressions) * 1000 if impressions else Decimal("0.00")
    )
    ads_today = await ad_selection_service.ads_posted_today(session, channel.id)

    return ChannelStatsResponse(
        channelId=str(channel.id),
        status=channel.status_for_frontend(now),  # type: ignore[arg-type]
        subscribers=channel.subscriber_count,
        subscribersUpdatedAt=channel.subscriber_count_updated_at,
        lifetimeImpressions=impressions,
        lifetimeClicks=lifetime_clicks,
        lifetimeEarnings=channel.lifetime_earnings_usd,
        ctr=ctr,
        effectiveCpm=effective_cpm.quantize(Decimal("0.0001")),
        last24hImpressions=int(last_24h_impressions_row[0]),
        last24hEarnings=Decimal(last_24h_impressions_row[1]) + Decimal(last_24h_clicks_row[1]),
        last24hClicks=int(last_24h_clicks_row[0]),
        adsToday=ads_today,
        maxAdsPerDay=channel.max_ads_per_day,
        effectiveMaxAdsPerDay=channel.effective_max_ads_per_day(now),
        livePostsCount=live_posts_count,
        botAdminVerified=channel.bot_admin_verified,
        trustHoursLeft=channel.trust_hours_left(now),
    )


@router.post(
    "/channels/{channel_id}/start",
    response_model=ChannelResponse,
    summary="Start delivery on an approved channel",
)
async def start_channel(
    channel_id: uuid.UUID,
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> ChannelResponse:
    """Opens the trust window: one ad per day for the first 72 hours."""
    channel = await session.get(Channel, channel_id)
    if channel is None or channel.publisher_id != publisher.id:
        raise NotFoundError("Channel not found.")
    channel = await moderation_service.start_channel(session, channel)
    return await _channel_response(session, channel)


@router.post(
    "/channels/logo-upload-url",
    summary="Get a presigned URL to upload a channel logo",
)
async def channel_logo_upload_url(
    payload: LogoUploadRequest,
    publisher: CurrentPublisherDep,
) -> dict[str, str]:
    """Same mechanism as the advertiser creative upload: the browser PUTs
    the file directly to R2, only the resulting public URL comes back here."""
    return upload_service.create_channel_logo_upload_url(
        content_type=payload.content_type, publisher_id=publisher.id
    )


@router.patch(
    "/channels/{channel_id}",
    response_model=ChannelResponse,
    summary="Update channel delivery preferences",
)
async def update_channel(
    channel_id: uuid.UUID,
    payload: dict,
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> ChannelResponse:
    channel = await session.get(Channel, channel_id)
    if channel is None or channel.publisher_id != publisher.id:
        raise NotFoundError("Channel not found.")

    if "maxAdsPerDay" in payload:
        value = int(payload["maxAdsPerDay"])
        if not 0 <= value <= settings.MAX_ADS_PER_DAY:
            raise BusinessRuleError(
                f"Ads per day must be between 0 and {settings.MAX_ADS_PER_DAY}."
            )
        channel.max_ads_per_day = value

    if "preferredHours" in payload:
        hours = payload["preferredHours"] or None
        if hours and any(int(h) < 0 or int(h) > 23 for h in hours):
            raise BusinessRuleError("Preferred hours must be UTC hours between 0 and 23.")
        channel.preferred_hours_utc = sorted({int(h) for h in hours}) if hours else None

    if "logoUrl" in payload:
        logo_url = (payload["logoUrl"] or "").strip() or None
        if logo_url and not logo_url.startswith("https://"):
            raise BusinessRuleError("Logo URL must be a valid https:// address.")
        channel.logo_url = logo_url

    await session.commit()
    await session.refresh(channel)
    return await _channel_response(session, channel)


# --------------------------------------------------------------------------- #
# Mini Apps
# --------------------------------------------------------------------------- #
@router.get("/mini-apps", response_model=MiniAppListResponse, summary="List Mini Apps")
async def list_mini_apps(
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> MiniAppListResponse:
    rows = (
        (
            await session.execute(
                select(MiniApp)
                .where(MiniApp.publisher_id == publisher.id)
                .order_by(MiniApp.created_at.desc())
            )
        )
        .scalars()
        .unique()
        .all()
    )
    return MiniAppListResponse(
        items=[_mini_app_response(row) for row in rows], total=len(rows)
    )


@router.post(
    "/mini-apps",
    response_model=MiniAppResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a Mini App for moderation",
)
async def create_mini_app(
    payload: MiniAppCreateRequest,
    publisher: CurrentPublisherDep,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> MiniAppResponse:
    """The Kinz-ID key is issued immediately but only serves ads once approved."""
    mini_app = MiniApp(
        publisher_id=publisher.id,
        name=payload.name,
        url=payload.url,
        original_url=payload.original_url or payload.url,
        bot_id=payload.bot_id,
        bot_username=payload.bot_username,
        bot_token=payload.bot_token,
        category=payload.category,
        description=payload.description,
        kinz_key=generate_kinz_key(live=True),
        formats_enabled=payload.formats_enabled,
        status=MiniAppStatus.PENDING_MODERATION.value,
        submitted_ip_hash=ip_hash,
    )
    session.add(mini_app)
    await session.commit()
    await session.refresh(mini_app)
    return _mini_app_response(mini_app)


@router.get(
    "/mini-apps/{mini_app_id}/key",
    response_model=MiniAppKeyResponse,
    summary="Kinz-ID integration key and snippet",
)
async def mini_app_key(
    mini_app_id: uuid.UUID,
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> MiniAppKeyResponse:
    mini_app = await session.get(MiniApp, mini_app_id)
    if mini_app is None or mini_app.publisher_id != publisher.id:
        raise NotFoundError("Mini App not found.")

    snippet = (
        '<script src="%s/sdk/kinz.js" '
        'data-kinz-id="%s" async></script>'
        % (settings.API_BASE_URL, mini_app.kinz_key)
    )
    return MiniAppKeyResponse(
        id=str(mini_app.id),
        kinzKey=mini_app.kinz_key,
        snippet=snippet,
        docsUrl=f"{settings.PUBLIC_BASE_URL}/docs/sdk",
    )


@router.post(
    "/mini-apps/{mini_app_id}/suspend",
    response_model=MiniAppResponse,
    summary="Pause a Mini App without deleting it",
)
async def suspend_mini_app(
    mini_app_id: uuid.UUID,
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> MiniAppResponse:
    mini_app = await session.get(MiniApp, mini_app_id)
    if mini_app is None or mini_app.publisher_id != publisher.id:
        raise NotFoundError("Mini App not found.")
    if mini_app.status == MiniAppStatus.ARCHIVED.value:
        raise BusinessRuleError("Un-archive this Mini App before suspending it.")
    mini_app.status = MiniAppStatus.SUSPENDED.value
    await session.commit()
    await session.refresh(mini_app)
    return _mini_app_response(mini_app)


@router.post(
    "/mini-apps/{mini_app_id}/resume",
    response_model=MiniAppResponse,
    summary="Resume a suspended Mini App",
)
async def resume_mini_app(
    mini_app_id: uuid.UUID,
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> MiniAppResponse:
    mini_app = await session.get(MiniApp, mini_app_id)
    if mini_app is None or mini_app.publisher_id != publisher.id:
        raise NotFoundError("Mini App not found.")
    if mini_app.status != MiniAppStatus.SUSPENDED.value:
        raise BusinessRuleError("Only a suspended Mini App can be resumed.")
    mini_app.status = MiniAppStatus.ACTIVE.value if mini_app.approved_at else MiniAppStatus.PENDING_MODERATION.value
    await session.commit()
    await session.refresh(mini_app)
    return _mini_app_response(mini_app)


@router.post(
    "/mini-apps/{mini_app_id}/archive",
    response_model=MiniAppResponse,
    summary="Archive a Mini App (suspend + hide from the active list)",
)
async def archive_mini_app(
    mini_app_id: uuid.UUID,
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> MiniAppResponse:
    """Archiving never deletes anything — stats and payouts already earned
    stay intact. There is no un-archive, same as the channel flow above."""
    mini_app = await session.get(MiniApp, mini_app_id)
    if mini_app is None or mini_app.publisher_id != publisher.id:
        raise NotFoundError("Mini App not found.")
    mini_app.status = MiniAppStatus.ARCHIVED.value
    mini_app.archived_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(mini_app)
    return _mini_app_response(mini_app)


# --------------------------------------------------------------------------- #
# Withdrawals
# --------------------------------------------------------------------------- #
async def _withdrawal_eligibility(
    session: SessionDep, publisher
) -> tuple[bool, datetime | None, str | None]:
    """A publisher can only withdraw once their first channel has been live.

    The cooldown starts at the first channel approval, which prevents a fresh
    account from cashing out immediately after a single burst of traffic.
    """
    if publisher.first_channel_approved_at is None:
        approved_at = (
            await session.execute(
                select(func.min(Channel.approved_at)).where(
                    Channel.publisher_id == publisher.id,
                    Channel.approved_at.is_not(None),
                )
            )
        ).scalar_one_or_none()
        if approved_at is None:
            return False, None, (
                "You need at least one approved channel before requesting a withdrawal."
            )
        publisher.first_channel_approved_at = approved_at

    eligible_at = publisher.first_channel_approved_at + timedelta(
        hours=settings.WITHDRAWAL_COOLDOWN_HOURS
    )
    if datetime.now(UTC) < eligible_at:
        hours = int((eligible_at - datetime.now(UTC)).total_seconds() // 3600) + 1
        return False, eligible_at, (
            f"Withdrawals unlock {settings.WITHDRAWAL_COOLDOWN_HOURS} hours after your "
            f"first channel is approved. Available in about {hours} hours."
        )
    return True, eligible_at, None


@router.get(
    "/withdrawals",
    response_model=WithdrawalListResponse,
    summary="Withdrawal history and eligibility",
)
async def list_withdrawals(
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> WithdrawalListResponse:
    rows = (
        (
            await session.execute(
                select(Withdrawal)
                .where(Withdrawal.publisher_id == publisher.id)
                .order_by(Withdrawal.requested_at.desc())
            )
        )
        .scalars()
        .unique()
        .all()
    )
    eligible, eligible_at, reason = await _withdrawal_eligibility(session, publisher)
    await session.commit()

    return WithdrawalListResponse(
        items=[_withdrawal_response(row) for row in rows],
        total=len(rows),
        availableBalance=publisher.available_balance_usd,
        heldBalance=publisher.held_balance_usd,
        minimum=settings.MIN_WITHDRAWAL,
        eligible=eligible,
        eligibleAt=eligible_at,
        ineligibleReason=reason,
    )


@router.post(
    "/withdrawals",
    response_model=WithdrawalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request a payout in USDT on TON",
)
async def create_withdrawal(
    payload: WithdrawalCreateRequest,
    publisher: CurrentPublisherDep,
    session: SessionDep,
    ip_hash: ClientIPHashDep,
) -> WithdrawalResponse:
    eligible, _, reason = await _withdrawal_eligibility(session, publisher)
    if not eligible:
        raise WithdrawalCooldownError(reason or "Withdrawals are not available yet.")

    pending = (
        await session.execute(
            select(func.count())
            .select_from(Withdrawal)
            .where(
                Withdrawal.publisher_id == publisher.id,
                Withdrawal.status.in_(
                    [WithdrawalStatus.PENDING.value, WithdrawalStatus.APPROVED.value]
                ),
            )
        )
    ).scalar_one()
    if pending:
        raise ConflictError(
            "You already have a withdrawal in progress. Wait for it to be "
            "processed before requesting another."
        )

    if Decimal(publisher.available_balance_usd) < payload.amount:
        raise InsufficientBalanceError(
            "Your available balance does not cover this withdrawal amount."
        )

    withdrawal = Withdrawal(
        publisher_id=publisher.id,
        amount_usd=payload.amount,
        destination_address=payload.destination_address,
        memo_comment=payload.memo_comment or settings.DEFAULT_WITHDRAWAL_MEMO,
        requested_at=datetime.now(UTC),
        requested_ip_hash=ip_hash,
    )
    session.add(withdrawal)
    await session.flush()

    await billing_service.hold_withdrawal_funds(
        session, publisher=publisher, amount=payload.amount, reference_id=withdrawal.id
    )
    await session.commit()
    await session.refresh(withdrawal)
    return _withdrawal_response(withdrawal)


# --------------------------------------------------------------------------- #
# Stats
# --------------------------------------------------------------------------- #
@router.get("/stats", response_model=PublisherStatsResponse, summary="Dashboard stats")
async def stats(
    publisher: CurrentPublisherDep,
    session: SessionDep,
) -> PublisherStatsResponse:
    channel_ids = (
        (
            await session.execute(
                select(Channel.id).where(Channel.publisher_id == publisher.id)
            )
        )
        .scalars()
        .all()
    )
    mini_app_ids = (
        (
            await session.execute(
                select(MiniApp.id).where(MiniApp.publisher_id == publisher.id)
            )
        )
        .scalars()
        .all()
    )
    placement_ids = list(channel_ids) + list(mini_app_ids)

    daily: list[float] = []
    impressions_30 = clicks_30 = 0
    if placement_ids:
        since = datetime.now(UTC) - timedelta(days=30)
        rows = (
            await session.execute(
                select(
                    PlacementDailyStat.stat_date,
                    func.coalesce(func.sum(PlacementDailyStat.impressions), 0),
                    func.coalesce(func.sum(PlacementDailyStat.clicks), 0),
                )
                .where(
                    PlacementDailyStat.placement_id.in_(placement_ids),
                    PlacementDailyStat.stat_date >= since,
                )
                .group_by(PlacementDailyStat.stat_date)
                .order_by(PlacementDailyStat.stat_date)
            )
        ).all()
        impressions_30 = sum(int(row[1]) for row in rows)
        clicks_30 = sum(int(row[2]) for row in rows)
        daily = [float(row[1]) for row in rows]

    active_channels = (
        await session.execute(
            select(func.count())
            .select_from(Channel)
            .where(
                Channel.publisher_id == publisher.id,
                Channel.status.in_(
                    [ChannelStatus.ACTIVE.value, ChannelStatus.ACTIVE_BUILDING_TRUST.value]
                ),
            )
        )
    ).scalar_one()
    active_mini_apps = (
        await session.execute(
            select(func.count())
            .select_from(MiniApp)
            .where(
                MiniApp.publisher_id == publisher.id,
                MiniApp.status == MiniAppStatus.ACTIVE.value,
            )
        )
    ).scalar_one()

    return PublisherStatsResponse(
        availableBalance=publisher.available_balance_usd,
        heldBalance=publisher.held_balance_usd,
        lifetimeEarnings=publisher.lifetime_earnings_usd,
        impressions30=impressions_30,
        clicks30=clicks_30,
        activeChannels=int(active_channels or 0),
        activeMiniApps=int(active_mini_apps or 0),
        daily=daily,
    )

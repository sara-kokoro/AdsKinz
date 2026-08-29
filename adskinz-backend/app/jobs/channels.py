"""Jobs that maintain channel lifecycle and bot-administration state."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.bot.aiogram_bot import fetch_chat_photo_bytes, get_member_count, verify_bot_is_admin
from app.config import settings
from app.core.enums import ChannelStatus
from app.database import session_scope
from app.models.placements import Channel
from app.redis_client import cache_delete_pattern, get_redis
from app.services import email_service, upload_service

logger = logging.getLogger(__name__)

# The setting is intentionally optional for backward-compatible deployments.
BOT_ADMIN_GRACE_CHECKS = getattr(settings, "BOT_ADMIN_GRACE_CHECKS", 2)
_ADMIN_FAILURE_KEY = "channel_admin_failures"
_local_failure_counts: dict[str, int] = {}


async def _clear_admin_failures(channel_id: str) -> None:
    _local_failure_counts.pop(channel_id, None)
    redis = get_redis()
    if redis is None:
        return
    try:
        await redis.delete(settings.ns(_ADMIN_FAILURE_KEY, channel_id))
    except Exception:  # noqa: BLE001 - verification must continue without Redis
        logger.warning("channels.admin_failure_counter_clear_failed channel=%s", channel_id)


async def _increment_admin_failures(channel_id: str) -> int:
    redis = get_redis()
    if redis is not None:
        try:
            return int(await redis.incr(settings.ns(_ADMIN_FAILURE_KEY, channel_id)))
        except Exception:  # noqa: BLE001 - retain a process-local fallback
            logger.warning("channels.admin_failure_counter_increment_failed channel=%s", channel_id)

    _local_failure_counts[channel_id] = _local_failure_counts.get(channel_id, 0) + 1
    return _local_failure_counts[channel_id]


async def refresh_channel_subscribers() -> dict:
    """Re-read the live subscriber count from Telegram for every deliverable
    channel — the count is never left to the publisher's own declaration.

    Runs every minute; each channel is still only worth one Telegram call
    per run, so this stays well inside normal bot API limits even with a
    few hundred channels.
    """
    now = datetime.now(UTC)
    summary = {"channels_checked": 0, "updated": 0, "failed": 0, "logos_captured": 0}

    async with session_scope() as session:
        channels = (
            (
                await session.execute(
                    select(Channel).where(
                        Channel.status.in_(
                            [
                                ChannelStatus.APPROVED_NOT_STARTED.value,
                                ChannelStatus.ACTIVE_BUILDING_TRUST.value,
                                ChannelStatus.ACTIVE.value,
                            ]
                        ),
                        Channel.telegram_chat_id.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        summary["channels_checked"] = len(channels)

        for channel in channels:
            count, error = await get_member_count(channel.telegram_chat_id)
            if count is None:
                summary["failed"] += 1
                logger.warning(
                    "channels.subscriber_refresh_failed channel=%s error=%s", channel.id, error
                )
                continue
            channel.subscriber_count = count
            channel.subscriber_count_updated_at = now
            summary["updated"] += 1

            # Self-healing logo capture: a channel only pays for this once
            # it actually has one — cheap for the steady state, and retries
            # automatically for the rare channel where the bot couldn't
            # read the photo yet (e.g. it wasn't admin at submission time).
            if not channel.logo_url:
                try:
                    photo_bytes = await fetch_chat_photo_bytes(channel.telegram_chat_id)
                    if photo_bytes:
                        channel.logo_url = upload_service.upload_channel_logo_bytes(
                            publisher_id=channel.publisher_id, data=photo_bytes
                        )
                        summary["logos_captured"] += 1
                except Exception:  # noqa: BLE001 - a logo miss must not break the subscriber refresh
                    pass

    return summary


async def channel_trust_expiry() -> dict:
    """Persist channels that have completed the dynamically computed trust window."""
    now = datetime.now(UTC)
    trust_ended_before = now - timedelta(hours=settings.TRUST_WINDOW_HOURS)
    summary = {"channels_promoted": 0}

    async with session_scope() as session:
        channels = (
            (
                await session.execute(
                    select(Channel).where(
                        Channel.status == ChannelStatus.ACTIVE_BUILDING_TRUST.value,
                        Channel.started_at.is_not(None),
                        Channel.started_at <= trust_ended_before,
                    )
                )
            )
            .scalars()
            .all()
        )
        for channel in channels:
            channel.status = ChannelStatus.ACTIVE.value
        summary["channels_promoted"] = len(channels)

    if summary["channels_promoted"]:
        await cache_delete_pattern("adsel:*")
    return summary


async def bot_admin_check() -> dict:
    """Re-verify bot administration for every currently deliverable channel."""
    now = datetime.now(UTC)
    summary = {
        "channels_checked": 0,
        "verified": 0,
        "failed": 0,
        "suspended": 0,
        "publisher_notifications": 0,
    }
    notices: list[tuple[str, str, str]] = []

    async with session_scope() as session:
        channels = (
            (
                await session.execute(
                    select(Channel).where(
                        Channel.status.in_(
                            [
                                ChannelStatus.ACTIVE_BUILDING_TRUST.value,
                                ChannelStatus.ACTIVE.value,
                            ]
                        )
                    )
                )
            )
            .scalars()
            .unique()
            .all()
        )
        summary["channels_checked"] = len(channels)

        for channel in channels:
            target = channel.telegram_chat_id or channel.public_link
            is_admin, can_post, can_delete, error = await verify_bot_is_admin(target)
            verified = bool(is_admin and can_post and can_delete)
            channel.bot_admin_last_checked_at = now

            if verified:
                channel.bot_admin_verified = True
                await _clear_admin_failures(str(channel.id))
                summary["verified"] += 1
                continue

            channel.bot_admin_verified = False
            failures = await _increment_admin_failures(str(channel.id))
            summary["failed"] += 1
            details = error or "The bot is not an administrator with post and delete permissions."
            notices.append((channel.publisher.email, channel.name, details))

            if failures >= BOT_ADMIN_GRACE_CHECKS:
                channel.status = ChannelStatus.SUSPENDED.value
                channel.suspended_at = now
                channel.rejection_reason = (
                    f"@{settings.BOT_USERNAME} failed {failures} consecutive "
                    f"admin checks: {details}"
                )
                await _clear_admin_failures(str(channel.id))
                summary["suspended"] += 1

    for email, channel_name, details in notices:
        sent = await email_service.send_email(
            email,
            "AdsKinz — bot admin rights required",
            (
                f"@{settings.BOT_USERNAME} could not verify administrator rights for "
                f'"{channel_name}". Please restore its post and delete permissions. '
                f"Check detail: {details}"
            ),
        )
        summary["publisher_notifications"] += int(sent)

    if summary["failed"]:
        await cache_delete_pattern("adsel:*")
    return summary

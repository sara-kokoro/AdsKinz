"""Jobs that maintain channel lifecycle and bot-administration state."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.bot.aiogram_bot import fetch_chat_photo_bytes, get_member_count, resolve_chat, verify_bot_is_admin
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
    """Re-read the live subscriber count from Telegram for every visible
    channel — the count is never left to the publisher's own declaration.

    Also self-heals two things that can fail at submission time (a
    transient Telegram error, a flood-control hiccup): a channel whose chat
    couldn't be resolved yet (``telegram_chat_id`` still null) gets another
    resolution attempt here, and any channel still missing a logo gets
    another attempt to capture it. Both keep retrying every minute until
    they succeed, so a channel is never permanently stuck on its initial
    placeholder numbers.

    Runs every minute; each channel is still only worth one or two Telegram
    calls per run, so this stays well inside normal bot API limits even
    with a few hundred channels.
    """
    now = datetime.now(UTC)
    summary = {
        "channels_checked": 0,
        "updated": 0,
        "failed": 0,
        "logos_captured": 0,
        "chats_resolved": 0,
    }

    async with session_scope() as session:
        channels = (
            (
                await session.execute(
                    select(Channel).where(
                        Channel.status.in_(
                            [
                                ChannelStatus.PENDING_MODERATION.value,
                                ChannelStatus.APPROVED_NOT_STARTED.value,
                                ChannelStatus.ACTIVE_BUILDING_TRUST.value,
                                ChannelStatus.ACTIVE.value,
                            ]
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        summary["channels_checked"] = len(channels)

        for channel in channels:
            if channel.telegram_chat_id is None:
                # Initial resolution at submission time never landed — retry
                # it here instead of leaving the channel stuck forever.
                chat_id, username, members, error = await resolve_chat(channel.public_link)
                if chat_id is None:
                    summary["failed"] += 1
                    logger.warning(
                        "channels.chat_resolution_retry_failed channel=%s error=%s",
                        channel.id,
                        error,
                    )
                    continue
                channel.telegram_chat_id = chat_id
                channel.telegram_username = username
                summary["chats_resolved"] += 1
                if members is not None:
                    channel.subscriber_count = members
                    channel.subscriber_count_updated_at = now
                    summary["updated"] += 1
                try:
                    is_admin, can_post, can_delete, _ = await verify_bot_is_admin(chat_id)
                    channel.bot_admin_verified = bool(is_admin and can_post and can_delete)
                    channel.bot_admin_last_checked_at = now
                except Exception:  # noqa: BLE001 - a bot-status miss must not break the refresh
                    pass
            else:
                count, error = await get_member_count(channel.telegram_chat_id)
                if count is None:
                    # The lightweight call failed (flood control, transient
                    # error) — fall back to the heavier full resolution,
                    # which is what worked the first time this channel was
                    # ever counted, before giving up for this run.
                    _, _, fallback_members, fallback_error = await resolve_chat(channel.public_link)
                    if fallback_members is not None:
                        count = fallback_members
                    else:
                        summary["failed"] += 1
                        logger.warning(
                            "channels.subscriber_refresh_failed channel=%s error=%s fallback_error=%s",
                            channel.id, error, fallback_error,
                        )
                        continue
                channel.subscriber_count = count
                channel.subscriber_count_updated_at = now
                summary["updated"] += 1

            # Self-healing logo capture: a channel only pays for this once
            # it actually has one — cheap for the steady state, and retries
            # automatically for the rare channel where the bot couldn't
            # read the photo yet (e.g. it wasn't admin at submission time).
            if not channel.logo_url and channel.telegram_chat_id is not None:
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


async def remind_unstarted_channels() -> dict:
    """Nudge publishers who were approved but never pressed Start.

    A channel stuck in APPROVED_NOT_STARTED never enters the eligible pool
    (see ad_selection_service.eligible_channels) — it delivers zero ads and
    earns zero revenue, invisibly, for as long as the publisher forgets
    about it. Sends at most one reminder per approval, after a grace period,
    so a publisher who's still mid-setup isn't emailed immediately.
    """
    now = datetime.now(UTC)
    remind_after = now - timedelta(hours=settings.UNSTARTED_CHANNEL_REMINDER_HOURS)
    summary = {"channels_checked": 0, "reminders_sent": 0}

    async with session_scope() as session:
        channels = (
            (
                await session.execute(
                    select(Channel).where(
                        Channel.status == ChannelStatus.APPROVED_NOT_STARTED.value,
                        Channel.approved_at.is_not(None),
                        Channel.approved_at <= remind_after,
                        Channel.not_started_reminder_sent_at.is_(None),
                    )
                )
            )
            .scalars()
            .unique()
            .all()
        )
        summary["channels_checked"] = len(channels)

        for channel in channels:
            sent = await email_service.send_channel_not_started_reminder(
                channel.publisher.email, channel_name=channel.name
            )
            if sent:
                channel.not_started_reminder_sent_at = now
                summary["reminders_sent"] += 1

    return summary

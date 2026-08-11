"""Native Telegram-channel posting pipeline used by the scheduler job."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from app.bot.aiogram_bot import post_ad
from app.config import settings
from app.core.security import generate_tracking_id
from app.database import session_scope
from app.models.tracking import ScheduledPost, TrackingLink
from app.redis_client import incr_channel_daily_posts
from app.services import ad_selection_service

logger = logging.getLogger(__name__)


async def dispatch_posts(limit: int = 50) -> dict:
    """Select and publish at most ``limit`` channel-native AdsKinz posts."""
    summary = {
        "channels_considered": 0,
        "posts_created": 0,
        "posts_posted": 0,
        "errors": 0,
    }
    if limit <= 0:
        return summary

    async with session_scope() as session:
        channels = await ad_selection_service.eligible_channels(session)
        for channel in channels[:limit]:
            summary["channels_considered"] += 1
            campaign = await ad_selection_service.select_for_channel(session, channel)
            if campaign is None:
                continue

            text, button_label, language_served = await ad_selection_service.resolve_creative(
                session, campaign, channel.declared_language
            )
            tracking_id = generate_tracking_id()
            scheduled_post = ScheduledPost(
                campaign_id=campaign.id,
                channel_id=channel.id,
                telegram_chat_id=channel.telegram_chat_id,
                tracking_id=tracking_id,
                language_served=language_served,
            )
            session.add(scheduled_post)
            await session.flush()
            session.add(
                TrackingLink(
                    tracking_id=tracking_id,
                    campaign_id=campaign.id,
                    scheduled_post_id=scheduled_post.id,
                    placement_type="channel",
                    placement_id=channel.id,
                    destination_url=campaign.destination_url,
                )
            )
            summary["posts_created"] += 1

            message_id, error = await post_ad(
                channel.telegram_chat_id,
                text,
                button_label,
                settings.tracking_link(str(tracking_id)),
                image_url=campaign.image_url,
            )
            if error or message_id is None:
                scheduled_post.post_error = error or "Telegram did not return a message id."
                summary["errors"] += 1
                logger.warning(
                    "posting.failed channel=%s campaign=%s error=%s",
                    channel.id,
                    campaign.id,
                    scheduled_post.post_error,
                )
                continue

            posted_at = datetime.now(UTC)
            scheduled_post.telegram_message_id = message_id
            scheduled_post.posted_at = posted_at
            # Post lifetime is deliberately independent of campaign budget.
            scheduled_post.delete_at = posted_at + timedelta(hours=settings.POST_LIFETIME_HOURS)
            channel.last_ad_posted_at = posted_at
            await incr_channel_daily_posts(channel.id, posted_at.strftime("%Y-%m-%d"))
            summary["posts_posted"] += 1

    return summary

"""Jobs responsible for native Telegram post delivery and expiry."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.bot import aiogram_bot
from app.bot.poster import dispatch_posts
from app.core.enums import CampaignStatus
from app.database import session_scope
from app.models.campaigns import Campaign
from app.models.tracking import ScheduledPost

logger = logging.getLogger(__name__)


def _message_is_already_deleted(error: str | None) -> bool:
    """Recognise Telegram's variants of the harmless missing-message response."""
    text = (error or "").lower()
    return any(
        marker in text
        for marker in (
            "message to delete not found",
            "message not found",
            "message_id_invalid",
            "message identifier is not specified",
        )
    )


async def auto_delete_posts() -> dict:
    """Delete native posts whose fixed 24-hour lifetime has elapsed."""
    now = datetime.now(UTC)
    summary = {"due": 0, "deleted": 0, "already_deleted": 0, "failed": 0, "invalid": 0}

    async with session_scope() as session:
        posts = (
            (
                await session.execute(
                    select(ScheduledPost).where(
                        ScheduledPost.deleted.is_(False),
                        ScheduledPost.posted_at.is_not(None),
                        ScheduledPost.delete_at.is_not(None),
                        ScheduledPost.delete_at <= now,
                    )
                )
            )
            .scalars()
            .all()
        )
        summary["due"] = len(posts)

        for post in posts:
            if post.telegram_chat_id is None or post.telegram_message_id is None:
                post.delete_error = "Posted message is missing its Telegram chat or message id."
                summary["invalid"] += 1
                continue

            deleted, error = await aiogram_bot.delete_post(
                post.telegram_chat_id, post.telegram_message_id
            )
            # A post is deleted 24h after posting regardless of remaining campaign
            # budget — this job is fully independent of budget tracking.
            if deleted or _message_is_already_deleted(error):
                post.deleted = True
                post.deleted_at = now
                post.delete_error = None
                summary["deleted"] += 1
                if not deleted:
                    summary["already_deleted"] += 1
                continue

            post.delete_error = error or "Telegram did not confirm deletion."
            summary["failed"] += 1
            logger.warning(
                "posts.auto_delete_failed post=%s chat=%s message=%s error=%s",
                post.id,
                post.telegram_chat_id,
                post.telegram_message_id,
                post.delete_error,
            )

    return summary


async def expire_posts_for_inactive_campaigns() -> dict:
    """Pull every live post down the moment its campaign stops delivering.

    Independent from ``auto_delete_posts``' fixed 24h lifetime: that job
    removes a post 24h after it went up no matter what the campaign is
    doing. This one removes a post the instant its campaign leaves
    ``active`` — budget exhausted, paused, paused for insufficient balance,
    or rejected — even if that post is only minutes old and even if the
    campaign still has budget sitting unused elsewhere (a daily cap or an
    advertiser-side pause can stop delivery long before the total budget is
    spent). A campaign that becomes active again (top-up, unpause) starts
    clean: post_dispatch is free to place new posts through its normal
    channel rotation, it does not restore the ones removed here.
    """
    now = datetime.now(UTC)
    summary = {"due": 0, "deleted": 0, "already_deleted": 0, "failed": 0, "invalid": 0}

    async with session_scope() as session:
        posts = (
            (
                await session.execute(
                    select(ScheduledPost)
                    .join(Campaign, Campaign.id == ScheduledPost.campaign_id)
                    .where(
                        ScheduledPost.deleted.is_(False),
                        ScheduledPost.posted_at.is_not(None),
                        Campaign.status != CampaignStatus.ACTIVE.value,
                    )
                )
            )
            .scalars()
            .all()
        )
        summary["due"] = len(posts)

        for post in posts:
            if post.telegram_chat_id is None or post.telegram_message_id is None:
                post.delete_error = "Posted message is missing its Telegram chat or message id."
                summary["invalid"] += 1
                continue

            deleted, error = await aiogram_bot.delete_post(
                post.telegram_chat_id, post.telegram_message_id
            )
            if deleted or _message_is_already_deleted(error):
                post.deleted = True
                post.deleted_at = now
                post.delete_error = None
                summary["deleted"] += 1
                if not deleted:
                    summary["already_deleted"] += 1
                continue

            post.delete_error = error or "Telegram did not confirm deletion."
            summary["failed"] += 1
            logger.warning(
                "posts.campaign_stop_delete_failed post=%s chat=%s message=%s error=%s",
                post.id,
                post.telegram_chat_id,
                post.telegram_message_id,
                post.delete_error,
            )

    return summary


async def post_dispatch() -> dict:
    """Run the existing native-post selection and dispatch pipeline."""
    return await dispatch_posts()

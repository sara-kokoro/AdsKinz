"""Jobs responsible for native Telegram post delivery and expiry."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.bot import aiogram_bot
from app.bot.poster import dispatch_posts
from app.database import session_scope
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


async def post_dispatch() -> dict:
    """Run the existing native-post selection and dispatch pipeline."""
    return await dispatch_posts()

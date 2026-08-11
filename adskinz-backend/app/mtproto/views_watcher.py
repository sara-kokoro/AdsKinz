"""Batch Telegram channel view polling and delta-based impression billing.

Telegram reports cumulative message views. Billing always uses the DELTA between
consecutive snapshots, never that cumulative value, so restarting this watcher
cannot double-charge views already recorded before the restart.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select

from app.database import session_scope
from app.models.tracking import ScheduledPost, ViewSnapshot
from app.mtproto.client import FloodWait, start_client
from app.services import billing_service

logger = logging.getLogger(__name__)


async def poll_views() -> dict:
    """Poll active native posts by channel and charge only new verified views."""
    summary = {
        "posts_polled": 0,
        "views_billed": 0,
        "amount_charged": Decimal("0"),
        "errors": 0,
    }
    client = await start_client()
    if client is None:
        logger.info("views_watcher.skipped reason=mtproto_unavailable")
        return summary

    async with session_scope() as session:
        posts = (
            (
                await session.execute(
                    select(ScheduledPost).where(
                        ScheduledPost.deleted.is_(False),
                        ScheduledPost.posted_at.is_not(None),
                        ScheduledPost.telegram_message_id.is_not(None),
                        ScheduledPost.telegram_chat_id.is_not(None),
                    )
                )
            )
            .scalars()
            .unique()
            .all()
        )
        by_chat: dict[int, list[ScheduledPost]] = defaultdict(list)
        for post in posts:
            # The query guarantees this; the guard keeps type-checkers and future migrations safe.
            if post.telegram_chat_id is not None:
                by_chat[post.telegram_chat_id].append(post)

        for chat_id, channel_posts in by_chat.items():
            message_ids = [post.telegram_message_id for post in channel_posts if post.telegram_message_id]
            try:
                messages = await client.get_messages(chat_id, message_ids=message_ids)
            except FloodWait as exc:
                wait_seconds = int(getattr(exc, "value", 0) or 0)
                logger.warning("views_watcher.flood_wait chat=%s seconds=%s", chat_id, wait_seconds)
                await asyncio.sleep(wait_seconds)
                summary["errors"] += 1
                continue
            except Exception as exc:  # noqa: BLE001 - one inaccessible channel must not abort the job
                logger.warning("views_watcher.channel_failed chat=%s error=%s", chat_id, exc)
                summary["errors"] += 1
                continue

            if not isinstance(messages, list):
                messages = [messages]
            messages_by_id = {
                message.id: message
                for message in messages
                if message is not None and getattr(message, "id", None) is not None
            }

            for post in channel_posts:
                message = messages_by_id.get(post.telegram_message_id)
                if message is None:
                    continue
                cumulative_views = max(0, int(getattr(message, "views", 0) or 0))
                delta = max(0, cumulative_views - post.last_view_count)
                charged = Decimal("0")
                billed_units = 0

                if delta > 0:
                    amount = billing_service.impression_cost(post.campaign.cpm_bid, delta)
                    charge = await billing_service.charge_campaign(
                        session,
                        campaign=post.campaign,
                        amount=amount,
                        units=delta,
                        event_type="impression",
                        placement_type="channel",
                        placement_id=post.channel_id,
                    )
                    charged = charge.charged
                    billed_units = charge.billed_units
                    post.billed_views += billed_units
                    post.revenue_usd = billing_service.q6(post.revenue_usd + charged)
                    summary["views_billed"] += billed_units
                    summary["amount_charged"] += charged

                session.add(
                    ViewSnapshot(
                        scheduled_post_id=post.id,
                        view_count_cumulative=cumulative_views,
                        delta=delta,
                        billed_amount_usd=charged,
                    )
                )
                # Always move the checkpoint, including when a budget prevents a charge.
                post.last_view_count = cumulative_views
                summary["posts_polled"] += 1

    return summary

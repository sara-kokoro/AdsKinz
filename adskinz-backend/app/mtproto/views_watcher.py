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
        # Populated with one entry per channel that raised, so a caller (the
        # admin debug endpoint) can see *why* without needing host log
        # access. Most common cause: the MTProto account has never
        # joined/seen this chat, so Telegram can't resolve the peer for a
        # user-session get_messages call (bot tokens don't have this
        # restriction, which is why this only ever bites the view-billing
        # path, not posting).
        "channel_errors": [],
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
            except Exception as first_exc:  # noqa: BLE001 - may just need the peer resolved, try that before giving up
                # A normal Telegram user account (unlike the bot) can't call
                # get_messages() on a chat it has never seen — Telegram
                # rejects with PEER_ID_INVALID because it has no cached
                # peer/access_hash for it yet.
                #
                # For a PUBLIC channel this is fixed by simply resolving it
                # (get_chat by @username) — that alone caches the peer and
                # does NOT make this account a member. This matters at
                # scale: a Telegram account can only join a few hundred to a
                # few thousand chats total, so actually joining every
                # onboarded channel would hit that wall long before AdsKinz
                # does (see the 100k-channel goal) and looks like mass/bot
                # behaviour to Telegram. Only PRIVATE channels (invite link,
                # no @username) genuinely require joining, since there is no
                # username to resolve — for those, this does still join, as
                # a last resort, and only for that one channel.
                channel = channel_posts[0].channel
                username = (channel.telegram_username or "").lstrip("@")
                resolved = False

                if username:
                    try:
                        await client.get_chat(username)
                        resolved = True
                    except Exception as resolve_exc:  # noqa: BLE001 - fall through to the private-channel path
                        logger.warning(
                            "views_watcher.resolve_failed chat=%s username=%s error=%s",
                            chat_id, username, resolve_exc,
                        )
                if not resolved and not username and channel.public_link:
                    try:
                        await client.join_chat(channel.public_link)
                        resolved = True
                    except Exception as join_exc:  # noqa: BLE001 - fall through to reporting the original error
                        logger.warning(
                            "views_watcher.autojoin_failed chat=%s link=%s error=%s",
                            chat_id, channel.public_link, join_exc,
                        )
                if resolved:
                    try:
                        messages = await client.get_messages(chat_id, message_ids=message_ids)
                    except Exception as retry_exc:  # noqa: BLE001
                        summary["errors"] += 1
                        summary["channel_errors"].append(
                            {"chat_id": chat_id, "error": f"post-resolve retry failed: {retry_exc}"}
                        )
                        continue
                elif isinstance(first_exc, FloodWait):
                    wait_seconds = int(getattr(first_exc, "value", 0) or 0)
                    logger.warning("views_watcher.flood_wait chat=%s seconds=%s", chat_id, wait_seconds)
                    await asyncio.sleep(wait_seconds)
                    summary["errors"] += 1
                    summary["channel_errors"].append({"chat_id": chat_id, "error": f"FloodWait({wait_seconds}s)"})
                    continue
                else:
                    logger.warning("views_watcher.channel_failed chat=%s error=%s", chat_id, first_exc)
                    summary["errors"] += 1
                    summary["channel_errors"].append({"chat_id": chat_id, "error": str(first_exc)})
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

                try:
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
                except Exception as exc:  # noqa: BLE001 - one bad post must not block billing for the rest
                    await session.rollback()
                    logger.warning("views_watcher.billing_failed post=%s error=%s", post.id, exc)
                    summary["errors"] += 1
                    summary["channel_errors"].append({"post_id": str(post.id), "error": str(exc)})
                    continue

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

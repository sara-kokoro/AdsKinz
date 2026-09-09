"""Compare a sponsored post's views to its channel's neighboring organic posts.

A channel that pads *every* post equally already trips
``fraud_service.scan_channel_view_spikes`` (views vs. subscriber count). This
scan catches the narrower, sneakier case: a publisher who only orders bought
views for the AdsKinz post specifically (to inflate what advertisers pay
for) while leaving their own organic posts alone — so the sponsored post
looks wildly out of place against its own immediate neighbors even though
the channel's overall numbers seem plausible.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.database import session_scope
from app.models.tracking import ScheduledPost
from app.mtproto.client import FloodWait, start_client
from app.services import fraud_service

logger = logging.getLogger(__name__)

# How many messages to look at on each side of the sponsored post.
NEIGHBOR_WINDOW = 3
# Need at least this many resolved organic neighbors before trusting the
# comparison — a single reference point is too noisy to act on.
MIN_NEIGHBORS_RESOLVED = 2
# Sponsored views at or above this multiple of the organic neighbor average
# gets flagged.
NEIGHBOR_DEVIATION_MULTIPLIER = Decimal("3")
# Only look at posts old enough that their organic neighbors have had a fair
# chance to accumulate views too, so a very fresh ad isn't compared against
# under-counted neighbors and flagged for no reason.
MIN_POST_AGE_HOURS = 6
# Posts to check per run. Kept modest: this is one extra get_messages call
# per channel on top of what views_watcher already does every 15 minutes.
BATCH_LIMIT = 200


async def scan_post_neighbors() -> dict:
    """For a batch of not-yet-checked posts, compare their view count to the
    few organic posts immediately before and after them on the same channel.

    Peer resolution (public channel lookup, or joining a private one) is
    intentionally NOT re-implemented here: views_watcher.poll_views already
    runs every 15 minutes and resolves/joins as needed as a side effect, so
    by the time a post is >= MIN_POST_AGE_HOURS old its channel's peer is
    already cached in this same MTProto session. If a channel's peer still
    fails to resolve here, it's logged and skipped for this run rather than
    duplicating that fallback logic a second time.
    """
    summary = {"posts_checked": 0, "flagged": 0, "errors": 0}
    client = await start_client()
    if client is None:
        logger.info("neighbor_check.skipped reason=mtproto_unavailable")
        return summary

    cutoff = datetime.now(UTC) - timedelta(hours=MIN_POST_AGE_HOURS)

    async with session_scope() as session:
        posts = (
            (
                await session.execute(
                    select(ScheduledPost)
                    .where(
                        ScheduledPost.deleted.is_(False),
                        ScheduledPost.posted_at.is_not(None),
                        ScheduledPost.posted_at <= cutoff,
                        ScheduledPost.telegram_message_id.is_not(None),
                        ScheduledPost.telegram_chat_id.is_not(None),
                        ScheduledPost.neighbor_checked_at.is_(None),
                    )
                    .limit(BATCH_LIMIT)
                )
            )
            .scalars()
            .unique()
            .all()
        )

        by_chat: dict[int, list[ScheduledPost]] = defaultdict(list)
        for post in posts:
            if post.telegram_chat_id is not None:
                by_chat[post.telegram_chat_id].append(post)

        for chat_id, chat_posts in by_chat.items():
            ad_ids = {post.telegram_message_id for post in chat_posts}
            wanted_ids: set[int] = set()
            for post in chat_posts:
                mid = post.telegram_message_id
                for offset in range(1, NEIGHBOR_WINDOW + 1):
                    wanted_ids.add(mid - offset)
                    wanted_ids.add(mid + offset)
            # Never let one sponsored post's inflated views count as another
            # sponsored post's "organic" neighbor.
            wanted_ids -= ad_ids
            wanted_ids = {i for i in wanted_ids if i > 0}

            try:
                messages = await client.get_messages(chat_id, message_ids=sorted(wanted_ids))
            except FloodWait as flood:
                wait_seconds = int(getattr(flood, "value", 0) or 0)
                logger.warning("neighbor_check.flood_wait chat=%s seconds=%s", chat_id, wait_seconds)
                summary["errors"] += 1
                continue
            except Exception as exc:  # noqa: BLE001 - one channel's peer issue must not block the batch
                logger.warning("neighbor_check.channel_failed chat=%s error=%s", chat_id, exc)
                summary["errors"] += 1
                continue

            if not isinstance(messages, list):
                messages = [messages]
            views_by_id = {
                m.id: max(0, int(getattr(m, "views", 0) or 0))
                for m in messages
                if m is not None and getattr(m, "id", None) is not None
            }

            for post in chat_posts:
                mid = post.telegram_message_id
                neighbor_ids = [mid - o for o in range(1, NEIGHBOR_WINDOW + 1)] + [
                    mid + o for o in range(1, NEIGHBOR_WINDOW + 1)
                ]
                neighbor_views = [
                    views_by_id[i] for i in neighbor_ids if views_by_id.get(i, 0) > 0
                ]

                post.neighbor_checked_at = datetime.now(UTC)
                summary["posts_checked"] += 1

                if len(neighbor_views) < MIN_NEIGHBORS_RESOLVED:
                    continue  # too little organic reference data to act on

                organic_avg = sum(neighbor_views) / len(neighbor_views)
                sponsored_views = post.last_view_count
                if organic_avg <= 0 or sponsored_views < organic_avg * float(NEIGHBOR_DEVIATION_MULTIPLIER):
                    continue

                channel = post.channel
                await fraud_service.record_anomaly(
                    session,
                    kind="channel",
                    subject_id=post.channel_id,
                    subject_label=channel.name if channel else str(post.channel_id),
                    reason=(
                        f"Sponsored post views ({sponsored_views}) are "
                        f"{sponsored_views / organic_avg:.1f}x the {len(neighbor_views)} "
                        f"neighboring organic posts on this channel ({organic_avg:.0f} avg) — "
                        f"consistent with a bought-views order placed on this post specifically"
                    ),
                    score=Decimal("0.85"),
                    details={
                        "scheduled_post_id": str(post.id),
                        "tracking_id": post.tracking_id,
                        "sponsored_views": sponsored_views,
                        "organic_neighbor_avg": round(organic_avg, 1),
                        "neighbors_sampled": len(neighbor_views),
                    },
                )
                summary["flagged"] += 1

    return summary

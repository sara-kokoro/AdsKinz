"""Job wrapper for MTProto view polling."""

from __future__ import annotations

from app.mtproto.neighbor_check import scan_post_neighbors
from app.mtproto.views_watcher import poll_views


async def views_polling() -> dict:
    """Poll cumulative Telegram post views and bill only their deltas."""
    return await poll_views()


async def neighbor_fraud_check() -> dict:
    """Compare sponsored posts to their channel's neighboring organic posts."""
    return await scan_post_neighbors()

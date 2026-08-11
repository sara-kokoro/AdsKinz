"""Job wrapper for MTProto view polling."""

from __future__ import annotations

from app.mtproto.views_watcher import poll_views


async def views_polling() -> dict:
    """Poll cumulative Telegram post views and bill only their deltas."""
    return await poll_views()

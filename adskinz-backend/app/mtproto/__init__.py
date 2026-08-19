"""Read-only Kurigram integration for Telegram view measurements."""

from app.mtproto.client import (
    get_client,
    is_configured,
    start_client,
    start_client_background,
    stop_client,
)
from app.mtproto.views_watcher import poll_views

__all__ = [
    "get_client",
    "is_configured",
    "poll_views",
    "start_client",
    "start_client_background",
    "stop_client",
]

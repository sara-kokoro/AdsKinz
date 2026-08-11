"""Telegram Bot API integration."""

from app.bot.aiogram_bot import (
    delete_post,
    get_bot,
    get_dispatcher,
    post_ad,
    start_bot,
    stop_bot,
)

__all__ = ["delete_post", "get_bot", "get_dispatcher", "post_ad", "start_bot", "stop_bot"]

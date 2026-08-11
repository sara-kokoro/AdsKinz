"""Aiogram handler registration."""

from aiogram import Dispatcher

from app.bot.handlers.channel_events import router as channel_events_router
from app.bot.handlers.start import router as start_router
from app.bot.handlers.verify import router as verify_router


def register_handlers(dp: Dispatcher) -> None:
    """Install every AdsKinz router exactly once on a new dispatcher."""
    dp.include_router(start_router)
    dp.include_router(verify_router)
    dp.include_router(channel_events_router)


__all__ = ["register_handlers"]

"""Lazy aiogram bot lifecycle and Telegram helpers."""

from __future__ import annotations

import asyncio
import html
import logging
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import (
    ChatMemberAdministrator,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from app.config import settings

logger = logging.getLogger(__name__)

_bot: Bot | None = None
_dispatcher: Dispatcher | None = None
_polling_task: asyncio.Task[None] | None = None


def get_bot() -> Bot:
    """Return the process-wide aiogram bot, creating it only when needed."""
    global _bot
    if _bot is None:
        _bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    return _bot


def get_dispatcher() -> Dispatcher:
    """Return the process-wide dispatcher with all application handlers registered."""
    global _dispatcher
    if _dispatcher is None:
        from app.bot.handlers import register_handlers

        _dispatcher = Dispatcher()
        register_handlers(_dispatcher)
    return _dispatcher


async def _poll() -> None:
    try:
        await get_dispatcher().start_polling(get_bot())
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001 - Telegram must not take down the API process
        logger.exception("bot.polling_failed")


async def start_bot() -> None:
    """Start long polling in the background when Telegram bot delivery is enabled."""
    global _polling_task
    if not settings.ENABLE_BOT:
        logger.info("bot.disabled")
        return
    if not settings.BOT_TOKEN:
        logger.warning("bot.disabled reason=missing_token")
        return
    if _polling_task is not None and not _polling_task.done():
        return

    _polling_task = asyncio.create_task(_poll(), name="adskinz-telegram-bot-polling")
    logger.info("bot.polling_started")


async def stop_bot() -> None:
    """Stop polling and close the shared bot HTTP session."""
    global _polling_task
    if _polling_task is not None:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
        _polling_task = None

    if _bot is not None:
        await _bot.session.close()
    logger.info("bot.stopped")


async def verify_bot_is_admin(chat_id_or_username: int | str) -> tuple[bool, bool, bool, str | None]:
    """Return the bot's admin and posting/deletion permissions in a Telegram chat."""
    try:
        bot = get_bot()
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id_or_username, me.id)
    except (TelegramForbiddenError, TelegramBadRequest) as exc:
        return False, False, False, str(exc)
    except Exception as exc:  # noqa: BLE001 - Telegram/network failures are user-visible checks
        logger.warning("bot.admin_check_failed chat=%s error=%s", chat_id_or_username, exc)
        return False, False, False, str(exc)

    if not isinstance(member, ChatMemberAdministrator):
        return False, False, False, None
    return (
        True,
        bool(member.can_post_messages),
        bool(member.can_delete_messages),
        None,
    )


def _normalise_public_chat(value: str) -> str:
    candidate = (value or "").strip()
    if candidate.startswith("@"):
        return candidate
    parsed = urlparse(candidate)
    if parsed.scheme and parsed.netloc.lower() in {"t.me", "www.t.me", "telegram.me", "www.telegram.me"}:
        username = parsed.path.strip("/").split("/", 1)[0]
        return f"@{username}" if username else ""
    return f"@{candidate.lstrip('@')}" if candidate else ""


async def get_member_count(chat_id_or_username: int | str) -> tuple[int | None, str | None]:
    """Lightweight subscriber-count read for an already-known chat.

    Unlike :func:`resolve_chat`, this skips ``get_chat`` and only asks for
    the member count — used by the periodic refresh job so it stays cheap
    even when it runs across every live channel.
    """
    try:
        bot = get_bot()
        count = await bot.get_chat_member_count(chat_id_or_username)
    except TelegramRetryAfter as exc:
        # Flood control: log the exact wait Telegram asked for. The
        # refresh job just retries next minute; the error is annotated so
        # it's obvious in logs why a channel's count is momentarily stale,
        # instead of looking like a silent permanent failure.
        logger.warning(
            "bot.member_count_flood_wait chat=%s retry_after=%s", chat_id_or_username, exc.retry_after
        )
        return None, f"flood_wait:{exc.retry_after}s"
    except (TelegramForbiddenError, TelegramBadRequest) as exc:
        logger.warning(
            "bot.member_count_failed chat=%s error_type=%s error=%s",
            chat_id_or_username, type(exc).__name__, exc,
        )
        return None, str(exc)
    except Exception as exc:  # noqa: BLE001 - Telegram/network failures must be reported gracefully
        logger.warning(
            "bot.member_count_failed chat=%s error_type=%s error=%s",
            chat_id_or_username, type(exc).__name__, exc,
        )
        return None, str(exc)
    return count, None


async def fetch_chat_photo_bytes(chat_id: int | str) -> bytes | None:
    """Download a channel's current profile photo straight from Telegram.

    Channel photos are public (anyone in the channel already sees them), so
    this is used to auto-populate the channel's logo — the publisher never
    has to upload anything themselves.
    """
    try:
        bot = get_bot()
        chat = await bot.get_chat(chat_id)
        if not chat.photo:
            return None
        file = await bot.get_file(chat.photo.big_file_id)
        buf = await bot.download_file(file.file_path)
        return buf.read() if buf else None
    except (TelegramForbiddenError, TelegramBadRequest) as exc:
        logger.info("bot.chat_photo_unavailable chat=%s error=%s", chat_id, exc)
        return None
    except Exception as exc:  # noqa: BLE001 - Telegram/network failures must be reported gracefully
        logger.warning("bot.chat_photo_failed chat=%s error=%s", chat_id, exc)
        return None


async def resolve_chat(public_link_or_username: str) -> tuple[int | None, str | None, int | None, str | None]:
    """Resolve a public Telegram link or username and return its chat metadata."""
    chat_ref = _normalise_public_chat(public_link_or_username)
    if not chat_ref:
        return None, None, None, "A public Telegram link or username is required."

    try:
        bot = get_bot()
        chat = await bot.get_chat(chat_ref)
        member_count = await bot.get_chat_member_count(chat.id)
    except (TelegramForbiddenError, TelegramBadRequest) as exc:
        return None, None, None, str(exc)
    except Exception as exc:  # noqa: BLE001 - Telegram/network failures must be reported gracefully
        logger.warning("bot.chat_resolution_failed chat=%s error=%s", chat_ref, exc)
        return None, None, None, str(exc)

    username = f"@{chat.username}" if chat.username else None
    return chat.id, username, member_count, None


async def post_ad(
    chat_id: int | str,
    text: str,
    button_label: str,
    tracking_url: str,
    image_url: str | None = None,
) -> tuple[int | None, str | None]:
    """Publish one escaped native ad with a single tracked call-to-action button."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=button_label, url=tracking_url)]]
    )
    try:
        bot = get_bot()
        safe_text = html.escape(text)
        if image_url:
            message = await bot.send_photo(
                chat_id=chat_id,
                photo=image_url,
                caption=safe_text,
                reply_markup=keyboard,
            )
        else:
            message = await bot.send_message(
                chat_id=chat_id,
                text=safe_text,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        return message.message_id, None
    except (TelegramForbiddenError, TelegramBadRequest) as exc:
        return None, str(exc)
    except Exception as exc:  # noqa: BLE001 - posting failures are persisted by the scheduler
        logger.warning("bot.post_failed chat=%s error=%s", chat_id, exc)
        return None, str(exc)


async def delete_post(chat_id: int | str, message_id: int) -> tuple[bool, str | None]:
    """Delete a previously posted native ad."""
    try:
        await get_bot().delete_message(chat_id=chat_id, message_id=message_id)
        return True, None
    except (TelegramForbiddenError, TelegramBadRequest) as exc:
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001 - cleanup jobs persist the error for later retry
        logger.warning("bot.delete_failed chat=%s message=%s error=%s", chat_id, message_id, exc)
        return False, str(exc)

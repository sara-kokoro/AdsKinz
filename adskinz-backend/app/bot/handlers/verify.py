"""Manual admin-rights verification command."""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, or_, select

from app.bot.aiogram_bot import resolve_chat, verify_bot_is_admin
from app.database import session_scope
from app.models.placements import Channel

router = Router(name="verify")


async def _persist_verification(chat_id: int, username: str | None, verified: bool) -> None:
    variants = []
    if username:
        clean = username.lstrip("@")
        variants = [username, clean, f"https://t.me/{clean}", f"https://t.me/{clean}/"]
    async with session_scope() as session:
        clauses = [Channel.telegram_chat_id == chat_id]
        if username:
            clauses.extend(
                [
                    func.lower(Channel.telegram_username).in_(
                        [username.lower(), username.lstrip("@").lower()]
                    ),
                    func.lower(Channel.public_link).in_([value.lower() for value in variants]),
                ]
            )
        channel = (
            await session.execute(select(Channel).where(or_(*clauses)).limit(1))
        ).scalar_one_or_none()
        if channel is not None:
            channel.telegram_chat_id = chat_id
            channel.bot_admin_verified = verified
            channel.bot_admin_last_checked_at = datetime.now(UTC)
            if username:
                channel.telegram_username = username


@router.message(Command("verify"))
async def verify_command(message: Message) -> None:
    """Check bot administration status in this channel or a supplied public channel."""
    username: str | None = None
    if message.chat.type == ChatType.CHANNEL:
        chat_id = message.chat.id
        username = f"@{message.chat.username}" if message.chat.username else None
    else:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("In a direct message, use /verify @your_channel or its public t.me link.")
            return
        chat_id, username, _, error = await resolve_chat(parts[1])
        if error or chat_id is None:
            await message.answer(f"I could not resolve that channel: {error or 'unknown error'}")
            return

    is_admin, can_post, can_delete, error = await verify_bot_is_admin(chat_id)
    if error:
        await message.answer(f"I could not check the bot permissions: {error}")
        return

    await _persist_verification(chat_id, username, is_admin)
    if is_admin and can_post and can_delete:
        await message.answer("Verified: the bot is an admin and can post and delete AdsKinz ads.")
    elif is_admin:
        await message.answer(
            "The bot is an admin, but it needs permission to post messages and delete messages. "
            f"Post: {'yes' if can_post else 'no'}; delete: {'yes' if can_delete else 'no'}."
        )
    else:
        await message.answer("The bot is not an administrator of this channel. Please promote it and try again.")

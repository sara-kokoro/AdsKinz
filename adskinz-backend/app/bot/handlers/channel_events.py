"""Keep persisted channel admin verification in sync with Telegram updates."""

from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.types import ChatMemberAdministrator, ChatMemberUpdated
from sqlalchemy import func, or_, select

from app.core.enums import ChannelStatus
from app.database import session_scope
from app.models.placements import Channel
from app.services import moderation_service

router = Router(name="channel_events")


def _public_link_variants(username: str | None) -> list[str]:
    if not username:
        return []
    clean = username.lstrip("@")
    return [
        clean,
        f"@{clean}",
        f"https://t.me/{clean}",
        f"https://t.me/{clean}/",
    ]


async def _find_channel(session, event: ChatMemberUpdated) -> Channel | None:
    username = event.chat.username
    clauses = [Channel.telegram_chat_id == event.chat.id]
    variants = _public_link_variants(username)
    if username:
        clauses.append(
            func.lower(Channel.telegram_username).in_(
                [username.lower(), f"@{username.lower()}"]
            )
        )
    if variants:
        clauses.append(func.lower(Channel.public_link).in_([value.lower() for value in variants]))

    return (
        await session.execute(select(Channel).where(or_(*clauses)).limit(1))
    ).scalar_one_or_none()


@router.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated) -> None:
    """Record promotion/demotion of this bot in tracked public channels."""
    if event.chat.type != ChatType.CHANNEL:
        return

    new_member = event.new_chat_member
    promoted = isinstance(new_member, ChatMemberAdministrator)
    # "Administrator" alone is not enough: without can_post_messages and
    # can_delete_messages, Telegram will reject every AdsKinz post and the
    # channel would otherwise sit marked as verified while never actually
    # delivering an ad.
    can_serve_ads = promoted and bool(new_member.can_post_messages) and bool(
        new_member.can_delete_messages
    )
    now = datetime.now(UTC)
    async with session_scope() as session:
        channel = await _find_channel(session, event)
        if channel is None:
            return

        channel.bot_admin_last_checked_at = now
        if can_serve_ads:
            channel.bot_admin_verified = True
            channel.telegram_chat_id = event.chat.id
            if event.chat.username:
                channel.telegram_username = f"@{event.chat.username}"
            return

        channel.bot_admin_verified = False
        if channel.status in {
            ChannelStatus.ACTIVE.value,
            ChannelStatus.ACTIVE_BUILDING_TRUST.value,
        }:
            await moderation_service.suspend_channel(
                session,
                channel,
                reason="AdsKinz bot was removed or demoted from channel administrator.",
            )

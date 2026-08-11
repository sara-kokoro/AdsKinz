"""Welcome and help commands."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import settings

router = Router(name="start")


def _dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Open AdsKinz", url=settings.PUBLIC_BASE_URL)],
        ]
    )


@router.message(Command("start"))
async def start_command(message: Message) -> None:
    await message.answer(
        "Welcome to AdsKinz. Advertisers create campaigns and pay for verified "
        "delivery; publishers add Telegram channels and earn from their views.\n\n"
        "Open the dashboard to get started.",
        reply_markup=_dashboard_keyboard(),
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "AdsKinz connects advertisers with Telegram channel publishers. "
        "Advertisers create native-post campaigns, while publishers register a "
        "channel, add this bot as admin, and earn from delivered views.\n\n"
        "Use /verify in a channel to check the bot permissions.",
        reply_markup=_dashboard_keyboard(),
    )

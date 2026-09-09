"""Welcome and help commands."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import settings

router = Router(name="start")

_WELCOME_PHOTO = "https://i.ibb.co/nMJt2B4r/uploaded-image.jpg"
_WELCOME_CAPTION = (
    '<blockquote><tg-emoji emoji-id="6008263495932448198">👋</tg-emoji> '
    "Welcome to <b>AdsKinz!</b></blockquote>\n\n"
    "Your all-in-one solution for <b>advertising and monetization on Telegram</b>. "
    '<tg-emoji emoji-id="5823645868607151256">🚀</tg-emoji>\n\n'
    "Whether you want to <b>promote your project, monetize your audience"
    '<tg-emoji emoji-id="5990147899403539264">💰</tg-emoji></b>, or <b>grow your reach,</b> '
    "AdsKinz is here to help.\n\n"
    '<tg-emoji emoji-id="4911290047799495551">⤵️</tg-emoji> '
    "<b>Explore the menu below to get started!</b>"
)


def _dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Open AdsKinz", url=settings.PUBLIC_BASE_URL, style="primary")],
        ]
    )


@router.message(Command("start"))
async def start_command(message: Message) -> None:
    await message.answer_photo(
        photo=_WELCOME_PHOTO,
        caption=_WELCOME_CAPTION,
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

from __future__ import annotations

from typing import Optional

from motor.core import AgnosticDatabase
from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.core.config import get_settings
from app.database.repositories import chats as chat_repo
from app.services import captcha, moderation
from app.services import permissions as perms

CAPTCHA_FOOTER = "Time's up for this verification.\nYou can rejoin to try again."


def _buttons(options: list[int], timeout: int) -> InlineKeyboardMarkup:
    def row(items: list[int]) -> list[InlineKeyboardButton]:
        return [InlineKeyboardButton(str(o), callback_data=f"cap:{o}") for o in items]

    return InlineKeyboardMarkup([row(options[0:2]), row(options[2:4])])


async def start_captcha(
    client: Client,
    db: AgnosticDatabase,
    chat_id: int,
    user: object,
    timeout: Optional[int] = None,
) -> Optional[Message]:
    """Restrict a new member and send them a math CAPTCHA."""
    if getattr(user, "is_bot", False):
        return None

    settings = await chat_repo.get_chat_settings(db, chat_id)
    timeout = timeout or settings.captcha_timeout

    question, answer, options = captcha.generate_challenge()
    await captcha.create_session(chat_id, user.id, question, answer, timeout)

    if await perms.can_restrict(client, chat_id):
        try:
            await client.restrict_chat_member(
                chat_id, user.id, moderation.MUTE_PERMISSIONS
            )
        except Exception:
            pass

    mention = getattr(user, "mention", None) or getattr(user, "first_name", str(getattr(user, "id", "?")))
    return await client.send_message(
        chat_id,
        f"🛡 Welcome {mention}!\n\n"
        "Please verify that you're human.\n\n"
        f"**Solve:**\n\n`{question}`\n\n"
        f"⏳ You have **{timeout}s** to answer. Limited attempts.",
        reply_markup=_buttons(options, timeout),
    )
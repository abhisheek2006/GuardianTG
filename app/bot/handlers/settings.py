from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message

from app.bot.decorators import with_rate_limit
from app.bot.filters import is_approved
from app.bot.keyboards import settings_keyboard
from app.bot.utils import is_group
from app.database import session as db_session
from app.database.repositories import chats as chat_repo
from app.services import permissions as perms


@Client.on_message(filters.command("settings") & is_approved)
@with_rate_limit()
async def settings_command(client: Client, message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    is_admin = await perms.is_chat_admin(client, message.chat.id, user_id)

    db = db_session.get_db()
    settings = await chat_repo.get_chat_settings(db, message.chat.id)

    header = "🛡 **Security Settings**\n\n"
    lines = [
        f"Anti-Spam:       {'🟢 ON' if settings.antispam_enabled else '🔴 OFF'}",
        f"Anti-Flood:      {'🟢 ON' if settings.antiflood_enabled else '🔴 OFF'}",
        f"Anti-Link:       {'🟢 ON' if settings.antilink_enabled else '🔴 OFF'}",
        f"Anti-Raid:       {'🟢 ON' if settings.antiraid_enabled else '🔴 OFF'}",
        f"CAPTCHA:         {'🟢 ON' if settings.captcha_enabled else '🔴 OFF'}",
        f"Anti-Bot:        {'🟢 ON' if settings.antibot_enabled else '🔴 OFF'}",
        f"Profanity:       {'🟢 ON' if settings.profanity_enabled else '🔴 OFF'}",
        f"Welcome:         {'🟢 ON' if settings.welcome_enabled else '🔴 OFF'}",
        f"Logging:         {'🟢 ON' if settings.log_enabled else '🔴 OFF'}",
    ]

    if is_admin:
        await message.reply_text(
            header + "\n".join(lines) + "\n\nTap a button to toggle.",
            reply_markup=settings_keyboard(settings),
        )
    else:
        await message.reply_text(
            header + "\n".join(lines) + "\n\n*Only administrators can modify settings.*"
        )
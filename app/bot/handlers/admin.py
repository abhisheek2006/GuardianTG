from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message

from app.bot.decorators import require_chat_admin, with_rate_limit
from app.bot.filters import group_approved
from app.bot.keyboards import admin_panel_keyboard
from app.bot.utils import is_group


@Client.on_message(filters.command("admin") & group_approved)
@require_chat_admin
@with_rate_limit()
async def admin_command(client: Client, message: Message) -> None:
    await message.reply_text(
        "🛡 **Admin Panel**\n\nSelect a section to manage.",
        reply_markup=admin_panel_keyboard(),
    )
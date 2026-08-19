from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message

from app.bot.keyboards import start_keyboard
from app.bot.utils import is_group


@Client.on_message(filters.command("start") & filters.private)
async def start_private(client: Client, message: Message) -> None:
    me = await client.get_me()
    text = (
        f"🛡 **{me.first_name}**\n\n"
        f"Advanced Telegram Group Security Bot.\n\n"
        f"Protect your community from:\n\n"
        f"🚫 Spam\n"
        f"🔗 Malicious links\n"
        f"🤖 Bot accounts\n"
        f"💥 Raids\n"
        f"📨 Flooding\n"
        f"🧪 Suspicious users\n"
        f"⚠️ Toxic content\n\n"
        f"Add me to your group as an administrator to get started."
    )
    await message.reply_text(text, reply_markup=start_keyboard(me.username or ""))


@Client.on_message(filters.command("start") & filters.group)
async def start_group(client: Client, message: Message) -> None:
    await message.reply_text(
        "🛡 **GuardianTG is protecting this group.**\n\n"
        "Use /help to see available commands. "
        "Administrators can manage security with /settings and /admin."
    )
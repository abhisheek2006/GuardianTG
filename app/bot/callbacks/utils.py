from __future__ import annotations

from pyrogram import Client
from pyrogram.types import CallbackQuery

from app.services import permissions as perms


async def require_callback_admin(client: Client, callback: CallbackQuery) -> bool:
    """Verify the callback sender is a chat admin. Returns True when allowed."""
    chat = callback.message.chat
    user_id = callback.from_user.id if callback.from_user else 0
    if not user_id:
        await callback.answer("🚫 Could not verify your identity.", show_alert=True)
        return False
    if not await perms.is_chat_admin(client, chat.id, user_id):
        await callback.answer("🚫 Only administrators can do this.", show_alert=True)
        return False
    return True
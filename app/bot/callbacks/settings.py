from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from app.bot.callbacks.utils import require_callback_admin
from app.bot.keyboards import advanced_keyboard, settings_keyboard
from app.database import session as db_session
from app.database.repositories import chats as chat_repo
from app.services import eventlog
from app.services import permissions as perms

TOGGLE_LABELS = {
    "antispam": "Anti-Spam",
    "antiflood": "Anti-Flood",
    "antilink": "Anti-Link",
    "antiraid": "Anti-Raid",
    "captcha": "CAPTCHA",
    "antibot": "Anti-Bot",
    "profanity": "Profanity",
    "welcome": "Welcome",
    "goodbye": "Goodbye",
    "log": "Logging",
}


@Client.on_callback_query(filters.regex(r"^set:"), group=0)
async def settings_callback(client: Client, callback: CallbackQuery) -> None:
    chat = callback.message.chat
    if chat.type in ("group", "supergroup") and not await require_callback_admin(client, callback):
        return

    action = callback.data.split(":", 1)[1]
    db = db_session.get_db()

    if action == "close":
        try:
            await callback.message.delete()
        except Exception:
            await callback.message.edit_text("Closed.")
        await callback.answer()
        return

    if action == "main":
        settings = await chat_repo.get_chat_settings(db, chat.id)
        await callback.message.edit_text(
            "🛡 **Security Settings**\n\nTap a button to toggle.",
            reply_markup=settings_keyboard(settings),
        )
        await callback.answer()
        return

    if action == "advanced":
        await callback.message.edit_text(
            "⚙️ **Advanced Settings**\n\nConfigure behaviours below.",
            reply_markup=advanced_keyboard(chat.id),
        )
        await callback.answer()
        return

    if action in TOGGLE_LABELS:
        settings = await chat_repo.get_chat_settings(db, chat.id)
        new_value = not settings.__getattribute__(action + "_enabled")
        await chat_repo.update_chat_setting(db, chat.id, action + "_enabled", new_value)
        label = TOGGLE_LABELS[action]
        icon = "🟢 ON" if new_value else "🔴 OFF"
        await eventlog.persist_and_notify(
            client, db, chat.id, "settings_changed",
            admin_id=callback.from_user.id,
            details={label: icon},
        )
        settings = await chat_repo.get_chat_settings(db, chat.id)
        await callback.message.edit_text(
            "🛡 **Security Settings**\n\nTap a button to toggle.",
            reply_markup=settings_keyboard(settings),
        )
        await callback.answer(f"{label}: {icon}")
        return

    await callback.answer("Unknown action", show_alert=True)
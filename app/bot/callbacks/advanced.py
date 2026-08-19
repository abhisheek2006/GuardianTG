from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.utils import require_callback_admin
from app.database import session as db_session
from app.database.repositories import chats as chat_repo
from app.database.repositories import filters as filter_repo
from app.services import moderation


def _instruction(text: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("◀️ Back", callback_data="set:advanced")]]
    )


@Client.on_callback_query(filters.regex(r"^adv:"), group=0)
async def advanced_callback(client: Client, callback: CallbackQuery) -> None:
    if not await require_callback_admin(client, callback):
        return

    action = callback.data.split(":", 1)[1]
    chat_id = callback.message.chat.id
    db = db_session.get_db()

    if action == "spam_mode":
        await callback.message.edit_text(
            "🎚 **Spam Mode**\n\n"
            "`monitor` – only log, never punish\n"
            "`delete` – remove flagged messages\n"
            "`warn` – warn the user\n"
            "`mute` – mute the user\n"
            "`ban` – ban the user\n\n"
            "Set it with `/spammode <mode>`",
            reply_markup=_instruction(""),
        )
        await callback.answer()
        return

    if action == "flood_action":
        await callback.message.edit_text(
            "🌊 **Flood Action**\n\n"
            "Set the flood limit and action with:\n"
            "`/antiflood <messages> <seconds> <action>`\n\n"
            "Example: `/antiflood 8 10 mute`",
            reply_markup=_instruction(""),
        )
        await callback.answer()
        return

    if action == "max_warnings":
        settings = await chat_repo.get_chat_settings(db, chat_id)
        await callback.message.edit_text(
            f"⚠️ **Max Warnings**\n\nCurrent: **{settings.max_warnings}**\n\n"
            "Set it with `/maxwarnings <1-10>`",
            reply_markup=_instruction(""),
        )
        await callback.answer()
        return

    if action == "mute_duration":
        settings = await chat_repo.get_chat_settings(db, chat_id)
        await callback.message.edit_text(
            f"🔇 **Mute Duration**\n\n"
            f"Current: **{moderation.format_duration(settings.mute_duration)}**\n\n"
            "Set it with `/mutetime <duration>`\n"
            "Examples: `10m`, `1h`, `6h`, `1d`, `7d`",
            reply_markup=_instruction(""),
        )
        await callback.answer()
        return

    if action == "allow_domain":
        settings = await chat_repo.get_chat_settings(db, chat_id)
        allow = ", ".join(settings.allow_domains) or "none"
        await callback.message.edit_text(
            f"🔗 **Allowed Domains**\n\n{allow}\n\n"
            "Add with `/allowdomain youtube.com`",
            reply_markup=_instruction(""),
        )
        await callback.answer()
        return

    if action == "block_domain":
        settings = await chat_repo.get_chat_settings(db, chat_id)
        blocked = ", ".join(settings.block_domains) or "none"
        await callback.message.edit_text(
            f"⛔ **Blocked Domains**\n\n{blocked}\n\n"
            "Add with `/blockdomain example.com`",
            reply_markup=_instruction(""),
        )
        await callback.answer()
        return

    if action == "allow_bot":
        settings = await chat_repo.get_chat_settings(db, chat_id)
        bots = ", ".join("@" + b for b in settings.allow_bots) or "none"
        await callback.message.edit_text(
            f"🤖 **Allowed Bots**\n\n{bots}\n\n"
            "Add with `/allowbot @examplebot`",
            reply_markup=_instruction(""),
        )
        await callback.answer()
        return

    await callback.answer("Unknown action", show_alert=True)
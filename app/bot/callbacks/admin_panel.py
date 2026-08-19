from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.utils import require_callback_admin
from app.bot.keyboards import admin_panel_keyboard
from app.database import session as db_session
from app.database.repositories import actions as action_repo
from app.database.repositories import chats as chat_repo
from app.database.repositories import filters as filter_repo
from app.database.repositories import logs as log_repo
from app.database.repositories import warnings as warnings_repo


def _back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("◀️ Back", callback_data="admin:menu")]]
    )


@Client.on_callback_query(filters.regex(r"^admin:"), group=0)
async def admin_panel_callback(client: Client, callback: CallbackQuery) -> None:
    if not await require_callback_admin(client, callback):
        return

    action = callback.data.split(":", 1)[1]
    chat_id = callback.message.chat.id
    db = db_session.get_db()

    if action == "menu":
        await callback.message.edit_text(
            "🛡 **Admin Panel**\n\nSelect a section.",
            reply_markup=admin_panel_keyboard(),
        )
        await callback.answer()
        return

    if action == "close":
        try:
            await callback.message.delete()
        except Exception:
            await callback.message.edit_text("Closed.")
        await callback.answer()
        return

    if action == "security":
        settings = await chat_repo.get_chat_settings(db, chat_id)
        lines = [
            "🛡 **Security**",
            "",
            f"Anti-Spam: {'🟢' if settings.antispam_enabled else '🔴'}",
            f"Anti-Flood: {'🟢' if settings.antiflood_enabled else '🔴'}",
            f"Anti-Link: {'🟢' if settings.antilink_enabled else '🔴'}",
            f"Anti-Raid: {'🟢' if settings.antiraid_enabled else '🔴'}",
            f"CAPTCHA: {'🟢' if settings.captcha_enabled else '🔴'}",
            f"Anti-Bot: {'🟢' if settings.antibot_enabled else '🔴'}",
            f"Spam mode: **{settings.spam_mode}**",
            "",
            "Open /settings to change.",
        ]
        await callback.message.edit_text("\n".join(lines), reply_markup=_back())
        await callback.answer()
        return

    if action == "moderation":
        await callback.message.edit_text(
            "⚖️ **Moderation Commands**\n\n"
            "/warn @user reason\n"
            "/warnings @user\n"
            "/clearwarns @user\n"
            "/mute 10m reason\n"
            "/unmute @user\n"
            "/ban @user reason\n"
            "/unban @user\n"
            "/kick @user\n"
            "/purge (reply to a message)\n\n"
            "Reply to a message for the fastest workflow.",
            reply_markup=_back(),
        )
        await callback.answer()
        return

    if action == "filters":
        filters_list = await filter_repo.list_filters(db, chat_id)
        if not filters_list:
            text = "🗂 **Filters**\n\nNo custom filters yet.\n\n/filter add <word> delete|warn|mute"
        else:
            lines = ["🗂 **Custom Filters**", ""]
            for f in filters_list:
                lines.append(f"• `{f.pattern}` → **{f.action}**")
            text = "\n".join(lines)
        await callback.message.edit_text(text, reply_markup=_back())
        await callback.answer()
        return

    if action == "warnings":
        settings = await chat_repo.get_chat_settings(db, chat_id)
        await callback.message.edit_text(
            f"⚠️ **Warnings**\n\n"
            f"Max warnings: **{settings.max_warnings}**\n"
            f"Warn system: {'on' if settings.warn_enabled else 'off'}\n\n"
            "Check a user's warnings with /warnings @user.",
            reply_markup=_back(),
        )
        await callback.answer()
        return

    if action == "logs":
        entries = await log_repo.recent_logs(db, chat_id, limit=10)
        if not entries:
            text = "📜 **Logs**\n\nNo logs yet."
        else:
            lines = ["📜 **Recent Logs**", ""]
            for e in entries:
                lines.append(
                    f"• {e.event_type} — `{e.user_id or e.admin_id or '?'}` "
                    f"({e.created_at.strftime('%m-%d %H:%M')})"
                )
            text = "\n".join(lines)
        await callback.message.edit_text(text, reply_markup=_back())
        await callback.answer()
        return

    if action == "welcome":
        settings = await chat_repo.get_chat_settings(db, chat_id)
        await callback.message.edit_text(
            f"👋 **Welcome**\n\n"
            f"Status: {'🟢 ON' if settings.welcome_enabled else '🔴 OFF'}\n\n"
            "`/welcome on|off`\n"
            "`/welcomemsg Welcome {user} to {chat}!`",
            reply_markup=_back(),
        )
        await callback.answer()
        return

    if action == "rules":
        settings = await chat_repo.get_chat_settings(db, chat_id)
        rules = settings.rules or "No rules set yet."
        await callback.message.edit_text(
            f"📜 **Rules**\n\n{rules}\n\nSet them with /setrules.",
            reply_markup=_back(),
        )
        await callback.answer()
        return

    await callback.answer("Unknown action", show_alert=True)
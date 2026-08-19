from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from app.bot.keyboards import back_keyboard, start_keyboard
from app.database import session as db_session
from app.database.repositories import chats as chat_repo


@Client.on_callback_query(filters.regex(r"^nav:"))
async def nav_callback(client: Client, callback: CallbackQuery) -> None:
    action = callback.data.split(":", 1)[1]
    chat = callback.message.chat

    if action == "help":
        await callback.message.edit_text(
            "🛡 **GuardianTG Help**\n\n"
            "Add me to your group as an administrator to start protecting it.\n\n"
            "**Moderation:** /warn /mute /ban /kick /purge /unban /unmute\n"
            "**Security:** /settings /antispam /antiflood /antilink /antiraid /captcha\n"
            "**Info:** /id /info /rules\n\n"
            "Use /help in a group for the full command list.",
            reply_markup=back_keyboard("nav:start"),
        )
        return

    if action == "features":
        await callback.message.edit_text(
            "⚙️ **Features**\n\n"
            "🚫 Anti-Spam — scoring engine with smart heuristics\n"
            "📨 Anti-Flood — message burst protection\n"
            "🔗 Anti-Link — link blocking + allowlist/blocklist\n"
            "💥 Anti-Raid — join-velocity detection + lockdown\n"
            "🧪 CAPTCHA — human verification on join\n"
            "🤖 Anti-Bot — remove unwanted bot accounts\n"
            "⚠️ Profanity — custom word filters\n"
            "👋 Welcome & Goodbye — configurable messages\n"
            "📜 Rules — per-group rules\n"
            "🗂 Logging — security log channel",
            reply_markup=back_keyboard("nav:start"),
        )
        return

    if action == "dev":
        await callback.message.edit_text(
            "👨‍💻 **Developer**\n\n"
            "GuardianTG is an open-source Telegram security bot.\n"
            "Built with Python 3.11+, Pyrogram, MongoDB, and Redis.\n\n"
            "Repo: github.com/abhisheek2006/GuardianTG",
            reply_markup=back_keyboard("nav:start"),
        )
        return

    if action == "start":
        me = await client.get_me()
        await callback.message.edit_text(
            "🛡 **GuardianTG**\n\nAdvanced Telegram Group Security Bot.",
            reply_markup=start_keyboard(me.username or ""),
        )
        return

    # Group-scoped actions: rules / security
    if chat.type in ("group", "supergroup"):
        db = db_session.get_db()
        settings = await chat_repo.get_chat_settings(db, chat.id)

        if action == "rules":
            rules = settings.rules or "No rules have been set for this group."
            await callback.message.edit_text(f"📜 **Group Rules**\n\n{rules}")
            return

        if action == "security":
            lines = [
                "🛡 **Security Status**",
                "",
                f"🟢 Anti-Spam" if settings.antispam_enabled else "🔴 Anti-Spam",
                f"🟢 Anti-Flood" if settings.antiflood_enabled else "🔴 Anti-Flood",
                f"🟢 Anti-Link" if settings.antilink_enabled else "🔴 Anti-Link",
                f"🟢 Anti-Raid" if settings.antiraid_enabled else "🔴 Anti-Raid",
                f"🟢 CAPTCHA" if settings.captcha_enabled else "🔴 CAPTCHA",
                f"🟢 Anti-Bot" if settings.antibot_enabled else "🔴 Anti-Bot",
                f"🟢 Logging" if settings.log_enabled else "🔴 Logging",
            ]
            await callback.message.edit_text("\n".join(lines))
            return

    await callback.answer("⚠️ This button only works inside a group.", show_alert=True)
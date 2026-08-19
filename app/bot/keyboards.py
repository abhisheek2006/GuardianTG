from __future__ import annotations

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import ChatSettingsDoc


def start_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➕ Add to Group",
                    url=f"https://t.me/{bot_username}?startgroup=true",
                )
            ],
            [
                InlineKeyboardButton("📚 Help", callback_data="nav:help"),
                InlineKeyboardButton("⚙️ Features", callback_data="nav:features"),
            ],
            [
                InlineKeyboardButton("👨‍💻 Developer", callback_data="nav:dev"),
            ],
        ]
    )


def settings_keyboard(settings: ChatSettingsDoc) -> InlineKeyboardMarkup:
    def btn(key: str, label: str) -> InlineKeyboardButton:
        status = settings.__getattribute__(key + "_enabled")
        icon = "🟢" if status else "🔴"
        return InlineKeyboardButton(f"{icon} {label}", callback_data=f"set:{key}")

    return InlineKeyboardMarkup(
        [
            [btn("antispam", "Anti-Spam"), btn("antiflood", "Anti-Flood")],
            [btn("antilink", "Anti-Link"), btn("antiraid", "Anti-Raid")],
            [btn("captcha", "CAPTCHA"), btn("antibot", "Anti-Bot")],
            [btn("profanity", "Profanity")],
            [btn("welcome", "Welcome"), btn("goodbye", "Goodbye")],
            [btn("log", "Logging")],
            [
                InlineKeyboardButton("⚙️ Advanced", callback_data="set:advanced"),
                InlineKeyboardButton("❌ Close", callback_data="set:close"),
            ],
        ]
    )


def advanced_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎚 Spam Mode", callback_data="adv:spam_mode")],
            [InlineKeyboardButton("🌊 Flood Action", callback_data="adv:flood_action")],
            [InlineKeyboardButton("⚠️ Max Warnings", callback_data="adv:max_warnings")],
            [InlineKeyboardButton("🔇 Mute Duration", callback_data="adv:mute_duration")],
            [InlineKeyboardButton("🔗 Allow Domain", callback_data="adv:allow_domain")],
            [InlineKeyboardButton("⛔ Block Domain", callback_data="adv:block_domain")],
            [InlineKeyboardButton("🤖 Allow Bot", callback_data="adv:allow_bot")],
            [InlineKeyboardButton("◀️ Back", callback_data="set:main")],
        ]
    )


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🛡 Security", callback_data="admin:security"),
             InlineKeyboardButton("⚖️ Moderation", callback_data="admin:moderation")],
            [InlineKeyboardButton("🗂 Filters", callback_data="admin:filters"),
             InlineKeyboardButton("⚠️ Warnings", callback_data="admin:warnings")],
            [InlineKeyboardButton("📜 Logs", callback_data="admin:logs")],
            [InlineKeyboardButton("👋 Welcome", callback_data="admin:welcome"),
             InlineKeyboardButton("📜 Rules", callback_data="admin:rules")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="set:main")],
            [InlineKeyboardButton("❌ Close", callback_data="admin:close")],
        ]
    )


def back_keyboard(callback_data: str = "nav:help") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data=callback_data)]])


def confirm_keyboard(confirm_data: str, cancel_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirm", callback_data=confirm_data),
                InlineKeyboardButton("❌ Cancel", callback_data=cancel_data),
            ]
        ]
    )


def welcome_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📜 Rules", callback_data="nav:rules"),
                InlineKeyboardButton("🛡 Security", callback_data="nav:security"),
            ]
        ]
    )


def raid_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔒 Lock Group", callback_data="raid:lock"),
                InlineKeyboardButton("👥 View Joins", callback_data="raid:joins"),
            ],
            [InlineKeyboardButton("⚙️ Security Settings", callback_data="set:main")],
        ]
    )
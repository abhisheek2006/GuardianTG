from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from motor.core import AgnosticDatabase
from pyrogram import Client

from app.database.repositories import chats as chat_repo
from app.database.repositories import logs as log_repo
from app.services import redis as redis_service

LOG_EVENT_LABELS = {
    "user_joined": "👤 User Joined",
    "user_left": "👋 User Left",
    "message_deleted": "🗑 Message Deleted",
    "warning_issued": "⚠️ Warning Issued",
    "user_muted": "🔇 User Muted",
    "user_unmuted": "🔊 User Unmuted",
    "user_banned": "🚷 User Banned",
    "user_unbanned": "✅ User Unbanned",
    "raid_detected": "🚨 Raid Detected",
    "captcha_failure": "🧪 CAPTCHA Failure",
    "link_blocked": "🔗 Link Blocked",
    "spam_detected": "🚫 Spam Detected",
    "settings_changed": "⚙️ Settings Changed",
    "filter_added": "🗂 Filter Added",
    "filter_removed": "🗂 Filter Removed",
}


def user_label(user_id: Optional[int]) -> str:
    if user_id is None:
        return "—"
    return f"`{user_id}`"


async def persist_and_notify(
    client: Client,
    db: AgnosticDatabase,
    chat_id: int,
    event_type: str,
    user_id: Optional[int] = None,
    admin_id: Optional[int] = None,
    message_id: Optional[int] = None,
    details: Optional[dict] = None,
    plain_text: Optional[str] = None,
) -> None:
    """Persist a security log entry and forward it to the log channel.

    `plain_text` (optional) is a short human-readable summary, used only if
    the entry also needs a channel post. Private message content is never
    logged; pass only structured `details`.
    """
    try:
        await log_repo.add_log(
            db,
            chat_id,
            event_type,
            user_id=user_id,
            admin_id=admin_id,
            message_id=message_id,
            details=details,
        )
    except Exception:
        # Logging must never crash the main flow.
        pass

    try:
        settings = await chat_repo.get_chat_settings(db, chat_id)
        if not (settings.log_enabled and settings.log_channel_id):
            return
        text = plain_text or format_log_entry(event_type, user_id, admin_id, details)
        await client.send_message(settings.log_channel_id, text)
    except Exception:
        pass


def format_log_entry(
    event_type: str,
    user_id: Optional[int] = None,
    admin_id: Optional[int] = None,
    details: Optional[dict] = None,
) -> str:
    label = LOG_EVENT_LABELS.get(event_type, event_type.replace("_", " ").title())
    lines = [f"🛡 SECURITY LOG", "", f"Action: **{label}**"]
    if user_id:
        lines.append(f"User: `{user_id}`")
    if admin_id:
        lines.append(f"Admin: `{admin_id}`")
    if details:
        for key, value in details.items():
            if value is None or value == "":
                continue
            key_label = key.replace("_", " ").title()
            lines.append(f"{key_label}: {value}")
    lines.append("")
    lines.append(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    return "\n".join(lines)


def format_chat_link(chat_id: int) -> str:
    return f"[{chat_id}](tg://resolve?domain=joinchat&post={chat_id})"
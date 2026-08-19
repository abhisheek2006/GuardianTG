from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from motor.core import AgnosticDatabase
from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant, UserPrivacyRestricted
from pyrogram.types import (
    ChatPermissions,
    ChatPrivileges,
    Message,
    User,
)

from app.database.repositories import actions as actions_repo
from app.database.repositories import chats as chat_repo
from app.database.repositories import warnings as warnings_repo
from app.services import eventlog
from app.services import permissions as perms

FULL_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_media_messages=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)

MUTE_PERMISSIONS = ChatPermissions(can_send_messages=False)

DURATION_RE = re.compile(
    r"^(\d+)\s*(s|sec|second|m|min|minute|h|hour|d|day|w|week)?$", re.I
)


def parse_duration(value: str) -> Optional[int]:
    """Parse a duration like '10m', '1h', '2d', '30', '90' -> seconds."""
    match = DURATION_RE.match(value.strip())
    if not match:
        return None
    amount = int(match.group(1))
    unit = (match.group(2) or "m").lower()
    multipliers = {
        "s": 1,
        "sec": 1,
        "second": 1,
        "m": 60,
        "min": 60,
        "minute": 60,
        "h": 3600,
        "hour": 3600,
        "d": 86400,
        "day": 86400,
        "w": 604800,
        "week": 604800,
    }
    return amount * multipliers[unit]


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} seconds"
    if seconds < 3600:
        return f"{seconds // 60} minutes"
    if seconds < 86400:
        return f"{seconds // 3600} hours"
    return f"{seconds // 86400} days"


async def resolve_target(
    client: Client, message: Message, mention: Optional[str] = None
) -> Optional[User]:
    """Resolve the target user of a moderation command.

    Priority: replied-to message author, then @username / @id argument.
    """
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if mention:
        try:
            return await client.get_users(mention)
        except Exception:
            return None
    return None


async def is_protected(client: Client, chat_id: int, user_id: int) -> bool:
    """True when the target is an admin (or the bot itself) and must not be punished."""
    if user_id == (await client.get_me()).id:
        return True
    return await perms.is_chat_admin(client, chat_id, user_id)


async def _ensure_can_restrict(client: Client, chat_id: int, message: Message) -> bool:
    if await perms.can_restrict(client, chat_id):
        return True
    missing = await perms.missing_permissions(client, chat_id)
    await message.reply_text(
        "⚠️ **Missing Permission**\n\n"
        "GuardianTG needs:\n\n"
        + "\n".join(f"• {item}" for item in missing)
        + "\n\nPlease promote the bot to administrator and enable the required permissions."
    )
    return False


# ── Warnings ─────────────────────────────────────────────────────────

async def warn_user(
    client: Client,
    db: AgnosticDatabase,
    chat_id: int,
    target: User,
    admin: User,
    reason: str,
    message: Message,
) -> dict:
    settings = await chat_repo.get_chat_settings(db, chat_id)
    if not settings.warn_enabled:
        return {"ok": False, "error": "Warning system is disabled in this chat."}

    if await is_protected(client, chat_id, target.id):
        await message.reply_text("🚫 You cannot warn an administrator.")
        return {"ok": False, "error": "protected"}

    warning = await warnings_repo.add_warning(
        db, chat_id, target.id, reason, admin.id
    )
    count = await warnings_repo.active_warning_count(db, chat_id, target.id)
    max_warnings = settings.max_warnings

    await actions_repo.log_action(
        db, chat_id, target.id, "warn", reason=reason, admin_user_id=admin.id
    )
    await eventlog.persist_and_notify(
        client,
        db,
        chat_id,
        "warning_issued",
        user_id=target.id,
        admin_id=admin.id,
        details={"reason": reason, "warnings": f"{count}/{max_warnings}"},
    )

    text = (
        f"⚠️ **Warning issued**\n\n"
        f"User: {target.mention}\n"
        f"Reason: {reason or 'Not specified'}\n\n"
        f"Warnings: **{count}/{max_warnings}**"
    )

    if count >= max_warnings:
        if await perms.can_restrict(client, chat_id):
            duration = settings.mute_duration
            await mute_user(
                client, db, chat_id, target.id, admin.id, duration,
                reason=f"Auto-punishment after reaching {max_warnings}/{max_warnings} warnings",
                message=None,
            )
            text += (
                f"\n\n🔇 **Limit reached — user muted for {format_duration(duration)}.**"
            )
        else:
            text += "\n\n⚠️ Could not auto-punish (bot lacks restrict permission)."

    await message.reply_text(text)
    return {"ok": True, "count": count, "max": max_warnings}


# ── Mute / unmute ────────────────────────────────────────────────────

async def mute_user(
    client: Client,
    db: AgnosticDatabase,
    chat_id: int,
    target_user_id: int,
    admin_user_id: int,
    duration: int,
    reason: Optional[str] = None,
    message: Optional[Message] = None,
) -> dict:
    if not await perms.can_restrict(client, chat_id):
        if message:
            await _ensure_can_restrict(client, chat_id, message)
        return {"ok": False, "error": "missing_permission"}

    until = datetime.now(timezone.utc) + timedelta(seconds=duration)
    try:
        await client.restrict_chat_member(
            chat_id,
            target_user_id,
            MUTE_PERMISSIONS,
            until_date=until,
        )
    except Exception:
        if message:
            await message.reply_text("⚠️ Could not mute that user. Maybe they left the chat.")
        return {"ok": False, "error": "restrict_failed"}

    await actions_repo.log_action(
        db, chat_id, target_user_id, "mute",
        reason=reason, admin_user_id=admin_user_id, expires_at=until,
    )
    await eventlog.persist_and_notify(
        client, db, chat_id, "user_muted",
        user_id=target_user_id, admin_id=admin_user_id,
        details={"duration": format_duration(duration), "reason": reason},
    )

    if message:
        await message.reply_text(
            f"🔇 **User muted**\n\n"
            f"User: `{target_user_id}`\n"
            f"Duration: {format_duration(duration)}\n"
            f"Reason: {reason or 'Not specified'}"
        )
    return {"ok": True}


async def unmute_user(
    client: Client,
    db: AgnosticDatabase,
    chat_id: int,
    target_user_id: int,
    admin_user_id: int,
    message: Optional[Message] = None,
) -> dict:
    try:
        await client.restrict_chat_member(chat_id, target_user_id, FULL_PERMISSIONS)
    except UserNotParticipant:
        if message:
            await message.reply_text("⚠️ That user is not in the chat.")
        return {"ok": False, "error": "not_participant"}
    except Exception:
        if message:
            await message.reply_text("⚠️ Could not unmute that user.")
        return {"ok": False, "error": "unmute_failed"}

    await actions_repo.log_action(
        db, chat_id, target_user_id, "unmute", admin_user_id=admin_user_id
    )
    await eventlog.persist_and_notify(
        client, db, chat_id, "user_unmuted",
        user_id=target_user_id, admin_id=admin_user_id,
    )
    if message:
        await message.reply_text(f"🔊 **User unmuted**\n\nUser: `{target_user_id}`")
    return {"ok": True}


# ── Ban / unban / kick ───────────────────────────────────────────────

async def ban_user(
    client: Client,
    db: AgnosticDatabase,
    chat_id: int,
    target: User,
    admin: User,
    reason: Optional[str],
    message: Message,
) -> dict:
    if not await _ensure_can_restrict(client, chat_id, message):
        return {"ok": False, "error": "missing_permission"}
    if await is_protected(client, chat_id, target.id):
        await message.reply_text("🚫 You cannot ban an administrator.")
        return {"ok": False, "error": "protected"}

    try:
        await client.ban_chat_member(chat_id, target.id)
    except UserPrivacyRestricted:
        await message.reply_text("⚠️ This user has restricted who can add them to groups.")
        return {"ok": False, "error": "privacy_restricted"}
    except Exception as exc:
        await message.reply_text(f"⚠️ Could not ban: {exc}")
        return {"ok": False, "error": "ban_failed"}

    await actions_repo.ban_user(db, chat_id, target.id, reason, admin.id)
    await actions_repo.log_action(
        db, chat_id, target.id, "ban", reason=reason, admin_user_id=admin.id
    )
    await eventlog.persist_and_notify(
        client, db, chat_id, "user_banned",
        user_id=target.id, admin_id=admin.id, details={"reason": reason},
    )
    await message.reply_text(
        f"🚷 **User banned**\n\nUser: {target.mention}\nReason: {reason or 'Not specified'}"
    )
    return {"ok": True}


async def unban_user(
    client: Client,
    db: AgnosticDatabase,
    chat_id: int,
    target: User,
    admin: User,
    message: Message,
) -> dict:
    if not await _ensure_can_restrict(client, chat_id, message):
        return {"ok": False, "error": "missing_permission"}
    try:
        await client.unban_chat_member(chat_id, target.id)
    except Exception as exc:
        await message.reply_text(f"⚠️ Could not unban: {exc}")
        return {"ok": False, "error": "unban_failed"}

    await actions_repo.unban_user(db, chat_id, target.id)
    await actions_repo.log_action(
        db, chat_id, target.id, "unban", admin_user_id=admin.id
    )
    await eventlog.persist_and_notify(
        client, db, chat_id, "user_unbanned",
        user_id=target.id, admin_id=admin.id,
    )
    await message.reply_text(f"✅ **User unbanned**\n\nUser: {target.mention}")
    return {"ok": True}


async def kick_user(
    client: Client,
    db: AgnosticDatabase,
    chat_id: int,
    target: User,
    admin: User,
    reason: Optional[str],
    message: Message,
) -> dict:
    if not await _ensure_can_restrict(client, chat_id, message):
        return {"ok": False, "error": "missing_permission"}
    if await is_protected(client, chat_id, target.id):
        await message.reply_text("🚫 You cannot kick an administrator.")
        return {"ok": False, "error": "protected"}

    try:
        await client.ban_chat_member(chat_id, target.id)
        await client.unban_chat_member(chat_id, target.id)
    except Exception as exc:
        await message.reply_text(f"⚠️ Could not kick: {exc}")
        return {"ok": False, "error": "kick_failed"}

    await actions_repo.log_action(
        db, chat_id, target.id, "kick", reason=reason, admin_user_id=admin.id
    )
    await eventlog.persist_and_notify(
        client, db, chat_id, "user_banned",
        user_id=target.id, admin_id=admin.id,
        details={"reason": reason or "Kicked (without ban)"},
    )
    await message.reply_text(f"👢 **User kicked**\n\nUser: {target.mention}")
    return {"ok": True}


# ── Purge ────────────────────────────────────────────────────────────

async def purge_messages(client: Client, chat_id: int, message_ids: list[int]) -> int:
    """Delete messages in batches of 100, respecting Telegram API limits."""
    deleted = 0
    for i in range(0, len(message_ids), 100):
        batch = message_ids[i:i + 100]
        try:
            await client.delete_messages(chat_id, batch)
            deleted += len(batch)
        except Exception:
            # delete_messages is atomic per call; fall back to per-message.
            for msg_id in batch:
                try:
                    await client.delete_messages(chat_id, msg_id)
                    deleted += 1
                except Exception:
                    continue
    return deleted


def reply_duration(value: Optional[str], default: int) -> int:
    if not value:
        return default
    parsed = parse_duration(value)
    return parsed if parsed else default
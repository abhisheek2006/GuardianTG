from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message

from app.bot.decorators import require_chat_admin, with_rate_limit
from app.bot.utils import is_group, parse_args, split_command
from app.database import session as db_session
from app.database.repositories import warnings as warnings_repo
from app.services import moderation
from app.services import runtime


@Client.on_message(filters.command("warn") & filters.group)
@require_chat_admin
@with_rate_limit()
async def warn_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    mention, reason = _split_target_reason(rest)

    target = await moderation.resolve_target(client, message, mention)
    if not target:
        await message.reply_text(
            "⚠️ Usage: reply to a message with `/warn reason` or use `/warn @user reason`"
        )
        return

    db = db_session.get_db()
    result = await moderation.warn_user(
        client, db, message.chat.id, target, message.from_user, reason, message
    )
    if not result.get("ok"):
        return


@Client.on_message(filters.command("warnings") & filters.group)
@require_chat_admin
@with_rate_limit()
async def warnings_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    mention = rest.split()[0] if rest.strip() else None
    target = await moderation.resolve_target(client, message, mention) or message.from_user

    db = db_session.get_db()
    count = await warnings_repo.active_warning_count(db, message.chat.id, target.id)
    settings = await db_session.get_db().chat_settings.find_one({"chat_id": message.chat.id})
    max_warnings = (settings or {}).get("max_warnings", 3)
    await message.reply_text(
        f"⚠️ **Warnings for {target.mention}:** {count}/{max_warnings}"
    )


@Client.on_message(filters.command("clearwarns") & filters.group)
@require_chat_admin
@with_rate_limit()
async def clearwarns_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    mention = rest.split()[0] if rest.strip() else None
    target = await moderation.resolve_target(client, message, mention)
    if not target:
        await message.reply_text("⚠️ Reply to a user or pass a username.")
        return

    db = db_session.get_db()
    removed = await warnings_repo.clear_warnings(db, message.chat.id, target.id)
    await message.reply_text(f"✅ Cleared {removed} warning(s) for {target.mention}.")


@Client.on_message(filters.command("mute") & filters.group)
@require_chat_admin
@with_rate_limit()
async def mute_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    mention, duration_str, reason = _parse_mute_args(rest)

    target = await moderation.resolve_target(client, message, mention)
    if not target:
        await message.reply_text("⚠️ Reply to a message or pass a username.")
        return

    db = db_session.get_db()
    settings = await db_session.get_db().chat_settings.find_one({"chat_id": message.chat.id})
    default_duration = (settings or {}).get("mute_duration", 600)

    duration = moderation.parse_duration(duration_str) if duration_str else default_duration
    if not duration:
        await message.reply_text(
            "⚠️ Invalid duration. Examples: `10m`, `1h`, `6h`, `1d`, `7d`"
        )
        return

    await moderation.mute_user(
        client, db, message.chat.id, target.id, message.from_user.id,
        duration, reason, message,
    )


@Client.on_message(filters.command("unmute") & filters.group)
@require_chat_admin
@with_rate_limit()
async def unmute_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    mention = rest.split()[0] if rest.strip() else None
    target = await moderation.resolve_target(client, message, mention)
    if not target:
        await message.reply_text("⚠️ Reply to a message or pass a username.")
        return
    db = db_session.get_db()
    await moderation.unmute_user(
        client, db, message.chat.id, target.id, message.from_user.id, message
    )


@Client.on_message(filters.command("ban") & filters.group)
@require_chat_admin
@with_rate_limit()
async def ban_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    mention, reason = _split_target_reason(rest)
    target = await moderation.resolve_target(client, message, mention)
    if not target:
        await message.reply_text("⚠️ Reply to a message or pass a username.")
        return
    db = db_session.get_db()
    await moderation.ban_user(
        client, db, message.chat.id, target, message.from_user, reason or None, message
    )


@Client.on_message(filters.command("unban") & filters.group)
@require_chat_admin
@with_rate_limit()
async def unban_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    mention = rest.split()[0] if rest.strip() else None
    target = await moderation.resolve_target(client, message, mention)
    if not target:
        await message.reply_text("⚠️ Reply to a message or pass a username.")
        return
    db = db_session.get_db()
    await moderation.unban_user(
        client, db, message.chat.id, target, message.from_user, message
    )


@Client.on_message(filters.command("kick") & filters.group)
@require_chat_admin
@with_rate_limit()
async def kick_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    mention, reason = _split_target_reason(rest)
    target = await moderation.resolve_target(client, message, mention)
    if not target:
        await message.reply_text("⚠️ Reply to a message or pass a username.")
        return
    db = db_session.get_db()
    await moderation.kick_user(
        client, db, message.chat.id, target, message.from_user, reason or None, message
    )


@Client.on_message(filters.command("purge") & filters.group)
@require_chat_admin
@with_rate_limit()
async def purge_command(client: Client, message: Message) -> None:
    reply = message.reply_to_message
    if not reply:
        await message.reply_text(
            "⚠️ Reply to a message to delete everything from there up to this point."
        )
        return

    # Count messages to delete (excluding the purge command message).
    total = message.id - reply.id + 1
    if total > 1000:
        await message.reply_text("⚠️ Too many messages. Please purge in chunks of 1000.")
        return

    if total <= 10:
        # Small enough — delete immediately without confirmation.
        await _do_purge(client, message, reply)
        return

    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    await message.reply_text(
        f"🧹 Delete **{total}** messages?",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Confirm", callback_data=f"purge:{reply.id}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="purge:cancel"),
                ]
            ]
        ),
    )


async def _do_purge(client: Client, message: Message, reply: Message) -> None:
    ids = list(range(reply.id, message.id + 1))
    try:
        deleted = await moderation.purge_messages(client, message.chat.id, ids)
        await message.reply_text(f"🧹 Deleted {deleted} message(s).")
    except Exception:
        await message.reply_text("⚠️ Could not delete messages. Check bot permissions.")


def _split_target_reason(rest: str) -> tuple[str | None, str]:
    """'@user reason...' -> ('@user', 'reason...')"""
    rest = rest.strip()
    if not rest:
        return None, ""
    if rest.startswith("@"):
        parts = rest.split(maxsplit=1)
        return parts[0], parts[1] if len(parts) > 1 else ""
    return None, rest


def _parse_mute_args(rest: str) -> tuple[str | None, str, str]:
    """'@user 10m reason' -> (mention, duration, reason)."""
    rest = rest.strip()
    if not rest:
        return None, "", ""
    if rest.startswith("@"):
        parts = rest.split(maxsplit=2)
        mention = parts[0]
        duration = parts[1] if len(parts) > 1 else ""
        reason = parts[2] if len(parts) > 2 else ""
        return mention, duration, reason
    parts = rest.split(maxsplit=1)
    duration = parts[0]
    reason = parts[1] if len(parts) > 1 else ""
    return None, duration, reason
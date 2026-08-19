from __future__ import annotations

import os
import signal
import sys

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

from app.bot.decorators import require_owner, with_rate_limit
from app.bot.keyboards import confirm_keyboard
from app.database import session as db_session
from app.database.repositories import actions as action_repo
from app.database.repositories import logs as log_repo
from app.database.repositories import users as user_repo
from app.services import approval, health, redis as redis_service
from app.services import text_format as tf


@Client.on_message(filters.command("stats"))
@require_owner
@with_rate_limit()
async def stats_command(client: Client, message: Message) -> None:
    db = db_session.get_db()
    users = await user_repo.count_users(db)
    chats = await log_repo.count_chats(db)
    actions = await action_repo.total_action_counts(db)
    log_count = await log_repo.count_logs(db)

    blocked = actions.get("ban", 0) + actions.get("kick", 0)
    lines = [
        "📊 **GuardianTG Statistics**",
        "",
        f"👥 Known users: **{users}**",
        f"💬 Groups: **{chats}**",
        f"📝 Log entries: **{log_count}**",
        "",
        "**Moderation actions**",
        f"⚠️ Warns: {actions.get('warn', 0)}",
        f"🔇 Mutes: {actions.get('mute', 0)}",
        f"🚷 Bans: {actions.get('ban', 0)}",
        f"👢 Kicks: {actions.get('kick', 0)}",
        f"🚫 Blocked: {blocked}",
    ]
    await message.reply_text("\n".join(lines))


@Client.on_message(filters.command("chats"))
@require_owner
@with_rate_limit()
async def chats_command(client: Client, message: Message) -> None:
    db = db_session.get_db()
    cursor = db.chats.find({}, {"telegram_chat_id": 1, "title": 1}).sort("created_at", -1).limit(20)
    rows = await cursor.to_list(length=20)
    if not rows:
        await message.reply_text("No groups registered yet.")
        return
    lines = ["💬 **Registered Groups**", ""]
    for row in rows:
        lines.append(f"• `{row.get('telegram_chat_id')}` — {row.get('title') or 'Untitled'}")
    await message.reply_text("\n".join(lines))


@Client.on_message(filters.command("broadcast"))
@require_owner
@with_rate_limit()
async def broadcast_command(client: Client, message: Message) -> None:
    text = message.text.split(maxsplit=1)[1].strip() if len(message.text.split(maxsplit=1)) > 1 else ""
    if not text:
        await message.reply_text(
            "⚠️ Usage: `/broadcast <message>`\n\n"
            "**Formatting markers:**\n"
            "`_mono_`  → mono text\n"
            "`{bold}`  → bold text\n"
            "`\"spoiler\"` → spoiler text\n"
            "`:quote:` → quoted/blockquote text\n"
            "`[label](https://url)` → link button\n"
            "URLs are auto-linked."
        )
        return

    # Store the draft so the confirm callback can reuse it.
    await redis_service.get_redis().set(
        f"bcast:draft:{message.from_user.id}",
        text,
        ex=600,
    )

    db = db_session.get_db()
    total = await log_repo.count_chats(db)
    preview = tf.format_rich_text(text)
    await message.reply_text(
        f"📢 Broadcast this message to **{total}** groups?\n\n{preview}",
        reply_markup=confirm_keyboard("bcast:yes", "bcast:no"),
    )


@Client.on_message(filters.command("restart"))
@require_owner
@with_rate_limit()
async def restart_command(client: Client, message: Message) -> None:
    await message.reply_text("🔄 Restarting...")
    from app.services import runtime

    try:
        await runtime.get_client().stop()
    except Exception:
        pass
    os.execv(sys.executable, [sys.executable, "-m", "app.main"])


@Client.on_message(filters.command("maintenance"))
@require_owner
@with_rate_limit()
async def maintenance_command(client: Client, message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    rest = parts[1].strip().lower() if len(parts) > 1 else ""
    if rest not in ("on", "off"):
        await message.reply_text("⚠️ Usage: `/maintenance on|off`")
        return
    enabled = rest == "on"
    await redis_service.get_redis().set(
        "maintenance", "1" if enabled else "0", ex=86400 if enabled else 1
    )
    await message.reply_text(
        f"🛠 Maintenance mode: {'ON' if enabled else 'OFF'}."
    )


@Client.on_message(filters.command("debug"))
@require_owner
@with_rate_limit()
async def debug_command(client: Client, message: Message) -> None:
    status = await health.check()
    await message.reply_text(status.summary)


@Client.on_message(filters.command("approve") & filters.private)
@require_owner
@with_rate_limit()
async def approve_command(client: Client, message: Message) -> None:
    """Approve a chat so the bot starts protecting it.

    Usage (in private chat with the bot):
      /approve <chat_id> <days>
      /approve <chat_id> 30
    """
    if message.chat.type != ChatType.PRIVATE:
        await message.reply_text(
            "⚠️ Run /approve in the bot's private chat with the owner account."
        )
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.reply_text(
            "⚠️ Usage: `/approve <chat_id> <days>`\n\n"
            "Example: `/approve -1001234567890 30`\n\n"
            "Add the bot as an administrator in the group/channel first, "
            "then approve it here. Until approved, the bot replies "
            "`You are not approved` in that chat."
        )
        return

    try:
        chat_id = int(parts[1].strip())
    except ValueError:
        await message.reply_text("⚠️ chat_id must be a number, e.g. -1001234567890")
        return

    days = 30
    if len(parts) >= 3:
        try:
            days = int(parts[2])
        except ValueError:
            await message.reply_text("⚠️ days must be a number.")
            return
        if days < 1 or days > 3650:
            await message.reply_text("⚠️ days must be between 1 and 3650.")
            return

    db = db_session.get_db()
    expires = await approval.approve(db, chat_id, days, message.from_user.id)
    await message.reply_text(
        f"✅ **Chat approved**\n\n"
        f"Chat ID: `{chat_id}`\n"
        f"Duration: {days} days\n"
        f"Expires: {expires.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        f"The bot is now active in this group/channel."
    )


@Client.on_message(filters.command("revoke") & filters.private)
@require_owner
@with_rate_limit()
async def revoke_command(client: Client, message: Message) -> None:
    """Revoke approval for a chat."""
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply_text("⚠️ Usage: `/revoke <chat_id>`")
        return
    try:
        chat_id = int(parts[1].strip())
    except ValueError:
        await message.reply_text("⚠️ chat_id must be a number.")
        return

    db = db_session.get_db()
    await approval.revoke(db, chat_id)
    await message.reply_text(f"⛔ Approval revoked for `{chat_id}`.")


@Client.on_message(filters.command("approved") & filters.private)
@require_owner
@with_rate_limit()
async def approved_list_command(client: Client, message: Message) -> None:
    db = db_session.get_db()
    rows = await approval.list_approved(db)
    if not rows:
        await message.reply_text("No chats approved yet.")
        return
    lines = ["✅ **Approved chats**", ""]
    for row in rows:
        expires = row.get("expires_at")
        exp_text = expires.strftime("%Y-%m-%d") if expires else "never"
        lines.append(f"• `{row.get('chat_id')}` — until {exp_text}")
    await message.reply_text("\n".join(lines))
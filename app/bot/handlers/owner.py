from __future__ import annotations

import os
import signal
import sys

from pyrogram import Client, filters
from pyrogram.types import Message

from app.bot.decorators import require_owner, with_rate_limit
from app.bot.keyboards import confirm_keyboard
from app.database import session as db_session
from app.database.repositories import actions as action_repo
from app.database.repositories import logs as log_repo
from app.database.repositories import users as user_repo
from app.services import health, redis as redis_service


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
        await message.reply_text("⚠️ Usage: `/broadcast <message>`")
        return

    db = db_session.get_db()
    total = await log_repo.count_chats(db)
    await message.reply_text(
        f"📢 Broadcast this message to **{total}** groups?\n\n{text}",
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
    _, rest = message.text.split(maxsplit=1)
    state = rest.strip().lower()
    if state not in ("on", "off"):
        await message.reply_text("⚠️ Usage: `/maintenance on|off`")
        return
    enabled = state == "on"
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
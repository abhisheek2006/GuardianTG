from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.callbacks.utils import require_callback_admin
from app.database import session as db_session
from app.services import antiraid, moderation
from app.services import redis as redis_service


# ── Purge confirmation ───────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^purge:"), group=0)
async def purge_callback(client: Client, callback: CallbackQuery) -> None:
    if not await require_callback_admin(client, callback):
        return

    data = callback.data.split(":", 1)[1]
    if data == "cancel":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer("Cancelled.")
        return

    try:
        start_id, end_id = (int(x) for x in data.split(":"))
    except ValueError:
        await callback.answer("Invalid purge range.", show_alert=True)
        return

    ids = list(range(start_id, end_id + 1))
    deleted = await moderation.purge_messages(client, callback.message.chat.id, ids)
    await callback.answer(f"Deleted {deleted} message(s).")
    try:
        await callback.message.edit_text(f"🧹 Deleted {deleted} message(s).")
    except Exception:
        pass


# ── Broadcast confirmation ───────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^bcast:"), group=0)
async def broadcast_callback(client: Client, callback: CallbackQuery) -> None:
    choice = callback.data.split(":", 1)[1]
    owner_id = callback.from_user.id if callback.from_user else 0

    if choice == "no":
        await callback.answer("Broadcast cancelled.")
        try:
            await callback.message.edit_text("📢 Broadcast cancelled.")
        except Exception:
            pass
        return

    draft = await redis_service.get_redis().get(f"bcast:draft:{owner_id}")
    if not draft:
        await callback.answer("⚠️ No draft found. Run /broadcast again.", show_alert=True)
        return

    from app.services import text_format as tf

    html_text = tf.format_rich_text(draft)
    db = db_session.get_db()
    cursor = db.chats.find({}, {"telegram_chat_id": 1}).sort("created_at", -1)
    sent = 0
    failed = 0
    chat_ids = [doc["telegram_chat_id"] for doc in await cursor.to_list(length=5000)]

    await callback.answer("Broadcasting…")
    for chat_id in chat_ids:
        try:
            await client.send_message(chat_id, html_text)
            sent += 1
        except Exception:
            failed += 1

    try:
        await callback.message.edit_text(
            f"📢 Broadcast complete.\n\nSent: **{sent}**\nFailed: {failed}"
        )
    except Exception:
        pass


# ── Raid controls ────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^raid:"), group=0)
async def raid_callback(client: Client, callback: CallbackQuery) -> None:
    if not await require_callback_admin(client, callback):
        return

    action = callback.data.split(":", 1)[1]
    chat_id = callback.message.chat.id

    if action == "lock":
        await antiraid.set_lockdown(chat_id, True)
        await callback.answer("🔒 Group locked down. New members must verify.")
        try:
            await callback.message.edit_text("🔒 **Group locked down.**\nNew members must pass CAPTCHA to join.")
        except Exception:
            pass
        return

    if action == "joins":
        recent = await antiraid.recent_joins(chat_id, limit=20)
        if not recent:
            await callback.answer("No recent joins recorded.", show_alert=True)
            return
        lines = ["👥 **Recent joins**", ""]
        for user_id in reversed(recent):
            lines.append(f"• `{user_id}`")
        await callback.message.edit_text("\n".join(lines))
        await callback.answer()
        return

    await callback.answer("Unknown action", show_alert=True)
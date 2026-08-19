from __future__ import annotations

from pyrogram import Client, enums
from pyrogram.types import ChatMemberUpdated, Message

from app.bot.handlers.verification import start_captcha
from app.bot.keyboards import welcome_buttons
from app.core.config import get_settings
from app.database import session as db_session
from app.database.repositories import chats as chat_repo
from app.database.repositories import users as user_repo
from app.services import antiraid, eventlog
from app.services import permissions as perms
from app.services import approval
from app.services import redis as redis_service

JOIN_STATUSES = {enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.RESTRICTED}
LEFT_STATUSES = {
    enums.ChatMemberStatus.LEFT,
    enums.ChatMemberStatus.BANNED,
}
PRIOR_STATUSES = {
    None,
    enums.ChatMemberStatus.LEFT,
    enums.ChatMemberStatus.BANNED,
}


@Client.on_chat_member_updated(group=0)
async def member_update(client: Client, update: ChatMemberUpdated) -> None:
    if update.chat.type not in ("group", "supergroup"):
        return

    db = db_session.get_db()
    if not await approval.is_approved(db, update.chat.id, use_cache=True):
        return

    new_status = update.new_chat_member.status if update.new_chat_member else None
    old_status = update.old_chat_member.status if update.old_chat_member else None
    user = update.new_chat_member.user if update.new_chat_member else (
        update.old_chat_member.user if update.old_chat_member else None
    )
    if user is None:
        return

    me = await client.get_me()
    if user.id == me.id:
        return

    if new_status in JOIN_STATUSES and old_status in PRIOR_STATUSES:
        await _handle_join(client, db, update, user)
    elif new_status in LEFT_STATUSES and old_status in JOIN_STATUSES:
        await _handle_leave(client, db, update, user)


async def _handle_join(
    client: Client, db, update: ChatMemberUpdated, user
) -> None:
    chat_id = update.chat.id
    settings = await chat_repo.get_chat_settings(db, chat_id)

    await user_repo.get_or_create_user(
        db, user.id, user.username, user.first_name, user.last_name, user.is_bot
    )
    await eventlog.persist_and_notify(
        client, db, chat_id, "user_joined", user_id=user.id
    )

    # ── Anti-bot ────────────────────────────────────────────────
    if settings.antibot_enabled and user.is_bot:
        username = (user.username or "").lower()
        if username not in settings.allow_bots and await perms.can_restrict(client, chat_id):
            try:
                await client.ban_chat_member(chat_id, user.id)
                await client.unban_chat_member(chat_id, user.id)
                await eventlog.persist_and_notify(
                    client, db, chat_id, "user_banned",
                    user_id=user.id,
                    details={"reason": "Bot accounts are not allowed in this group"},
                )
            except Exception:
                pass
            return

    # ── Anti-raid ───────────────────────────────────────────────
    if settings.antiraid_enabled:
        try:
            count = await antiraid.record_join(chat_id, user.id, settings.raid_window)
            if await antiraid.is_raid(chat_id, settings.raid_threshold, settings.raid_window):
                await antiraid.set_lockdown(chat_id, True)
                await _notify_raid(client, db, chat_id, count, settings)
        except Exception:
            pass

    # ── Lockdown: always verify new members ─────────────────────
    lock = await antiraid.is_lockdown(chat_id)

    # ── CAPTCHA verification ────────────────────────────────────
    if settings.captcha_enabled and not user.is_bot:
        try:
            await start_captcha(client, db, chat_id, user)
        except Exception:
            pass

    # ── Welcome message ─────────────────────────────────────────
    if settings.welcome_enabled:
        try:
            template = (
                settings.welcome_message or "Welcome {user} to {chat}!"
            )
            text = (
                template.replace("{user}", user.mention)
                .replace("{name}", (user.first_name or "Member"))
                .replace("{username}", f"@{user.username}" if user.username else str(user.id))
                .replace("{chat}", update.chat.title or "the group")
                .replace("{id}", str(user.id))
            )
            await client.send_message(chat_id, text, reply_markup=welcome_buttons())
        except Exception:
            pass

    if lock:
        try:
            await client.send_message(
                chat_id,
                "🔒 **Lockdown active** — new members are being verified with CAPTCHA.",
            )
        except Exception:
            pass


async def _handle_leave(
    client: Client, db, update: ChatMemberUpdated, user
) -> None:
    chat_id = update.chat.id
    settings = await chat_repo.get_chat_settings(db, chat_id)
    await eventlog.persist_and_notify(
        client, db, chat_id, "user_left", user_id=user.id
    )
    if settings.goodbye_enabled:
        try:
            template = settings.goodbye_message or "👋 {user} has left the group."
            text = template.replace("{user}", user.mention or "Someone")
            await client.send_message(chat_id, text)
        except Exception:
            pass


async def _notify_raid(client: Client, db, chat_id: int, count: int, settings) -> None:
    from app.bot.keyboards import raid_keyboard

    # Notify admins (cached list) + owner.
    notified = 0
    for admin_id in await perms.get_chat_admins(client, chat_id):
        try:
            await client.send_message(
                admin_id,
                f"🚨 **RAID DETECTED**\n\n"
                f"Chat: {chat_id}\n\n"
                f"**{count}** users joined in the last {settings.raid_window} seconds.\n\n"
                "GuardianTG has activated emergency protection.\n"
                "New members are now locked and require CAPTCHA verification.",
                reply_markup=raid_keyboard(),
            )
            notified += 1
        except Exception:
            continue

    owner = get_settings().owner_id
    if owner and owner not in await perms.get_chat_admins(client, chat_id):
        try:
            await client.send_message(
                owner,
                f"🚨 **RAID DETECTED**\n\nChat: `{chat_id}`\n"
                f"{count} joins in {settings.raid_window}s.",
            )
        except Exception:
            pass

    if notified == 0:
        await eventlog.persist_and_notify(
            client, db, chat_id, "raid_detected",
            details={"joins": count, "window": settings.raid_window, "action": "lockdown"},
        )
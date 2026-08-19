from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message

from app.bot.decorators import require_chat_admin, with_rate_limit
from app.bot.utils import is_group, split_command
from app.database import session as db_session
from app.database.repositories import chats as chat_repo
from app.database.repositories import filters as filter_repo
from app.services import eventlog
from app.services import filters as filter_service


# ── Welcome / Goodbye ─────────────────────────────────────────────────

@Client.on_message(filters.command("welcome") & filters.group)
@require_chat_admin
@with_rate_limit()
async def welcome_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    db = db_session.get_db()
    if not rest:
        settings = await chat_repo.get_chat_settings(db, message.chat.id)
        current = (
            settings.welcome_message
            or "Welcome {user} to {chat}!"
        )
        await message.reply_text(
            f"👋 **Welcome message**\n\nCurrent: {current}\n\n"
            "Usage:\n`/welcome on|off`\n`/welcomemsg Welcome {user} to {chat}!`\n\n"
            "Variables: {user} {name} {username} {chat} {id}"
        )
        return

    state = rest.strip().lower()
    if state in ("on", "off"):
        enabled = state == "on"
        await chat_repo.update_chat_setting(db, message.chat.id, "welcome_enabled", enabled)
        await eventlog.persist_and_notify(
            client, db, message.chat.id, "settings_changed",
            admin_id=message.from_user.id,
            details={"welcome": "ON" if enabled else "OFF"},
        )
        await message.reply_text(f"👋 Welcome messages: {'🟢 ON' if enabled else '🔴 OFF'}")
        return
    await message.reply_text("⚠️ Usage: `/welcome on` or `/welcome off`")


@Client.on_message(filters.command("welcomemsg") & filters.group)
@require_chat_admin
@with_rate_limit()
async def welcomemsg_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    if not rest:
        await message.reply_text("⚠️ Usage: `/welcomemsg Welcome {user} to {chat}!`")
        return
    db = db_session.get_db()
    await chat_repo.update_chat_setting(db, message.chat.id, "welcome_message", rest)
    await eventlog.persist_and_notify(
        client, db, message.chat.id, "settings_changed",
        admin_id=message.from_user.id,
        details={"welcome_message": "updated"},
    )
    await message.reply_text(f"✅ Welcome message set:\n\n{rest}")


@Client.on_message(filters.command("goodbye") & filters.group)
@require_chat_admin
@with_rate_limit()
async def goodbye_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    db = db_session.get_db()
    if not rest:
        settings = await chat_repo.get_chat_settings(db, message.chat.id)
        current = settings.goodbye_message or "👋 {user} has left the group."
        await message.reply_text(
            f"👋 **Goodbye message**\n\nCurrent: {current}\n\n"
            "Usage: `/goodbye on|off`\n`/goodbyemsg 👋 {user} left.`"
        )
        return
    state = rest.strip().lower()
    if state in ("on", "off"):
        enabled = state == "on"
        await chat_repo.update_chat_setting(db, message.chat.id, "goodbye_enabled", enabled)
        await message.reply_text(f"👋 Goodbye messages: {'🟢 ON' if enabled else '🔴 OFF'}")
        return
    await message.reply_text("⚠️ Usage: `/goodbye on` or `/goodbye off`")


@Client.on_message(filters.command("goodbyemsg") & filters.group)
@require_chat_admin
@with_rate_limit()
async def goodbyemsg_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    if not rest:
        await message.reply_text("⚠️ Usage: `/goodbyemsg 👋 {user} left.`")
        return
    db = db_session.get_db()
    await chat_repo.update_chat_setting(db, message.chat.id, "goodbye_message", rest)
    await message.reply_text(f"✅ Goodbye message set:\n\n{rest}")


# ── Rules ─────────────────────────────────────────────────────────────

@Client.on_message(filters.command("rules") & filters.group)
@with_rate_limit()
async def rules_command(client: Client, message: Message) -> None:
    db = db_session.get_db()
    settings = await chat_repo.get_chat_settings(db, message.chat.id)
    if settings.rules:
        await message.reply_text(f"📜 **Group Rules**\n\n{settings.rules}")
    else:
        await message.reply_text("📜 No rules have been set yet for this group.")


@Client.on_message(filters.command("setrules") & filters.group)
@require_chat_admin
@with_rate_limit()
async def setrules_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    if not rest:
        await message.reply_text(
            "⚠️ Usage: `/setrules 1. No spam. 2. No scams.`"
        )
        return
    db = db_session.get_db()
    await chat_repo.update_chat_setting(db, message.chat.id, "rules", rest)
    await eventlog.persist_and_notify(
        client, db, message.chat.id, "settings_changed",
        admin_id=message.from_user.id,
        details={"rules": "updated"},
    )
    await message.reply_text("✅ Rules saved.")


# ── Log channel ──────────────────────────────────────────────────────

@Client.on_message(filters.command("setlogchannel") & filters.group)
@require_chat_admin
@with_rate_limit()
async def setlogchannel_command(client: Client, message: Message) -> None:
    reply = message.reply_to_message
    channel_id: int | None = None

    if reply and reply.forward_from_chat:
        channel_id = reply.forward_from_chat.id
    elif reply and reply.sender_chat:
        channel_id = reply.sender_chat.id
    else:
        await message.reply_text(
            "⚠️ Forward a message from your log channel, or reply to a channel post,\n"
            "then run /setlogchannel. Example:\n\n"
            "1. Create a channel.\n"
            "2. Add the bot as administrator.\n"
            "3. Forward a post from the channel here.\n"
            "4. Reply to that forward with /setlogchannel."
        )
        return

    db = db_session.get_db()
    await chat_repo.update_chat_setting(db, message.chat.id, "log_channel_id", channel_id)
    await chat_repo.update_chat_setting(db, message.chat.id, "log_enabled", True)
    await message.reply_text(
        f"✅ Log channel set to `{channel_id}`. Logging enabled."
    )


# ── Custom filters ───────────────────────────────────────────────────

@Client.on_message(filters.command("filter") & filters.group)
@require_chat_admin
@with_rate_limit()
async def filter_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    parts = rest.split(maxsplit=2)
    action = parts[0].lower() if parts else ""

    db = db_session.get_db()

    if action == "add" and len(parts) >= 3:
        pattern = parts[1]
        punish = parts[2].lower()
        if punish not in ("delete", "warn", "mute"):
            await message.reply_text("⚠️ Action must be delete, warn, or mute.")
            return
        if not filter_service.validate_pattern(pattern):
            await message.reply_text("⚠️ Invalid pattern.")
            return
        await filter_repo.add_filter(db, message.chat.id, pattern, punish)
        await eventlog.persist_and_notify(
            client, db, message.chat.id, "filter_added",
            admin_id=message.from_user.id,
            details={"pattern": pattern, "action": punish},
        )
        await message.reply_text(f"✅ Filter added: `{pattern}` → **{punish}**")
        return

    if action == "remove" and len(parts) >= 2:
        pattern = parts[1]
        removed = await filter_repo.remove_filter(db, message.chat.id, pattern)
        await eventlog.persist_and_notify(
            client, db, message.chat.id, "filter_removed",
            admin_id=message.from_user.id,
            details={"pattern": pattern},
        )
        await message.reply_text(
            f"✅ Removed filter `{pattern}`." if removed else f"⚠️ Filter `{pattern}` not found."
        )
        return

    if action == "list":
        filters_list = await filter_repo.list_filters(db, message.chat.id)
        if not filters_list:
            await message.reply_text("No custom filters set.")
            return
        lines = ["🗂 **Custom Filters**\n"]
        for f in filters_list:
            lines.append(f"• `{f.pattern}` → **{f.action}**")
        await message.reply_text("\n".join(lines))
        return

    await message.reply_text(
        "⚠️ Usage:\n"
        "/filter add <word> delete|warn|mute\n"
        "/filter remove <word>\n"
        "/filter list"
    )


# ── Misc info commands ───────────────────────────────────────────────

@Client.on_message(filters.command("id"))
@with_rate_limit()
async def id_command(client: Client, message: Message) -> None:
    lines = [f"Chat ID: `{message.chat.id}`"]
    if message.from_user:
        lines.append(f"Your ID: `{message.from_user.id}`")
    if message.reply_to_message and message.reply_to_message.from_user:
        lines.append(
            f"Replied user: `{message.reply_to_message.from_user.id}`"
        )
    await message.reply_text("\n".join(lines))


@Client.on_message(filters.command("info"))
@with_rate_limit()
async def info_command(client: Client, message: Message) -> None:
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    if not target:
        await message.reply_text("⚠️ No user found.")
        return
    await message.reply_text(
        f"**User info**\n\n"
        f"Name: {target.first_name or ''} {target.last_name or ''}\n"
        f"Username: @{target.username if target.username else '—'}\n"
        f"ID: `{target.id}`\n"
        f"Bot: {'Yes' if target.is_bot else 'No'}"
    )
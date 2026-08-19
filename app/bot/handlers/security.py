from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message

from app.bot.decorators import require_chat_admin, with_rate_limit
from app.bot.filters import group_approved
from app.bot.utils import split_command
from app.database import session as db_session
from app.database.repositories import chats as chat_repo
from app.services import antilink
from app.services import eventlog


async def _toggle(client: Client, message: Message, key: str, label: str) -> None:
    db = db_session.get_db()
    settings = await chat_repo.get_chat_settings(db, message.chat.id)
    new_value = not settings.__getattribute__(key + "_enabled")
    await chat_repo.update_chat_setting(db, message.chat.id, key + "_enabled", new_value)
    icon = "🟢 ON" if new_value else "🔴 OFF"
    await message.reply_text(f"{label}: {icon}")
    await eventlog.persist_and_notify(
        client, db, message.chat.id, "settings_changed",
        admin_id=message.from_user.id,
        details={f"{label}": icon},
    )


@Client.on_message(filters.command("antispam") & group_approved)
@require_chat_admin
@with_rate_limit()
async def antispam_command(client: Client, message: Message) -> None:
    await _toggle(client, message, "antispam", "🛡 Anti-Spam")


@Client.on_message(filters.command("antilink") & group_approved)
@require_chat_admin
@with_rate_limit()
async def antilink_command(client: Client, message: Message) -> None:
    await _toggle(client, message, "antilink", "🔗 Anti-Link")


@Client.on_message(filters.command("antiraid") & group_approved)
@require_chat_admin
@with_rate_limit()
async def antiraid_command(client: Client, message: Message) -> None:
    await _toggle(client, message, "antiraid", "💥 Anti-Raid")


@Client.on_message(filters.command("captcha") & group_approved)
@require_chat_admin
@with_rate_limit()
async def captcha_command(client: Client, message: Message) -> None:
    await _toggle(client, message, "captcha", "🧪 CAPTCHA")


@Client.on_message(filters.command("antibot") & group_approved)
@require_chat_admin
@with_rate_limit()
async def antibot_command(client: Client, message: Message) -> None:
    await _toggle(client, message, "antibot", "🤖 Anti-Bot")


@Client.on_message(filters.command("antiflood") & group_approved)
@require_chat_admin
@with_rate_limit()
async def antiflood_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    db = db_session.get_db()
    settings = await chat_repo.get_chat_settings(db, message.chat.id)

    if not rest:
        await message.reply_text(
            f"🌊 **Anti-Flood**\n\n"
            f"Limit: {settings.flood_limit} messages / {settings.flood_window}s\n"
            f"Action: {settings.flood_action}\n\n"
            "Usage: `/antiflood <messages> <seconds> <action>`\n"
            "Actions: warn, delete, mute, kick, ban\n"
            "Example: `/antiflood 8 10 mute`"
        )
        return

    parts = rest.split()
    if len(parts) < 2:
        await message.reply_text("⚠️ Usage: `/antiflood <messages> <seconds> <action>`")
        return

    try:
        limit = int(parts[0])
        window = int(parts[1])
    except ValueError:
        await message.reply_text("⚠️ Messages and seconds must be numbers.")
        return

    action = parts[2].lower() if len(parts) > 2 else settings.flood_action
    valid_actions = ("delete", "warn", "mute", "kick", "ban")
    if action not in valid_actions:
        await message.reply_text("⚠️ Invalid action. Use: " + ", ".join(valid_actions))
        return

    if limit < 2 or window < 1:
        await message.reply_text("⚠️ Limit must be >= 2 messages, window >= 1 second.")
        return

    await chat_repo.update_chat_setting(db, message.chat.id, "flood_limit", limit)
    await chat_repo.update_chat_setting(db, message.chat.id, "flood_window", window)
    await chat_repo.update_chat_setting(db, message.chat.id, "flood_action", action)
    await eventlog.persist_and_notify(
        client, db, message.chat.id, "settings_changed",
        admin_id=message.from_user.id,
        details={"anti_flood": f"{limit} msgs / {window}s -> {action}"},
    )
    await message.reply_text(
        f"🌊 Anti-Flood updated: **{limit}** messages / **{window}s** → **{action}**"
    )


@Client.on_message(filters.command("allowdomain") & group_approved)
@require_chat_admin
@with_rate_limit()
async def allowdomain_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    if not rest:
        await message.reply_text("⚠️ Usage: `/allowdomain youtube.com`")
        return
    domain = antilink.parse_domain(rest)
    db = db_session.get_db()
    settings = await chat_repo.get_chat_settings(db, message.chat.id)
    if domain not in settings.allow_domains:
        await chat_repo.update_chat_setting(
            db, message.chat.id, "allow_domains", settings.allow_domains + [domain]
        )
    await message.reply_text(f"✅ Allowed domain: `{domain}`")


@Client.on_message(filters.command("blockdomain") & group_approved)
@require_chat_admin
@with_rate_limit()
async def blockdomain_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    if not rest:
        await message.reply_text("⚠️ Usage: `/blockdomain example.com`")
        return
    domain = antilink.parse_domain(rest)
    db = db_session.get_db()
    settings = await chat_repo.get_chat_settings(db, message.chat.id)
    if domain not in settings.block_domains:
        await chat_repo.update_chat_setting(
            db, message.chat.id, "block_domains", settings.block_domains + [domain]
        )
    await message.reply_text(f"⛔ Blocked domain: `{domain}`")


@Client.on_message(filters.command("allowbot") & group_approved)
@require_chat_admin
@with_rate_limit()
async def allowbot_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    if not rest:
        await message.reply_text("⚠️ Usage: `/allowbot @examplebot`")
        return
    username = rest.strip().lstrip("@").lower()
    db = db_session.get_db()
    settings = await chat_repo.get_chat_settings(db, message.chat.id)
    if username not in settings.allow_bots:
        await chat_repo.update_chat_setting(
            db, message.chat.id, "allow_bots", settings.allow_bots + [username]
        )
    await message.reply_text(f"✅ Trusted bot: @{username}")


@Client.on_message(filters.command("spammode") & group_approved)
@require_chat_admin
@with_rate_limit()
async def spammode_command(client: Client, message: Message) -> None:
    _, rest = split_command(message)
    valid = ("monitor", "delete", "warn", "mute", "ban")
    if not rest or rest.lower() not in valid:
        await message.reply_text(
            "⚠️ Usage: `/spammode monitor|delete|warn|mute|ban`\n\n"
            "`monitor` only logs, never punishes."
        )
        return
    db = db_session.get_db()
    await chat_repo.update_chat_setting(db, message.chat.id, "spam_mode", rest.lower())
    await message.reply_text(f"✅ Spam mode set to **{rest.lower()}**")
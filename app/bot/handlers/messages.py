from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message

from app.bot.filters import group_approved, is_approved
from app.bot.utils import is_command
from app.database import session as db_session
from app.database.repositories import chats as chat_repo
from app.database.repositories import filters as filter_repo
from app.services import antiflood, antilink, antispam, enforcer
from app.services import filters as filter_service
from app.services import permissions as perms
from app.services import redis as redis_service


async def _maintenance_mode() -> bool:
    try:
        return bool(await redis_service.get_redis().get("maintenance"))
    except Exception:
        return False


# ── Unapproved chat gate ─────────────────────────────────────────────
@Client.on_message(filters.group & ~is_approved, group=0)
async def unapproved_gate(client: Client, message: Message) -> None:
    if await _maintenance_mode():
        return
    if not is_command(message):
        return
    try:
        await message.reply_text(
            "⚠️ **Not Approved**\n\n"
            "This chat is not approved to use GuardianTG.\n\n"
            "Please contact the group administrator or the bot owner "
            "to get this chat approved first."
        )
    except Exception:
        pass


# ── Main security engine ─────────────────────────────────────────────
@Client.on_message(group_approved & ~filters.command("start"), group=0)
async def security_engine(client: Client, message: Message) -> None:
    if await _maintenance_mode():
        return
    if not message.from_user:
        return
    if is_command(message):
        return

    me = await client.get_me()
    if message.from_user.id == me.id:
        return

    text = message.text or message.caption or ""
    db = db_session.get_db()
    settings = await chat_repo.get_chat_settings(db, message.chat.id)

    # Admins: keep their message, attach the link as a designed button.
    if await perms.is_chat_admin(client, message.chat.id, message.from_user.id):
        if settings.antilink_enabled and text:
            links = antispam.extract_links(text)
            if links:
                try:
                    await message.reply_text(
                        "🔗 Link posted by an admin:",
                        reply_markup=antilink.build_link_keyboard(links),
                    )
                except Exception:
                    pass
        return

    user = message.from_user
    delete_ids = [message.id]
    actions: list[str] = []
    reasons: list[str] = []

    # ── Anti-flood ──────────────────────────────────────────────
    if settings.antiflood_enabled:
        try:
            count = await antiflood.check_flood(
                message.chat.id, user.id, message.id,
                settings.flood_limit, settings.flood_window,
            )
            if count > settings.flood_limit:
                actions.append(settings.flood_action)
                reasons.append("Flooding")
                delete_ids.extend(
                    await antiflood.get_flood_message_ids(message.chat.id, user.id)
                )
        except Exception:
            pass

    # ── Anti-spam scoring ───────────────────────────────────────
    if settings.antispam_enabled:
        try:
            scan = await antispam.scan_message(
                message.chat.id, user.id, text, settings
            )
            if scan.score >= settings.spam_score_threshold:
                actions.append(settings.spam_mode)
                reasons.extend(scan.reasons)
        except Exception:
            pass

    # ── Anti-link ───────────────────────────────────────────────
    if settings.antilink_enabled and text:
        try:
            decision = antilink.decide(text, settings)
            if decision.blocked:
                actions.append("delete")
                reasons.append(f"Link blocked: {decision.reason}")
        except Exception:
            pass

    # ── Profanity + custom filters ──────────────────────────────
    if settings.profanity_enabled and text:
        try:
            custom_filters = await filter_repo.list_filters(
                db, message.chat.id, enabled_only=True
            )
            match = filter_service.check_text(text, custom_filters)
            if match is None:
                match = filter_service.check_builtin(text)
            if match:
                if isinstance(match, filter_service.FilterMatch):
                    actions.append(match.filter.action)
                    reasons.append(f"Matched filter: {match.pattern}")
                else:
                    actions.append("delete")
                    reasons.append(f"Toxic content ({match})")
        except Exception:
            pass

    # ── Apply the strongest triggered action ────────────────────
    if actions:
        chosen = enforcer.choose_action(*actions)
        try:
            await enforcer.enforce(
                client, db, message.chat.id, user, chosen,
                "; ".join(dict.fromkeys(reasons)),
                message=message,
                delete_ids=list(dict.fromkeys(delete_ids))[:100],
            )
        except Exception:
            pass
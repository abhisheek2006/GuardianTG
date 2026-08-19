from __future__ import annotations

from typing import Optional

from motor.core import AgnosticDatabase
from pyrogram import Client
from pyrogram.types import Message, User

from app.database.repositories import chats as chat_repo
from app.services import antiflood, moderation
from app.services import eventlog

# Map human action names to a rank used for "least aggressive wins"
# when multiple signals fire for one message.
ACTION_RANK = {"monitor": 0, "delete": 1, "warn": 2, "mute": 3, "kick": 4, "ban": 5}


async def enforce(
    client: Client,
    db: AgnosticDatabase,
    chat_id: int,
    user: User,
    action: str,
    reason: str,
    message: Optional[Message] = None,
    delete_ids: Optional[list[int]] = None,
) -> None:
    """Apply a security action (delete/warn/mute/kick/ban) to `user`."""
    action = (action or "monitor").lower()
    if action not in ACTION_RANK:
        action = "monitor"

    settings = await chat_repo.get_chat_settings(db, chat_id)

    # monitor mode: log only, never punish.
    if action == "monitor":
        await eventlog.persist_and_notify(
            client, db, chat_id, "spam_detected",
            user_id=user.id, message_id=message.id if message else None,
            details={"signal": reason, "action": "monitored"},
        )
        return

    # Always remove the offending message(s) unless explicitly warn-only.
    if delete_ids and action != "warn":
        try:
            await client.delete_messages(chat_id, delete_ids[:100])
        except Exception:
            pass

    admin = await client.get_me()

    if action == "delete":
        await eventlog.persist_and_notify(
            client, db, chat_id, "spam_detected",
            user_id=user.id, message_id=message.id if message else None,
            details={"signal": reason, "action": "deleted"},
        )

    elif action == "warn":
        if message:
            await moderation.warn_user(
                client, db, chat_id, user, admin, reason, message
            )

    elif action == "mute":
        if await moderation.is_protected(client, chat_id, user.id):
            return
        duration = settings.mute_duration
        await moderation.mute_user(
            client, db, chat_id, user.id, admin.id, duration,
            reason=reason, message=message,
        )

    elif action == "kick":
        if await moderation.is_protected(client, chat_id, user.id):
            return
        await moderation.kick_user(
            client, db, chat_id, user, admin, reason, message or (await _fake_message(client, chat_id, user))
        )

    elif action == "ban":
        if await moderation.is_protected(client, chat_id, user.id):
            return
        await moderation.ban_user(
            client, db, chat_id, user, admin, reason, message or (await _fake_message(client, chat_id, user))
        )

    await antiflood.clear_flood(chat_id, user.id)


async def _fake_message(client: Client, chat_id: int, user: User) -> Message:
    """A synthetic message used only as a reply target when no real message exists."""
    try:
        return await client.send_message(chat_id, f"⚠️ Automatic action against {user.id}")
    except Exception:
        # Fallback: a local Message object is not constructible safely here;
        # callers only use it for .reply_text/.chat.id, so pass None-guard upstream.
        raise RuntimeError("no message context")


def choose_action(*actions: str) -> str:
    """Pick the most severe action from the signals that fired."""
    best = "monitor"
    for action in actions:
        if ACTION_RANK.get(action, 0) > ACTION_RANK.get(best, 0):
            best = action
    return best
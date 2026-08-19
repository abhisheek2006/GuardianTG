from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from app.database import session as db_session
from app.database.repositories import chats as chat_repo
from app.services import antiraid, captcha, eventlog, moderation
from app.services import permissions as perms


@Client.on_callback_query(filters.regex(r"^cap:"), group=0)
async def captcha_answer_callback(client: Client, callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer("Could not verify your identity.", show_alert=True)
        return

    try:
        answer = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer("Invalid answer.", show_alert=True)
        return

    user = callback.from_user
    chat_id = callback.message.chat.id
    db = db_session.get_db()
    settings = await chat_repo.get_chat_settings(db, chat_id)

    success, reason, remaining = await captcha.verify_answer(
        chat_id, user.id, answer, settings.captcha_max_attempts
    )

    if success:
        if await perms.can_restrict(client, chat_id):
            try:
                await client.restrict_chat_member(
                    chat_id, user.id, moderation.FULL_PERMISSIONS
                )
            except Exception:
                pass
        await eventlog.persist_and_notify(
            client, db, chat_id, "captcha_passed",
            user_id=user.id,
        )
        await callback.answer("✅ Verified! Welcome to the group.")
        try:
            await callback.message.edit_text(
                f"✅ **{user.first_name or 'User'} verified successfully.**\nWelcome to the group!"
            )
        except Exception:
            pass
        return

    if reason == "wrong":
        await callback.answer(
            f"❌ Wrong answer. {remaining} attempts left.", show_alert=True
        )
        return

    # Expired or attempts exhausted -> remove the user.
    await antiraid.record_captcha_failure(chat_id)
    await eventlog.persist_and_notify(
        client, db, chat_id, "captcha_failure",
        user_id=user.id,
        details={"reason": reason.replace("_", " ")},
    )

    if await perms.can_restrict(client, chat_id):
        try:
            await client.ban_chat_member(chat_id, user.id)
            await client.unban_chat_member(chat_id, user.id)
        except Exception:
            pass

    if reason == "expired":
        await callback.answer("⏳ Verification expired. You can rejoin to try again.", show_alert=True)
        await callback.message.edit_text(
            "⏳ **Verification expired.**\nYou can rejoin to try again."
        )
    else:
        await callback.answer("❌ Too many attempts. You were removed.", show_alert=True)
        await callback.message.edit_text(
            "❌ **Verification failed.** Too many attempts. You were removed."
        )
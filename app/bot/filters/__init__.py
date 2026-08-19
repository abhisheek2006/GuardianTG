from __future__ import annotations

from pyrogram import filters as _pyro_filters

from app.core.config import get_settings


async def _chat_is_approved(_filter: object, client: object, update: object) -> bool:
    chat_type = getattr(getattr(update, "chat", None), "type", None)
    if chat_type in ("private", "bot"):
        return True

    user_id = getattr(getattr(update, "from_user", None), "id", 0)
    if get_settings().is_sudo(user_id):
        return True

    chat_id = getattr(getattr(update, "chat", None), "id", None)
    if chat_id is None:
        return False

    from app.database import session as db_session
    from app.services import approval

    try:
        return await approval.is_approved(db_session.get_db(), chat_id, use_cache=True)
    except Exception:
        # Fail open on infra errors: never brick a chat because of a hiccup.
        return True


is_approved = _pyro_filters.create(_chat_is_approved, "ChatApprovedFilter")

# Approved groups only (used by all group command handlers).
group_approved = _pyro_filters.group & is_approved

# Approved groups only, excluding the bot's own messages and commands.
group_text_approved = _pyro_filters.group & is_approved & _pyro_filters.text
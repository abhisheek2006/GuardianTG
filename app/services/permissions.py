from __future__ import annotations

from typing import Optional

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatMember, ChatPrivileges

from app.core.config import get_settings
from app.services import redis as redis_service

ADMIN_CACHE_TTL = 60  # seconds
BOT_CACHE_TTL = 60


async def is_owner(user_id: int) -> bool:
    return get_settings().is_owner(user_id)


async def is_sudo(user_id: int) -> bool:
    return get_settings().is_sudo(user_id)


async def is_chat_admin(client: Client, chat_id: int, user_id: int) -> bool:
    """Verify admin status through Telegram (never trust supplied IDs)."""
    if await is_sudo(user_id):
        return True

    cache_key = f"admins:{chat_id}"
    cached = await redis_service.json_get(cache_key)
    if cached is not None:
        return user_id in cached

    try:
        admins = await get_chat_admins(client, chat_id)
    except Exception:
        return False

    await redis_service.json_set(cache_key, list(admins), ex=ADMIN_CACHE_TTL)
    return user_id in admins


async def get_chat_admins(client: Client, chat_id: int) -> set[int]:
    """Fetch full admin list from Telegram for a chat."""
    admins: set[int] = set()
    async for member in client.get_chat_members(chat_id):
        if member.user and member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        ):
            admins.add(member.user.id)
    return admins


async def get_bot_member(client: Client, chat_id: int) -> Optional[ChatMember]:
    """Bot's own ChatMember in the chat (cached)."""
    me = await client.get_me()
    cache_key = f"botmember:{chat_id}"
    cached = await redis_service.json_get(cache_key)
    if cached is not None:
        return ChatMember(
            user=me, status=cached["status"], privileges=cached.get("privileges")
        )
    member = await client.get_chat_member(chat_id, me.id)
    await redis_service.json_set(
        cache_key,
        {"status": member.status, "privileges": member.privileges.__dict__ if member.privileges else None},
        ex=BOT_CACHE_TTL,
    )
    return member


async def _bot_rights(client: Client, chat_id: int) -> ChatPrivileges:
    member = await get_bot_member(client, chat_id)
    if member is None:
        return ChatPrivileges()
    if member.status == ChatMemberStatus.OWNER:
        return ChatPrivileges(can_delete_messages=True, can_restrict_members=True)
    return member.privileges or ChatPrivileges()


async def is_bot_admin(client: Client, chat_id: int) -> bool:
    member = await get_bot_member(client, chat_id)
    return member is not None and member.status in (
        ChatMemberStatus.OWNER,
        ChatMemberStatus.ADMINISTRATOR,
    )


async def can_delete(client: Client, chat_id: int) -> bool:
    return bool((await _bot_rights(client, chat_id)).can_delete_messages)


async def can_restrict(client: Client, chat_id: int) -> bool:
    return bool((await _bot_rights(client, chat_id)).can_restrict_members)


async def can_ban(client: Client, chat_id: int) -> bool:
    return await can_restrict(client, chat_id)


async def can_invite(client: Client, chat_id: int) -> bool:
    return bool((await _bot_rights(client, chat_id)).can_invite_users)


async def can_pin(client: Client, chat_id: int) -> bool:
    return bool((await _bot_rights(client, chat_id)).can_pin_messages)


async def missing_permissions(client: Client, chat_id: int) -> list[str]:
    """Returns the human-readable list of required-but-missing permissions."""
    missing: list[str] = []
    if not await can_delete(client, chat_id):
        missing.append("Delete messages")
    if not await can_restrict(client, chat_id):
        missing.append("Restrict members")
    if not await can_ban(client, chat_id):
        missing.append("Ban users")
    return missing
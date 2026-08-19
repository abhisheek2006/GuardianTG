from __future__ import annotations

from functools import wraps
from typing import Callable, TypeVar

from pyrogram import Client
from pyrogram.types import CallbackQuery, Message

from app.services import permissions as perms
from app.services import redis as redis_service

F = TypeVar("F", bound=Callable)


def get_user_id(update: Message | CallbackQuery) -> int | None:
    return update.from_user.id if update.from_user else None


async def _deny(update: Message | CallbackQuery, text: str) -> None:
    if isinstance(update, CallbackQuery):
        await update.answer(text, show_alert=True)
    else:
        await update.reply_text(text)


def require_owner(func: F) -> F:
    """Only the configured OWNER_ID (or sudo ids) may run this command."""

    @wraps(func)
    async def wrapper(client: Client, update: Message | CallbackQuery) -> None:
        user_id = get_user_id(update)
        if not user_id or not await perms.is_owner(user_id):
            await _deny(update, "🚫 This command is restricted to the bot owner.")
            return
        await func(client, update)

    return wrapper  # type: ignore[return-value]


def require_chat_admin(func: F) -> F:
    """Only chat administrators (or sudo users) may run this command."""

    @wraps(func)
    async def wrapper(client: Client, message: Message) -> None:
        user_id = get_user_id(message)
        if not user_id:
            await _deny(message, "🚫 Could not verify your identity.")
            return
        if not await perms.is_chat_admin(client, message.chat.id, user_id):
            await _deny(message, "🚫 This command requires administrator rights.")
            return
        await func(client, message)

    return wrapper  # type: ignore[return-value]


def require_sudo(func: F) -> F:
    """Owner or listed sudo users only."""

    @wraps(func)
    async def wrapper(client: Client, update: Message | CallbackQuery) -> None:
        user_id = get_user_id(update)
        if not user_id or not await perms.is_sudo(user_id):
            await _deny(update, "🚫 This command is restricted to trusted users.")
            return
        await func(client, update)

    return wrapper  # type: ignore[return-value]


def with_rate_limit(limit: int | None = None, window: int | None = None) -> Callable[[F], F]:
    """Apply the Redis-backed rate limit and answer silently when exceeded."""

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(client: Client, update: Message | CallbackQuery) -> None:
            user_id = get_user_id(update)
            if user_id is None:
                return await func(client, update)
            rl_limit = limit
            rl_window = window
            from app.core.config import get_settings

            settings = get_settings()
            rl_limit = rl_limit or settings.rate_limit
            rl_window = rl_window or settings.rate_window
            key = f"rl:{user_id}:{func.__name__}"
            allowed, count = await redis_service.allow(key, rl_limit, rl_window)
            if not allowed:
                await _deny(
                    update,
                    "⏳ Slow down! You are using commands too fast. Please wait a moment.",
                )
                return
            await func(client, update)

        return wrapper  # type: ignore[return-value]

    return decorator
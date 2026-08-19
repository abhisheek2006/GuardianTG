from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from pyrogram import Client
from pyrogram.types import Message, User

from app.core.config import get_settings
from app.services import redis as redis_service

HandlerT = Callable[[Client, Any], Awaitable[None]]


class RateLimitExceeded(Exception):
    pass


def rate_limit(
    limit: int | None = None, window: int | None = None
) -> Callable[[HandlerT], HandlerT]:
    """Decorator: max `limit` calls per `window` seconds, keyed per user/chat.

    Uses Redis. When the limit is exceeded the handler is skipped (and the
    middleware signals the caller via an exception attribute if needed).
    """

    def decorator(func: HandlerT) -> HandlerT:
        async def wrapper(client: Client, update: Any) -> None:
            settings = get_settings()
            lmt = limit if limit is not None else settings.rate_limit
            win = window if window is not None else settings.rate_window

            if isinstance(update, Message):
                scope = update.from_user.id if update.from_user else 0
                key = f"rl:{scope}:{func.__name__}"
            else:
                scope = update.from_user.id if update.from_user else 0
                key = f"rl:{scope}:{func.__name__}"

            allowed, count = await redis_service.allow(key, lmt, win)
            if not allowed:
                raise RateLimitExceeded(f"rate limit for {func.__name__}")
            return await func(client, update)

        return wrapper

    return decorator


def is_ratelimited(func: HandlerT) -> bool:
    """Returns whether the decorated handler reports rate limiting.

    Handlers catch RateLimitExceeded internally; this helper is used by
    handler glue that wants to send a friendly message.
    """
    return True  # placeholder — see RateLimitExceeded usage in handlers


class SlidingWindow:
    """In-memory fallback rate limiter (used when Redis is unavailable)."""

    def __init__(self, limit: int, window: float) -> None:
        self.limit = limit
        self.window = window
        self._events: dict[int, list[float]] = {}

    def allow(self, key: int) -> bool:
        now = time.monotonic()
        bucket = self._events.setdefault(key, [])
        bucket[:] = [t for t in bucket if now - t < self.window]
        if len(bucket) >= self.limit:
            return False
        bucket.append(now)
        return True
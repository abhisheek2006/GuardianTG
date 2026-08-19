from __future__ import annotations

from typing import Optional

from app.services import redis as redis_service

JOIN_LIST_TTL = 1800


async def record_join(chat_id: int, user_id: int, window: int) -> int:
    key = f"joins:{chat_id}"
    count = await redis_service.incr_window(key, window)
    list_key = f"joinlist:{chat_id}"
    r = redis_service.get_redis()
    await r.rpush(list_key, user_id)
    await r.expire(list_key, JOIN_LIST_TTL)
    return count


async def recent_join_count(chat_id: int, window: int) -> int:
    key = f"joins:{chat_id}"
    raw = await redis_service.get_redis().get(key)
    return int(raw) if raw else 0


async def recent_joins(chat_id: int, limit: int = 30) -> list[int]:
    raw = await redis_service.get_redis().lrange(
        f"joinlist:{chat_id}", -limit, -1
    )
    return [int(x) for x in raw]


async def set_lockdown(chat_id: int, active: bool, ttl: int = 900) -> None:
    key = f"lockdown:{chat_id}"
    r = redis_service.get_redis()
    if active:
        await r.set(key, "1", ex=ttl)
    else:
        await r.delete(key)


async def is_lockdown(chat_id: int) -> bool:
    return bool(await redis_service.get_redis().exists(f"lockdown:{chat_id}"))


async def is_raid(chat_id: int, threshold: int, window: int) -> bool:
    count = await recent_join_count(chat_id, window)
    return count >= threshold


async def recent_captcha_failures(chat_id: int) -> int:
    raw = await redis_service.get_redis().get(f"captcha_fail:{chat_id}")
    return int(raw) if raw else 0


async def record_captcha_failure(chat_id: int, window: int = 600) -> int:
    return await redis_service.incr_window(f"captcha_fail:{chat_id}", window)


async def get_recent_captcha_failure_window(chat_id: int) -> Optional[int]:
    return await recent_captcha_failures(chat_id)
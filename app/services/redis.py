from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.config import get_settings

_redis: Optional[aioredis.Redis] = None


async def connect() -> aioredis.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
        await _redis.ping()
    return _redis


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis not connected. Call connect() at startup first.")
    return _redis


async def close() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None


async def ping() -> bool:
    try:
        await get_redis().ping()
        return True
    except Exception:
        return False


# ── Small typed helpers used by the security engine ────────────────

async def json_set(key: str, value: Any, ex: Optional[int] = None) -> None:
    await get_redis().set(key, json.dumps(value, default=str), ex=ex)


async def json_get(key: str) -> Optional[Any]:
    raw = await get_redis().get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def incr_window(key: str, window: int) -> int:
    """Increment a counter key with TTL = window. Returns new count."""
    pipe = get_redis().pipeline()
    pipe.incr(key)
    pipe.expire(key, window)
    results = await pipe.execute()
    return int(results[0])


async def allow(key: str, limit: int, window: int) -> tuple[bool, int]:
    """Rate limit. Returns (allowed, current_count)."""
    count = await incr_window(key, window)
    return count <= limit, count
from __future__ import annotations

from app.services import redis as redis_service

FLOOD_KEY_TTL = 600  # keep the message-id list around long enough to act


async def check_flood(
    chat_id: int, user_id: int, message_id: int, limit: int, window: int
) -> int:
    """Count messages from `user_id` within `window` seconds.

    Returns the current count after counting this message. When count > limit
    a flood is detected.
    """
    key = f"flood:{chat_id}:{user_id}"
    count = await redis_service.incr_window(key, window)

    msg_key = f"floodmsgs:{chat_id}:{user_id}"
    await redis_service.get_redis().rpush(msg_key, message_id)
    await redis_service.get_redis().expire(msg_key, FLOOD_KEY_TTL)
    return count


async def get_flood_message_ids(chat_id: int, user_id: int) -> list[int]:
    raw = await redis_service.get_redis().lrange(
        f"floodmsgs:{chat_id}:{user_id}", 0, -1
    )
    return [int(x) for x in raw]


async def clear_flood(chat_id: int, user_id: int) -> None:
    pipe = redis_service.get_redis().pipeline()
    pipe.delete(f"flood:{chat_id}:{user_id}")
    pipe.delete(f"floodmsgs:{chat_id}:{user_id}")
    await pipe.execute()
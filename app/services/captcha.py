from __future__ import annotations

import random
import time
from typing import Optional

from app.services import redis as redis_service

CAPTCHA_SESSION_TTL = 600


def generate_challenge() -> tuple[str, int, list[int]]:
    """Generate a random arithmetic challenge.

    Returns (question, answer, options). Options are shuffled.
    """
    if random.random() < 0.3:
        a = random.randint(10, 99)
        b = random.randint(10, 99)
        answer = a + b
        question = f"{a} + {b} = ?"
    else:
        a = random.randint(2, 20)
        b = random.randint(2, 20)
        answer = a * b
        question = f"{a} × {b} = ?"

    options = {answer}
    while len(options) < 4:
        delta = random.randint(1, 9) * random.choice([-1, 1])
        options.add(max(1, answer + delta))
    options_list = list(options)
    random.shuffle(options_list)
    return question, answer, options_list


def _session_key(chat_id: int, user_id: int) -> str:
    return f"captcha:{chat_id}:{user_id}"


async def create_session(
    chat_id: int, user_id: int, question: str, answer: int, timeout: int
) -> dict:
    payload = {
        "question": question,
        "answer": answer,
        "attempts": 0,
        "expires_at": time.time() + timeout,
    }
    await redis_service.json_set(_session_key(chat_id, user_id), payload, ex=CAPTCHA_SESSION_TTL)
    return payload


async def get_session(chat_id: int, user_id: int) -> Optional[dict]:
    return await redis_service.json_get(_session_key(chat_id, user_id))


async def verify_answer(
    chat_id: int, user_id: int, answer: int, max_attempts: int
) -> tuple[bool, Optional[str], Optional[int]]:
    """Verify a CAPTCHA answer.

    Returns (success, reason, remaining_attempts).
    reason is None on success, otherwise 'expired' or 'wrong'.
    """
    session = await get_session(chat_id, user_id)
    if session is None:
        return False, "expired", 0

    if time.time() > session["expires_at"]:
        await delete_session(chat_id, user_id)
        return False, "expired", 0

    if int(answer) == int(session["answer"]):
        await delete_session(chat_id, user_id)
        return True, None, 0

    session["attempts"] += 1
    remaining = max_attempts - session["attempts"]
    await redis_service.json_set(_session_key(chat_id, user_id), session, ex=CAPTCHA_SESSION_TTL)
    if remaining <= 0:
        await delete_session(chat_id, user_id)
        return False, "attempts_exhausted", 0
    return False, "wrong", remaining


async def delete_session(chat_id: int, user_id: int) -> None:
    await redis_service.get_redis().delete(_session_key(chat_id, user_id))


async def cleanup_expired() -> int:
    """Remove all expired captcha sessions (called periodically)."""
    removed = 0
    r = redis_service.get_redis()
    async for key in r.scan_iter(match="captcha:*"):
        session = await redis_service.json_get(key)
        if session and time.time() > session["expires_at"]:
            await r.delete(key)
            removed += 1
    return removed
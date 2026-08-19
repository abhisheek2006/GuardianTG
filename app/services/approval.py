from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from motor.core import AgnosticDatabase

from app.services import redis as redis_service

APPROVAL_CACHE_TTL = 60


async def approve(
    db: AgnosticDatabase, chat_id: int, days: int, approved_by: int
) -> datetime:
    expires = datetime.now(timezone.utc) + timedelta(days=days)
    await db.approvals.update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "chat_id": chat_id,
                "expires_at": expires,
                "approved_by": approved_by,
            },
            "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )
    await _cache_set(chat_id, True, expires)
    return expires


async def revoke(db: AgnosticDatabase, chat_id: int) -> None:
    await db.approvals.delete_one({"chat_id": chat_id})
    await _cache_set(chat_id, False)


async def get_expiry(db: AgnosticDatabase, chat_id: int) -> Optional[datetime]:
    doc = await db.approvals.find_one({"chat_id": chat_id})
    return doc.get("expires_at") if doc else None


async def is_approved(
    db: AgnosticDatabase, chat_id: int, use_cache: bool = True
) -> bool:
    if use_cache:
        cached = await redis_service.get_redis().get(f"approved:{chat_id}")
        if cached == "1":
            return True
        if cached == "0":
            return False

    doc = await db.approvals.find_one({"chat_id": chat_id})
    if not doc:
        await _cache_set(chat_id, False)
        return False

    expires = doc.get("expires_at")
    if expires is None or expires > datetime.now(timezone.utc):
        await _cache_set(chat_id, True, expires)
        return True

    await db.approvals.delete_one({"chat_id": chat_id})
    await _cache_set(chat_id, False)
    return False


async def list_approved(db: AgnosticDatabase, limit: int = 100) -> list[dict]:
    cursor = db.approvals.find({}).sort("expires_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def _cache_set(chat_id: int, value: bool, expires: Optional[datetime] = None) -> None:
    r = redis_service.get_redis()
    key = f"approved:{chat_id}"
    if value and expires:
        ttl = max(1, int((expires - datetime.now(timezone.utc)).total_seconds()))
        await r.set(key, "1", ex=min(ttl, APPROVAL_CACHE_TTL))
    elif value:
        await r.set(key, "1", ex=APPROVAL_CACHE_TTL)
    else:
        await r.set(key, "0", ex=APPROVAL_CACHE_TTL)
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from motor.core import AgnosticDatabase

from app.database.models import BannedUserDoc, ModerationActionDoc
from app.database.models.base import utcnow


async def log_action(
    db: AgnosticDatabase,
    chat_id: int,
    target_user_id: int,
    action: str,
    reason: Optional[str] = None,
    admin_user_id: Optional[int] = None,
    expires_at: Optional[datetime] = None,
) -> ModerationActionDoc:
    doc = ModerationActionDoc(
        chat_id=chat_id,
        target_user_id=target_user_id,
        action=action,
        reason=reason,
        admin_user_id=admin_user_id,
        expires_at=expires_at,
    )
    await db.moderation_actions.insert_one(doc.model_dump())
    return doc


async def ban_user(
    db: AgnosticDatabase,
    chat_id: int,
    user_id: int,
    reason: Optional[str],
    banned_by: int,
) -> BannedUserDoc:
    doc = BannedUserDoc(
        chat_id=chat_id, user_id=user_id, reason=reason, banned_by=banned_by
    )
    await db.banned_users.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$setOnInsert": doc.model_dump()},
        upsert=True,
    )
    return doc


async def unban_user(db: AgnosticDatabase, chat_id: int, user_id: int) -> int:
    result = await db.banned_users.delete_one({"chat_id": chat_id, "user_id": user_id})
    return result.deleted_count


async def is_banned(db: AgnosticDatabase, chat_id: int, user_id: int) -> bool:
    return await db.banned_users.count_documents(
        {"chat_id": chat_id, "user_id": user_id}
    ) > 0


async def find_expiring_mutes(
    db: AgnosticDatabase, before: datetime, limit: int = 500
) -> list[ModerationActionDoc]:
    cursor = (
        db.moderation_actions.find(
            {
                "action": "mute",
                "expires_at": {"$ne": None, "$lte": before},
            }
        )
        .sort("expires_at", 1)
        .limit(limit)
    )
    return [ModerationActionDoc.from_doc(d) for d in await cursor.to_list(length=limit)]


async def action_counts(db: AgnosticDatabase, chat_id: int) -> dict[str, int]:
    """Count moderation actions grouped by type for a chat."""
    pipeline = [
        {"$match": {"chat_id": chat_id}},
        {"$group": {"_id": "$action", "count": {"$sum": 1}}},
    ]
    counts: dict[str, int] = {}
    async for row in db.moderation_actions.aggregate(pipeline):
        counts[row["_id"]] = row["count"]
    return counts


async def total_action_counts(db: AgnosticDatabase) -> dict[str, int]:
    pipeline = [{"$group": {"_id": "$action", "count": {"$sum": 1}}}]
    counts: dict[str, int] = {}
    async for row in db.moderation_actions.aggregate(pipeline):
        counts[row["_id"]] = row["count"]
    return counts


async def upsert_banned_without_duplicate(
    db: AgnosticDatabase, chat_id: int, user_id: int
) -> None:
    now = utcnow()
    await db.banned_users.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$setOnInsert": {"chat_id": chat_id, "user_id": user_id, "created_at": now}},
        upsert=True,
    )
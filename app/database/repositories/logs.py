from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from motor.core import AgnosticDatabase

from app.database.models import LogEntryDoc


async def add_log(
    db: AgnosticDatabase,
    chat_id: int,
    event_type: str,
    user_id: Optional[int] = None,
    admin_id: Optional[int] = None,
    message_id: Optional[int] = None,
    details: Optional[dict] = None,
) -> LogEntryDoc:
    doc = LogEntryDoc(
        chat_id=chat_id,
        event_type=event_type,
        user_id=user_id,
        admin_id=admin_id,
        message_id=message_id,
        details=details,
    )
    await db.logs.insert_one(doc.model_dump())
    return doc


async def recent_logs(
    db: AgnosticDatabase, chat_id: int, limit: int = 50
) -> list[LogEntryDoc]:
    cursor = db.logs.find({"chat_id": chat_id}).sort("created_at", -1).limit(limit)
    return [LogEntryDoc.from_doc(d) for d in await cursor.to_list(length=limit)]


async def purge_old_logs(db: AgnosticDatabase, retention_days: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = await db.logs.delete_many({"created_at": {"$lt": cutoff}})
    return result.deleted_count


async def count_events(db: AgnosticDatabase, chat_id: int, event_type: str) -> int:
    return await db.logs.count_documents({"chat_id": chat_id, "event_type": event_type})


async def global_event_counts(
    db: AgnosticDatabase, since: Optional[datetime] = None
) -> dict[str, int]:
    match: dict = {}
    if since is not None:
        match["created_at"] = {"$gte": since}
    pipeline = [{"$match": match}, {"$group": {"_id": "$event_type", "count": {"$sum": 1}}}]
    counts: dict[str, int] = {}
    async for row in db.logs.aggregate(pipeline):
        counts[row["_id"]] = row["count"]
    return counts


async def count_chats(db: AgnosticDatabase) -> int:
    return await db.chats.count_documents({})


async def count_logs(db: AgnosticDatabase) -> int:
    return await db.logs.count_documents({})
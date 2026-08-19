from __future__ import annotations

from typing import Optional

from motor.core import AgnosticDatabase

from app.database.models import CustomFilterDoc


async def list_filters(
    db: AgnosticDatabase, chat_id: int, enabled_only: bool = False
) -> list[CustomFilterDoc]:
    query: dict = {"chat_id": chat_id}
    if enabled_only:
        query["enabled"] = True
    cursor = db.filters.find(query).sort("created_at", 1)
    docs = await cursor.to_list(length=500)
    return [CustomFilterDoc.from_doc(d) for d in docs]


async def add_filter(
    db: AgnosticDatabase,
    chat_id: int,
    pattern: str,
    action: str,
    filter_type: str = "profanity",
) -> CustomFilterDoc:
    doc = CustomFilterDoc(
        chat_id=chat_id, pattern=pattern, action=action, filter_type=filter_type
    )
    await db.filters.update_one(
        {"chat_id": chat_id, "pattern": pattern.lower()},
        {"$set": doc.model_dump(exclude={"pattern"}), "$setOnInsert": {"pattern": pattern.lower()}},
        upsert=True,
    )
    return doc


async def remove_filter(db: AgnosticDatabase, chat_id: int, pattern: str) -> int:
    result = await db.filters.delete_one(
        {"chat_id": chat_id, "pattern": pattern.lower()}
    )
    return result.deleted_count
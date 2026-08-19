from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from motor.core import AgnosticDatabase

from app.database.models import WarningDoc


async def add_warning(
    db: AgnosticDatabase,
    chat_id: int,
    user_id: int,
    reason: str,
    issued_by: int,
    expires_at: Optional[datetime] = None,
) -> WarningDoc:
    doc = WarningDoc(
        chat_id=chat_id,
        user_id=user_id,
        reason=reason,
        issued_by=issued_by,
        expires_at=expires_at,
    )
    await db.warnings.insert_one(doc.model_dump())
    return doc


async def active_warning_count(db: AgnosticDatabase, chat_id: int, user_id: int) -> int:
    now = datetime.now(timezone.utc)
    query = {
        "chat_id": chat_id,
        "user_id": user_id,
        "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}],
    }
    return await db.warnings.count_documents(query)


async def list_warnings(
    db: AgnosticDatabase, chat_id: int, user_id: int, limit: int = 50
) -> list[WarningDoc]:
    cursor = (
        db.warnings.find({"chat_id": chat_id, "user_id": user_id})
        .sort("created_at", -1)
        .limit(limit)
    )
    return [WarningDoc.from_doc(d) for d in await cursor.to_list(length=limit)]


async def clear_warnings(db: AgnosticDatabase, chat_id: int, user_id: int) -> int:
    result = await db.warnings.delete_many({"chat_id": chat_id, "user_id": user_id})
    return result.deleted_count
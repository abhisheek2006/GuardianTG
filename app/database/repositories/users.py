from __future__ import annotations

from typing import Optional

from motor.core import AgnosticDatabase

from app.database.models import UserDoc
from app.database.models.base import utcnow


async def get_or_create_user(
    db: AgnosticDatabase,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    is_bot: bool = False,
) -> UserDoc:
    col = db.users
    existing = await col.find_one({"telegram_id": telegram_id})
    if existing:
        update: dict = {}
        if username is not None and existing.get("username") != username:
            update["username"] = username
        if first_name is not None and existing.get("first_name") != first_name:
            update["first_name"] = first_name
        if last_name is not None and existing.get("last_name") != last_name:
            update["last_name"] = last_name
        if update:
            update["updated_at"] = utcnow()
            await col.update_one(
                {"telegram_id": telegram_id}, {"$set": update}
            )
            existing.update(update)
        return UserDoc.from_doc(existing)

    doc = UserDoc(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        is_bot=is_bot,
    )
    await col.insert_one(doc.model_dump())
    return doc


async def get_user(db: AgnosticDatabase, telegram_id: int) -> Optional[UserDoc]:
    doc = await db.users.find_one({"telegram_id": telegram_id})
    return UserDoc.from_doc(doc)


async def count_users(db: AgnosticDatabase) -> int:
    return await db.users.count_documents({})
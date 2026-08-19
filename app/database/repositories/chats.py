from __future__ import annotations

from typing import Optional

from motor.core import AgnosticDatabase

from app.database.models import ChatDoc, ChatSettingsDoc
from app.database.models.base import utcnow


async def get_or_create_chat(
    db: AgnosticDatabase,
    telegram_chat_id: int,
    title: Optional[str] = None,
    chat_type: Optional[str] = None,
) -> ChatDoc:
    col = db.chats
    doc = await col.find_one({"telegram_chat_id": telegram_chat_id})
    if doc:
        update: dict = {}
        if title is not None and doc.get("title") != title:
            update["title"] = title
        if chat_type is not None and doc.get("chat_type") != chat_type:
            update["chat_type"] = chat_type
        if update:
            update["updated_at"] = utcnow()
            await col.update_one({"telegram_chat_id": telegram_chat_id}, {"$set": update})
            doc.update(update)
        return ChatDoc.from_doc(doc)

    chat = ChatDoc(telegram_chat_id=telegram_chat_id, title=title, chat_type=chat_type)
    await col.insert_one(chat.model_dump())
    return chat


async def get_chat_settings(
    db: AgnosticDatabase, chat_id: int, create_if_missing: bool = True
) -> ChatSettingsDoc:
    doc = await db.chat_settings.find_one({"chat_id": chat_id})
    if doc:
        return ChatSettingsDoc.from_doc(doc)
    if not create_if_missing:
        return ChatSettingsDoc.defaults(chat_id)
    defaults = ChatSettingsDoc.defaults(chat_id)
    await db.chat_settings.insert_one(defaults.model_dump())
    return defaults


async def save_chat_settings(db: AgnosticDatabase, settings: ChatSettingsDoc) -> None:
    payload = settings.model_dump()
    payload["updated_at"] = utcnow()
    await db.chat_settings.update_one(
        {"chat_id": settings.chat_id},
        {"$set": payload},
        upsert=True,
    )


async def update_chat_setting(
    db: AgnosticDatabase, chat_id: int, key: str, value: object
) -> None:
    await db.chat_settings.update_one(
        {"chat_id": chat_id},
        {"$set": {key: value, "updated_at": utcnow()}},
        upsert=True,
    )
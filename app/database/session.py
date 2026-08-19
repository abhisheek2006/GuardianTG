from __future__ import annotations

import asyncio
from typing import Any, Optional

import motor.motor_asyncio
from motor.core import AgnosticClient, AgnosticDatabase

from app.core.config import get_settings

_client: Optional[AgnosticClient] = None
_db: Optional[AgnosticDatabase] = None
_connect_lock = asyncio.Lock()


async def connect() -> AgnosticDatabase:
    """Connect to MongoDB, create required indexes. Idempotent."""
    global _client, _db
    async with _connect_lock:
        if _db is not None:
            return _db

        settings = get_settings()
        _client = motor.motor_asyncio.AsyncIOMotorClient(
            settings.mongo_uri,
            serverSelectionTimeoutMS=10_000,
            connectTimeoutMS=10_000,
            maxPoolSize=50,
        )
        _db = _client[settings.mongo_database]
        await _db.command("ping")
        await _ensure_indexes(_db)
        return _db


async def _ensure_indexes(db: AgnosticDatabase) -> None:
    """Create the indexes the queries rely on (idempotent)."""
    await db.users.create_index("telegram_id", unique=True)
    await db.chats.create_index("telegram_chat_id", unique=True)

    await db.chat_settings.create_index("chat_id", unique=True)

    await db.warnings.create_index([("chat_id", 1), ("user_id", 1)])
    await db.warnings.create_index([("chat_id", 1), ("expires_at", 1)])

    await db.moderation_actions.create_index([("chat_id", 1), ("created_at", -1)])
    await db.moderation_actions.create_index([("chat_id", 1), ("action", 1)])
    await db.moderation_actions.create_index([("chat_id", 1), ("expires_at", 1)])

    await db.filters.create_index([("chat_id", 1), ("pattern", 1)])

    await db.banned_users.create_index([("chat_id", 1), ("user_id", 1)], unique=True)

    await db.verification_sessions.create_index([("chat_id", 1), ("user_id", 1)])
    await db.verification_sessions.create_index("expires_at", expireAfterSeconds=0)

    await db.logs.create_index([("chat_id", 1), ("created_at", -1)])
    await db.logs.create_index([("chat_id", 1), ("event_type", 1)])
    await db.logs.create_index("created_at")


def get_db() -> AgnosticDatabase:
    if _db is None:
        raise RuntimeError("Database not connected. Call connect() at startup first.")
    return _db


async def ping() -> bool:
    try:
        await get_db().command("ping")
        return True
    except Exception:
        return False


async def close() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


def get_collection(name: str) -> Any:
    return get_db()[name]
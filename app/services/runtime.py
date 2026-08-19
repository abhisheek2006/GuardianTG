from __future__ import annotations

from typing import Optional

from motor.core import AgnosticDatabase
from pyrogram import Client

# Shared runtime references, wired in main.py at startup.
client: Optional[Client] = None
db: Optional[AgnosticDatabase] = None


def get_client() -> Client:
    if client is None:
        raise RuntimeError("Telegram client not started.")
    return client


def get_db() -> AgnosticDatabase:
    if db is None:
        raise RuntimeError("Database not connected.")
    return db
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.database.models.base import DocBase, utcnow


class UserDoc(DocBase):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_bot: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ChatDoc(DocBase):
    telegram_chat_id: int
    title: Optional[str] = None
    chat_type: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
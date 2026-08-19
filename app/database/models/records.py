from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from app.database.models.base import DocBase, utcnow

MODERATION_ACTIONS = ("warn", "mute", "ban", "kick", "unban", "unmute", "delete")
FILTER_ACTIONS = ("delete", "warn", "mute")


class WarningDoc(DocBase):
    chat_id: int
    user_id: int
    reason: str = ""
    issued_by: int
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ModerationActionDoc(DocBase):
    chat_id: int
    target_user_id: int
    admin_user_id: Optional[int] = None
    action: str
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class BannedUserDoc(DocBase):
    chat_id: int
    user_id: int
    reason: Optional[str] = None
    banned_by: int
    created_at: datetime = Field(default_factory=utcnow)


class CustomFilterDoc(DocBase):
    chat_id: int
    filter_type: str = "profanity"
    pattern: str
    action: str = "delete"
    enabled: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class VerificationSessionDoc(DocBase):
    chat_id: int
    user_id: int
    challenge: str
    attempts: int = 0
    expires_at: datetime
    created_at: datetime = Field(default_factory=utcnow)


class LogEntryDoc(DocBase):
    chat_id: int
    event_type: str
    user_id: Optional[int] = None
    admin_id: Optional[int] = None
    message_id: Optional[int] = None
    details: Optional[dict] = None
    created_at: datetime = Field(default_factory=utcnow)
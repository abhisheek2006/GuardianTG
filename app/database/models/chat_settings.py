from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from app.database.models.base import DocBase, utcnow

MUTE_ACTIONS = ("delete", "warn", "mute", "kick", "ban")
SPAM_MODES = ("monitor", "delete", "warn", "mute", "ban")


class ChatSettingsDoc(DocBase):
    """Per-chat configurable security settings (one document per chat)."""

    chat_id: int

    # Feature toggles
    antispam_enabled: bool = True
    antiflood_enabled: bool = True
    antilink_enabled: bool = True
    antiraid_enabled: bool = True
    captcha_enabled: bool = True
    antibot_enabled: bool = True
    profanity_enabled: bool = True
    welcome_enabled: bool = False
    goodbye_enabled: bool = False
    log_enabled: bool = False
    warn_enabled: bool = True

    # Limits / thresholds
    max_warnings: int = 3
    mute_duration: int = 600
    flood_limit: int = 10
    flood_window: int = 10
    captcha_timeout: int = 120
    raid_threshold: int = 30
    raid_window: int = 60
    spam_score_threshold: int = 10

    # Behaviour
    spam_mode: str = "delete"
    flood_action: str = "mute"

    # Lists
    allow_domains: List[str] = Field(default_factory=list)
    block_domains: List[str] = Field(default_factory=list)
    allow_bots: List[str] = Field(default_factory=list)

    # Content
    welcome_message: Optional[str] = None
    goodbye_message: Optional[str] = None
    rules: Optional[str] = None

    # Logging
    log_channel_id: Optional[int] = None

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @classmethod
    def defaults(cls, chat_id: int) -> "ChatSettingsDoc":
        return cls(chat_id=chat_id)

    def as_toggle_list(self) -> list[tuple[str, bool, str]]:
        toggles = [
            ("Anti-Spam", self.antispam_enabled, "antispam"),
            ("Anti-Flood", self.antiflood_enabled, "antiflood"),
            ("Anti-Link", self.antilink_enabled, "antilink"),
            ("Anti-Raid", self.antiraid_enabled, "antiraid"),
            ("CAPTCHA", self.captcha_enabled, "captcha"),
            ("Anti-Bot", self.antibot_enabled, "antibot"),
            ("Profanity", self.profanity_enabled, "profanity"),
            ("Welcome", self.welcome_enabled, "welcome"),
            ("Goodbye", self.goodbye_enabled, "goodbye"),
            ("Logging", self.log_enabled, "log"),
        ]
        return [(label, enabled, key) for label, enabled, key in toggles]
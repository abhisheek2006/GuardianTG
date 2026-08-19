from __future__ import annotations

import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables / .env.

    All secrets live in the environment. Nothing is hardcoded.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Core ────────────────────────────────────────────────
    bot_name: str = "GuardianTG"
    bot_tagline: str = "Advanced Telegram Group Security Bot"
    bot_token: str = ""

    mongo_uri: str = ""
    mongo_database: str = "guardiantg"
    redis_url: str = "redis://localhost:6379/0"

    owner_id: int | None = None
    # Union with `str` lets pydantic-settings fall back to the raw string when
    # the env value (e.g. an empty `SUDO_IDS=`) is not valid JSON.
    sudo_ids: list[int] | str = []

    # ── Logging ─────────────────────────────────────────────
    log_level: str = "INFO"
    log_file: str = "logs/bot.log"

    # ── Defaults ────────────────────────────────────────────
    default_warn_limit: int = 3
    default_mute_duration: int = 600

    captcha_timeout: int = 120
    captcha_max_attempts: int = 3

    rate_limit: int = 20
    rate_window: int = 10

    flood_limit: int = 10
    flood_window: int = 10

    raid_threshold: int = 30
    raid_window: int = 60

    spam_score_threshold: int = 10

    # ── Web dashboard ───────────────────────────────────────
    web_dashboard_enabled: bool = False
    web_host: str = "0.0.0.0"
    web_port: int = 8000
    web_secret: str = ""
    web_admin_email: str = "abhisheekmondal927@gmail.com"
    web_admin_password: str = "abhisheek2006"

    # ── Data retention ──────────────────────────────────────
    log_retention_days: int = 30

    # ── Runtime ─────────────────────────────────────────────
    restart_command: str = "python -m app.main"

    # ────────────────────────────────────────────────────────

    @field_validator("sudo_ids", mode="before")
    @classmethod
    def _parse_sudo_ids(cls, value: object) -> object:
        """Accept `123`, `123,456`, `[1, 2]` or an empty value."""
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("[") and value.endswith("]"):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [int(p) for p in parsed]
                except ValueError:
                    pass
            return [int(p) for p in value.split(",") if p.strip()]
        if isinstance(value, int):
            return [value]
        if isinstance(value, (list, tuple, set)):
            return [int(p) for p in value]
        return value

    @field_validator("bot_token")
    @classmethod
    def _validate_bot_token(cls, value: str) -> str:
        if not value or ":" not in value:
            raise ValueError(
                "BOT_TOKEN is missing or invalid. Create a bot with @BotFather and copy the token."
            )
        return value

    @field_validator("mongo_uri")
    @classmethod
    def _validate_mongo_uri(cls, value: str) -> str:
        if not value:
            raise ValueError("MONGO_URI is missing. Use a MongoDB connection string.")
        if not value.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError(
                "MONGO_URI must start with mongodb:// or mongodb+srv://"
            )
        return value

    def is_owner(self, user_id: int) -> bool:
        return self.owner_id is not None and user_id == self.owner_id

    def is_sudo(self, user_id: int) -> bool:
        return user_id in self.sudo_ids or self.is_owner(user_id)

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.mongo_uri and self.owner_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_settings() -> None:
    """Raise with a useful message when required config is missing."""
    settings = get_settings()
    errors: list[str] = []

    if not settings.bot_token or ":" not in settings.bot_token:
        errors.append("BOT_TOKEN is missing/invalid (create a bot via @BotFather).")
    if not settings.mongo_uri:
        errors.append("MONGO_URI is missing (MongoDB required).")
    if not settings.redis_url:
        errors.append("REDIS_URL is missing.")
    if settings.owner_id is None:
        errors.append("OWNER_ID is missing (your Telegram user id).")

    if errors:
        raise RuntimeError(
            "GuardianTG configuration is incomplete:\n  - " + "\n  - ".join(errors)
            + "\nCopy .env.example to .env and fill in the values."
        )
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.database import session as db_session
from app.services import redis as redis_service
from app.services import runtime


@dataclass
class HealthStatus:
    telegram: bool = False
    database: bool = False
    redis: bool = False

    @property
    def healthy(self) -> bool:
        return self.telegram and self.database and self.redis

    @property
    def summary(self) -> str:
        marks = {
            "telegram": self.telegram,
            "database": self.database,
            "redis": self.redis,
        }
        lines = [
            "🛡 **GuardianTG Health Check**",
            "",
            f"🔌 Telegram: {'🟢 OK' if self.telegram else '🔴 DOWN'}",
            f"🗄  MongoDB:   {'🟢 OK' if self.database else '🔴 DOWN'}",
            f"⚡ Redis:      {'🟢 OK' if self.redis else '🔴 DOWN'}",
        ]
        if not self.healthy:
            lines.append("")
            lines.append("⚠️ One or more critical services are unreachable.")
        return "\n".join(lines)


async def check() -> HealthStatus:
    status = HealthStatus()
    try:
        client = runtime.get_client()
        await client.get_me()
        status.telegram = True
    except Exception:
        pass

    try:
        status.database = await db_session.ping()
    except Exception:
        status.database = False

    try:
        status.redis = await redis_service.ping()
    except Exception:
        status.redis = False

    return status


async def check_and_notify() -> None:
    """Check services; notify the owner on critical failure (throttled)."""
    status = await check()
    if status.healthy:
        return

    settings = get_settings()
    if not settings.owner_id:
        return

    r = redis_service.get_redis()
    key = "health:notified"
    notified = await r.get(key)
    if notified:
        return

    try:
        await runtime.get_client().send_message(
            settings.owner_id, status.summary
        )
        await r.set(key, "1", ex=300)
    except Exception:
        pass
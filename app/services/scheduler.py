from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.database.repositories import actions as actions_repo
from app.database.repositories import logs as log_repo
from app.services import captcha, health, moderation, runtime
from app.services import redis as redis_service

scheduler: AsyncIOScheduler = AsyncIOScheduler()


async def _unmute_expired() -> None:
    """Automatically unmute users whose mute duration has expired."""
    db = runtime.get_db()
    now = datetime.now(timezone.utc)
    expiring = await actions_repo.find_expiring_mutes(db, now)
    client = runtime.get_client()
    for action in expiring:
        try:
            await client.restrict_chat_member(
                action.chat_id,
                action.target_user_id,
                moderation.FULL_PERMISSIONS,
            )
            await actions_repo.log_action(
                db,
                action.chat_id,
                action.target_user_id,
                "unmute",
                reason="Automatic unmute (duration expired)",
            )
        except Exception:
            continue


async def _cleanup_expired_captchas() -> None:
    try:
        await captcha.cleanup_expired()
    except Exception:
        pass


async def _cleanup_old_logs() -> None:
    try:
        db = runtime.get_db()
        removed = await log_repo.purge_old_logs(
            db, get_settings().log_retention_days
        )
        if removed:
            from app.core.logging import get_logger

            get_logger(__name__).info("Purged %s old log entries", removed)
    except Exception:
        pass


async def _periodic_health_check() -> None:
    try:
        await health.check_and_notify()
    except Exception:
        pass


def start_scheduler() -> None:
    """Register periodic background jobs and start the scheduler."""
    if scheduler.running:
        return

    scheduler.add_job(
        _unmute_expired, IntervalTrigger(seconds=30), id="unmute_expired",
        max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        _cleanup_expired_captchas, IntervalTrigger(seconds=60), id="cleanup_captchas",
        max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        _cleanup_old_logs, IntervalTrigger(minutes=30), id="cleanup_logs",
        max_instances=1, coalesce=True,
    )
    scheduler.add_job(
        _periodic_health_check, IntervalTrigger(minutes=5), id="health_check",
        max_instances=1, coalesce=True,
    )
    scheduler.start()


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
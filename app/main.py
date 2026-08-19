from __future__ import annotations

import asyncio
import signal

# Pyrogram 2.0.106 calls asyncio.get_event_loop() at import time, which
# raises on Python 3.14+. Install a default event loop first so the import
# (and therefore the whole bot) starts successfully on Python 3.14.
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from app.core.config import validate_settings
from app.core.logging import get_logger, setup_logging
from app.database import session as db_session
from app.services import redis as redis_service
from app.services import runtime, scheduler


async def _run() -> None:
    validate_settings()
    setup_logging()
    logger = get_logger("guardiantg")

    # ── Connect infrastructure ─────────────────────────────────
    logger.info("Connecting to MongoDB…")
    db = await db_session.connect()
    logger.info("MongoDB connected.")

    logger.info("Connecting to Redis…")
    await redis_service.connect()
    logger.info("Redis connected.")

    from app.bot.client import create_client

    client = create_client()
    runtime.client = client
    runtime.db = db

    # ── Optional web dashboard ─────────────────────────────────
    web_task = None
    from app.core.config import get_settings

    if get_settings().web_dashboard_enabled:
        try:
            from app.web.main import start_web

            web_task = asyncio.create_task(start_web())
            logger.info("Web dashboard starting on %s:%s", get_settings().web_host, get_settings().web_port)
        except Exception:
            logger.exception("Could not start web dashboard")

    # ── Start Telegram client (loads all plugins) ──────────────
    await client.start()
    logger.info("✅ Bot connected successfully. (id=%s)", (await client.get_me()).id)

    scheduler.start_scheduler()
    logger.info("Background scheduler started.")

    # ── Wait for shutdown signal ───────────────────────────────
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, RuntimeError):
            # Windows: no signal handlers for SIGTERM.
            if sig is signal.SIGINT:
                try:
                    loop.add_signal_handler(sig, stop_event.set)
                except Exception:
                    pass

    logger.info("GuardianTG is running. Press Ctrl+C to stop.")
    await stop_event.wait()

    # ── Graceful shutdown ──────────────────────────────────────
    logger.info("Shutting down…")
    scheduler.shutdown_scheduler()
    if web_task is not None:
        web_task.cancel()
        try:
            await web_task
        except asyncio.CancelledError:
            pass
    try:
        await client.stop()
    except Exception:
        pass
    await db_session.close()
    await redis_service.close()
    logger.info("Shutdown complete.")


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass
    except Exception:
        from app.core.logging import setup_logging as _sl

        _sl()
        get_logger("guardiantg").exception("Fatal error")


if __name__ == "__main__":
    main()
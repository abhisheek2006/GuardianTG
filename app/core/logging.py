from __future__ import annotations

import logging
import os
import re
from logging.handlers import RotatingFileHandler

from app.core.config import get_settings

_configured = False

_LOGGED_SECRETS: list[str] = []


def register_secret(secret: str) -> None:
    """Register a value that must never appear in log output."""
    if secret and len(secret) >= 4:
        _LOGGED_SECRETS.append(secret)


class SecretRedactionFilter(logging.Filter):
    """Redacts registered secrets (tokens, passwords, keys) from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not _LOGGED_SECRETS:
            return True
        msg = record.getMessage()
        for secret in _LOGGED_SECRETS:
            if secret in msg:
                record.msg = record.msg.replace(secret, "***")
                record.args = ()
        return True


def setup_logging() -> None:
    global _configured
    if _configured:
        return

    settings = get_settings()

    # Never log credentials.
    register_secret(settings.bot_token)
    register_secret(settings.web_secret)

    match = re.search(r"://([^:/@]+):([^@/]+)@", settings.mongo_uri)
    if match:
        register_secret(match.group(2))
    match = re.search(r"://([^:/@]+):([^@/]+)@", settings.redis_url)
    if match:
        register_secret(match.group(2))

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    log_dir = os.path.dirname(settings.log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.addFilter(SecretRedactionFilter())

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    try:
        file_handler = RotatingFileHandler(
            settings.log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as exc:
        root.warning("Could not create log file %s: %s", settings.log_file, exc)

    # Quiet noisy third-party loggers.
    for noisy in ("pyrogram", "aiohttp", "aiosqlite", "httpx", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True
    root.info("Logging initialized (level=%s)", settings.log_level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
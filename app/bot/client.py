from __future__ import annotations

from pyrogram import Client

from app.core.config import get_settings


def create_client() -> Client:
    settings = get_settings()
    return Client(
        "guardiantg",
        bot_token=settings.bot_token,
        plugins={"root": "app.bot.handlers"},
        workdir=".",
    )
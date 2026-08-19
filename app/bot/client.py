from __future__ import annotations

import importlib

from pyrogram import Client
from pyrogram.handlers.handler import Handler

from app.core.config import get_settings

# Callback handlers (inline keyboards) live outside the plugins root that
# pyrogram auto-loads (`app.bot.handlers`). The class-level
# `@Client.on_callback_query` decorators only stash handlers on
# `func.handlers`, so we must register them on the client explicitly.
CALLBACK_MODULES = (
    "app.bot.callbacks.admin_panel",
    "app.bot.callbacks.advanced",
    "app.bot.callbacks.misc",
    "app.bot.callbacks.nav",
    "app.bot.callbacks.settings",
    "app.bot.callbacks.verification",
)


def _register_callback_handlers(client: Client) -> None:
    for module_name in CALLBACK_MODULES:
        module = importlib.import_module(module_name)
        for name in vars(module):
            obj = getattr(module, name)
            try:
                for handler, group in obj.handlers:
                    if isinstance(handler, Handler) and isinstance(group, int):
                        client.add_handler(handler, group)
            except AttributeError:
                continue


def create_client() -> Client:
    settings = get_settings()
    client = Client(
        "guardiantg",
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        bot_token=settings.bot_token,
        plugins={"root": "app.bot.handlers"},
        workdir=".",
    )
    _register_callback_handlers(client)
    return client
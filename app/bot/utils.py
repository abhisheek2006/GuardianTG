from __future__ import annotations

from typing import Optional

from pyrogram.enums import ChatType
from pyrogram.types import Message, User

from app.core.config import get_settings


def human_name(user: Optional[User]) -> str:
    if user is None:
        return "Unknown"
    return user.first_name or user.username or str(user.id)


def user_display(user: Optional[User]) -> str:
    if user is None:
        return "`0`"
    if user.username:
        return f"@{user.username}"
    return f"`{user.id}`"


def is_group(message: Message) -> bool:
    return message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


def is_command(message: Message) -> bool:
    return bool(message.text and message.text.startswith("/"))


def parse_args(message: Message) -> str:
    parts = message.text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def split_command(message: Message) -> tuple[str, str]:
    parts = message.text.split(maxsplit=1)
    cmd = parts[0].split("@")[0]
    rest = parts[1].strip() if len(parts) > 1 else ""
    return cmd, rest


def cap_len(text: str, limit: int = 4000) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."
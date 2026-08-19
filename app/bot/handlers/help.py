from __future__ import annotations

from pyrogram import Client, filters
from pyrogram.types import Message

from app.bot.utils import is_group
from app.services import permissions as perms


@Client.on_message(filters.command("help"))
async def help_command(client: Client, message: Message) -> None:
    is_owner = await perms.is_owner(message.from_user.id) if message.from_user else False
    is_admin = False
    if is_group(message):
        is_admin = await perms.is_chat_admin(client, message.chat.id, message.from_user.id)

    blocks: list[str] = ["🛡 **GuardianTG Help**", ""]

    blocks.append("**Moderation**")
    blocks.append("/warn - Warn a user")
    blocks.append("/warnings - View user warnings")
    blocks.append("/clearwarns - Clear a user's warnings")
    blocks.append("/mute - Mute a user")
    blocks.append("/unmute - Unmute a user")
    blocks.append("/ban - Ban a user")
    blocks.append("/unban - Unban a user")
    blocks.append("/kick - Kick a user")
    blocks.append("/purge - Delete a range of messages")

    blocks.append("")
    blocks.append("**Security**")
    if is_admin:
        blocks.append("/antispam - Toggle anti-spam")
        blocks.append("/antiflood - Configure flood protection")
        blocks.append("/antilink - Toggle link blocking")
        blocks.append("/antiraid - Toggle raid protection")
        blocks.append("/captcha - Toggle CAPTCHA verification")
        blocks.append("/antibot - Toggle bot protection")
        blocks.append("/allowdomain - Allow a domain")
        blocks.append("/allowbot - Allow a bot")
    else:
        blocks.append("Group admins can manage security settings here.")

    blocks.append("")
    blocks.append("**Settings**")
    if is_admin:
        blocks.append("/settings - Interactive security panel")
        blocks.append("/admin - Admin panel")
        blocks.append("/setrules - Set group rules")
        blocks.append("/welcome - Configure welcome message")
        blocks.append("/setlogchannel - Set the log channel")
        blocks.append("/filter - Manage custom filters")
    else:
        blocks.append("/rules - View group rules")
        blocks.append("/settings - View security status")

    blocks.append("")
    blocks.append("**Information**")
    blocks.append("/id - Chat and user IDs")
    blocks.append("/info - User information")
    blocks.append("/rules - Group rules")

    if is_owner:
        blocks.append("")
        blocks.append("**Owner**")
        blocks.append("/stats /chats /broadcast /restart /maintenance /debug")

    await message.reply_text("\n".join(blocks))
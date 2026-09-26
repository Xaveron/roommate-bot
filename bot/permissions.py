"""Who may do what in a room: the same checks for the bot and the Mini App.

Both ask Telegram (getChatMember), so a chat admin keeps their rights wherever they act.
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatMemberRestricted

from bot.db.models import Room

logger = logging.getLogger(__name__)

ADMIN_STATUSES = (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR)
IN_CHAT_STATUSES = (*ADMIN_STATUSES, ChatMemberStatus.MEMBER)


async def can_manage(bot: Bot, room: Room, user_id: int) -> bool:
    """Room settings may be changed by the room creator and by chat admins."""
    if room.created_by == user_id:
        return True
    try:
        chat_member = await bot.get_chat_member(room.chat_id, user_id)
    except TelegramAPIError:
        logger.warning("Cannot check admin rights of %s in %s", user_id, room.chat_id)
        return False
    return chat_member.status in ADMIN_STATUSES


async def is_in_chat(bot: Bot, room: Room, user_id: int) -> bool:
    """Whether the user is in the room's group chat, i.e. may press "I live here" there."""
    try:
        chat_member = await bot.get_chat_member(room.chat_id, user_id)
    except TelegramAPIError:
        return False
    if isinstance(chat_member, ChatMemberRestricted):
        return chat_member.is_member
    return chat_member.status in IN_CHAT_STATUSES

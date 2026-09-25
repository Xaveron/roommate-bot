"""Sending messages on behalf of the bot: reminders and announcements in the group chat.

This is the Telegram side of the reminder flow; *what* to send is decided in ``bot.services``.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
)
from aiogram.types import InlineKeyboardMarkup, Message

from bot.db.models import Assignment, AssignmentStatus, Room
from bot.i18n import I18n, Translator
from bot.keyboards.common import turn_keyboard
from bot.services.reminders import ReminderService
from bot.utils.text import bold, esc, mention

logger = logging.getLogger(__name__)


def reminder_text(t: Translator, assignment: Assignment, *, with_room: bool = True) -> str:
    category = assignment.category
    lines = [t("reminder-text", kind=category.kind, emoji=category.emoji, name=esc(category.name))]
    if with_room:
        lines.append(t("reminder-room", room=esc(category.room.name)))
    if assignment.status == AssignmentStatus.ACCEPTED:
        lines.append("")
        lines.append(t("turn-accepted"))
    return "\n".join(lines)


def member_name(assignment: Assignment) -> str:
    return bold(assignment.member.display_name)


class Notifier:
    def __init__(self, bot: Bot, i18n: I18n) -> None:
        self.bot = bot
        self.i18n = i18n

    def translator(self, room: Room) -> Translator:
        return self.i18n.get(room.language)

    async def bot_username(self) -> str:
        return (await self.bot.me()).username or ""

    async def send_group(
        self, room: Room, text: str, markup: InlineKeyboardMarkup | None = None
    ) -> Message | None:
        """Post into the room's group chat; never raises."""
        try:
            return await self.bot.send_message(room.chat_id, text, reply_markup=markup)
        except TelegramForbiddenError:
            logger.warning(
                "Bot was removed from chat %s, deactivating room %s", room.chat_id, room.id
            )
            room.is_active = False
        except TelegramAPIError:
            logger.exception("Failed to post into chat %s", room.chat_id)
        return None

    async def deliver_reminder(self, assignment: Assignment, now: datetime) -> None:
        """DM the member; if the bot can't write to them, remind them in the group chat."""
        room = assignment.category.room
        t = self.translator(room)
        user = assignment.member.user
        await self.strip_buttons(assignment)

        message: Message | None = None
        try:
            message = await self.bot.send_message(
                user.id, reminder_text(t, assignment), reply_markup=turn_keyboard(t, assignment)
            )
            user.dm_available = True
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            logger.info("Cannot DM user %s (%s), falling back to the group", user.id, exc)
            user.dm_available = False
        except TelegramAPIError:
            logger.exception("Failed to DM user %s", user.id)

        if message is None:
            text = t(
                "reminder-group-fallback",
                mention=mention(user.id, user.display_name),
                text=reminder_text(t, assignment, with_room=False),
            )
            message = await self.send_group(
                room,
                text,
                turn_keyboard(t, assignment, bot_username=await self.bot_username()),
            )
        ReminderService.mark_delivered(
            assignment,
            now,
            message.chat.id if message else None,
            message.message_id if message else None,
        )

    async def strip_buttons(self, assignment: Assignment) -> None:
        """Remove the buttons from the previous reminder message, if any."""
        if assignment.message_chat_id is None or assignment.message_id is None:
            return
        with suppress(TelegramAPIError):  # too old, deleted or unchanged: nothing to do
            await self.bot.edit_message_reply_markup(
                chat_id=assignment.message_chat_id, message_id=assignment.message_id
            )

    async def close_reminder(self, assignment: Assignment, note: str) -> None:
        """Replace the reminder message with a final note (e.g. somebody else did it)."""
        if assignment.message_chat_id is None or assignment.message_id is None:
            return
        t = self.translator(assignment.category.room)
        text = f"{reminder_text(t, assignment)}\n\n{note}"
        try:
            await self.bot.edit_message_text(
                text=text, chat_id=assignment.message_chat_id, message_id=assignment.message_id
            )
        except TelegramAPIError:
            logger.debug("Could not edit reminder message of assignment %s", assignment.id)

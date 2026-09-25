"""Helpers shared by handlers."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from aiogram import Bot, F
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Chat, InlineKeyboardMarkup, Message

from bot.db.models import CategoryKind, Member, Room
from bot.i18n import I18n, Translator
from bot.keyboards.common import vote_keyboard
from bot.services.tasks import Completion
from bot.utils.text import bold, esc

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4000

# Free-text answers to a pending question (commands keep working while a question is pending).
ANSWER = F.text & ~F.text.startswith("/")


def is_group(chat: Chat | None) -> bool:
    return chat is not None and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


async def can_manage(bot: Bot, room: Room, user_id: int) -> bool:
    """Room settings may be changed by the room creator and by chat admins."""
    if room.created_by == user_id:
        return True
    try:
        chat_member = await bot.get_chat_member(room.chat_id, user_id)
    except TelegramAPIError:
        logger.warning("Cannot check admin rights of %s in %s", user_id, room.chat_id)
        return False
    return chat_member.status in (ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR)


def default_category_names(i18n: I18n, language: str) -> Mapping[str, str]:
    t = i18n.get(language)
    return {
        kind: t("category-default-name", kind=kind)
        for kind in (CategoryKind.BREAD, CategoryKind.WATER, CategoryKind.TRASH)
    }


def name_of(member: Member | None, t: Translator) -> str:
    return bold(member.display_name) if member is not None else t("nobody")


def completion_text(t: Translator, completion: Completion) -> str:
    category = completion.category
    key = "group-done" if completion.in_turn else "group-out-of-turn"
    lines = [
        t(
            key,
            emoji=category.emoji,
            category=esc(category.name),
            name=bold(completion.member.display_name),
        )
    ]
    if completion.next_member is not None:
        lines.append(t("group-next", name=bold(completion.next_member.display_name)))
    return "\n".join(lines)


def completion_markup(t: Translator, completion: Completion) -> InlineKeyboardMarkup | None:
    """👍 / 🤨 buttons, unless nobody else lives in the room."""
    return vote_keyboard(t, completion.duty.id) if completion.voters > 0 else None


def split_long(text: str, limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split a message by blank lines so that each part fits into one Telegram message."""
    parts: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            parts.append(current)
        current = block[:limit]
    if current:
        parts.append(current)
    return parts


async def answer_long(message: Message, text: str, **kwargs: object) -> None:
    for part in split_long(text):
        await message.answer(part, **kwargs)  # type: ignore[arg-type]

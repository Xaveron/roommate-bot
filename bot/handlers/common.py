"""Helpers shared by handlers."""

from __future__ import annotations

from aiogram import F
from aiogram.enums import ChatType
from aiogram.types import Chat, Message

MAX_MESSAGE_LENGTH = 4000

# Free-text answers to a pending question (commands keep working while a question is pending).
ANSWER = F.text & ~F.text.startswith("/")


def is_group(chat: Chat | None) -> bool:
    return chat is not None and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


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

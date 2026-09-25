from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.i18n import I18n


class I18nMiddleware(BaseMiddleware):
    """Injects ``t``: the room language, otherwise the user's Telegram language."""

    def __init__(self, i18n: I18n) -> None:
        self.i18n = i18n

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        room = data.get("room")
        user = data.get("user")
        locale = self.i18n.resolve(
            room.language if room is not None else None,
            user.language_code if user is not None else None,
        )
        data["i18n"] = self.i18n
        data["t"] = self.i18n.get(locale)
        return await handler(event, data)

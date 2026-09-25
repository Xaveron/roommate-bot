from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.db import Database


class DbSessionMiddleware(BaseMiddleware):
    """Opens one session per update and commits it when the handler succeeds."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.db.session() as session:
            data["session"] = session
            result = await handler(event, data)
            await session.commit()
            return result

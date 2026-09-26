from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager, nullcontext
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Chat, TelegramObject, User

from bot.db import Database


class DbSessionMiddleware(BaseMiddleware):
    """Opens one session per update and commits it when the handler succeeds.

    Updates of the same chat are handled one after another (see ``Database.lock_for``).
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._chat_lock(data), self.db.session() as session:
            data["session"] = session
            result = await handler(event, data)
            await session.commit()
            return result

    def _chat_lock(self, data: dict[str, Any]) -> AbstractAsyncContextManager[Any]:
        chat: Chat | None = data.get("event_chat")
        user: User | None = data.get("event_from_user")
        key = chat.id if chat is not None else user.id if user is not None else None
        return self.db.lock_for(key) if key is not None else nullcontext()

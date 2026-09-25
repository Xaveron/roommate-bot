"""Duty history."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Category, Duty, Room
from bot.db.repositories import CategoryRepo, DutyRepo


@dataclass(slots=True)
class CategoryHistory:
    category: Category
    duties: Sequence[Duty]


class HistoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.categories = CategoryRepo(session)
        self.duties = DutyRepo(session)

    async def for_category(self, category: Category, limit: int = 15) -> CategoryHistory:
        return CategoryHistory(category, await self.duties.list_recent(category.id, limit))

    async def for_room(self, room: Room, limit_per_category: int = 7) -> list[CategoryHistory]:
        return [
            await self.for_category(category, limit_per_category)
            for category in await self.categories.list(room.id)
        ]

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select

from bot.db.models import Category
from bot.db.repositories.base import Repository


class CategoryRepo(Repository):
    async def get(self, category_id: int) -> Category | None:
        return await self.session.get(Category, category_id)

    async def list(self, room_id: int, *, active_only: bool = False) -> Sequence[Category]:
        query = select(Category).where(Category.room_id == room_id)
        if active_only:
            query = query.where(Category.is_active.is_(True))
        result = await self.session.scalars(query.order_by(Category.sort_order, Category.id))
        return result.all()

    async def find_by_name(self, room_id: int, name: str) -> Category | None:
        wanted = name.strip().casefold()
        for category in await self.list(room_id):
            if category.name.casefold() == wanted:
                return category
        return None

    async def next_sort_order(self, room_id: int) -> int:
        current = await self.session.scalar(
            select(func.max(Category.sort_order)).where(Category.room_id == room_id)
        )
        return 0 if current is None else current + 1

    async def add(self, category: Category) -> Category:
        self.session.add(category)
        await self.session.flush()
        return category

    async def delete(self, category: Category) -> None:
        await self.session.delete(category)
        await self.session.flush()

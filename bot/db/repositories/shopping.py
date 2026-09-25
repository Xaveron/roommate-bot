from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select

from bot.db.models import ShoppingItem
from bot.db.repositories.base import Repository


class ShoppingRepo(Repository):
    async def get(self, item_id: int) -> ShoppingItem | None:
        return await self.session.get(ShoppingItem, item_id)

    async def add(self, item: ShoppingItem) -> ShoppingItem:
        self.session.add(item)
        await self.session.flush()
        return item

    async def list_open(self, room_id: int) -> Sequence[ShoppingItem]:
        result = await self.session.scalars(
            select(ShoppingItem)
            .where(ShoppingItem.room_id == room_id, ShoppingItem.bought_at.is_(None))
            .order_by(ShoppingItem.created_at, ShoppingItem.id)
        )
        return result.all()

    async def bought_count(self, member_id: int) -> int:
        return (
            await self.session.scalar(
                select(func.count())
                .select_from(ShoppingItem)
                .where(ShoppingItem.bought_by == member_id)
            )
            or 0
        )

"""The room's shared shopping list."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Member, Room, ShoppingItem
from bot.db.repositories import ShoppingRepo
from bot.services.errors import ServiceError

MAX_ITEM_LENGTH = 64
MAX_OPEN_ITEMS = 50


def split_items(text: str) -> list[str]:
    """'соль, молоко\\nхлеб' -> ['соль', 'молоко', 'хлеб'] (trimmed, without duplicates)."""
    items: dict[str, str] = {}
    for part in re.split(r"[,;\n]+", text):
        item = " ".join(part.split())[:MAX_ITEM_LENGTH]
        if item:
            items.setdefault(item.casefold(), item)
    return list(items.values())


class ShoppingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.items = ShoppingRepo(session)

    async def open_items(self, room: Room) -> Sequence[ShoppingItem]:
        return await self.items.list_open(room.id)

    async def add(self, room: Room, member: Member, text: str, now: datetime) -> list[ShoppingItem]:
        """Add items that aren't on the list yet. Returns the added ones."""
        wanted = split_items(text)
        if not wanted:
            raise ServiceError("err-buy-empty")
        existing = await self.items.list_open(room.id)
        known = {item.text.casefold() for item in existing}
        fresh = [item for item in wanted if item.casefold() not in known]
        if len(existing) + len(fresh) > MAX_OPEN_ITEMS:
            raise ServiceError("err-buy-too-many", max=MAX_OPEN_ITEMS)
        return [
            await self.items.add(
                ShoppingItem(room_id=room.id, text=item, added_by=member.id, created_at=now)
            )
            for item in fresh
        ]

    async def mark_bought(
        self, room: Room, item_id: int, member: Member, now: datetime
    ) -> ShoppingItem:
        item = await self.items.get(item_id)
        if item is None or item.room_id != room.id or item.bought_at is not None:
            raise ServiceError("err-item-gone")
        item.bought_by = member.id
        item.bought_at = now
        await self.session.flush()
        return item

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select

from bot.db.models import Room
from bot.db.repositories.base import Repository


class RoomRepo(Repository):
    async def get(self, room_id: int) -> Room | None:
        return await self.session.get(Room, room_id)

    async def get_by_chat_id(self, chat_id: int) -> Room | None:
        return await self.session.scalar(select(Room).where(Room.chat_id == chat_id))

    async def add(self, room: Room) -> Room:
        self.session.add(room)
        await self.session.flush()
        return room

    async def list_active(self) -> Sequence[Room]:
        result = await self.session.scalars(
            select(Room).where(Room.is_active.is_(True)).order_by(Room.id)
        )
        return result.all()

    async def count(self, *, active_only: bool = True) -> int:
        query = select(func.count()).select_from(Room)
        if active_only:
            query = query.where(Room.is_active.is_(True))
        return await self.session.scalar(query) or 0

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select

from bot.db.models import Member, Room
from bot.db.repositories.base import Repository


class MemberRepo(Repository):
    async def get(self, member_id: int) -> Member | None:
        return await self.session.get(Member, member_id)

    async def get_by_user(self, room_id: int, user_id: int) -> Member | None:
        return await self.session.scalar(
            select(Member).where(Member.room_id == room_id, Member.telegram_user_id == user_id)
        )

    async def list(self, room_id: int, *, active_only: bool = True) -> Sequence[Member]:
        query = select(Member).where(Member.room_id == room_id)
        if active_only:
            query = query.where(Member.is_active.is_(True))
        result = await self.session.scalars(query.order_by(Member.joined_at, Member.id))
        return result.all()

    async def add(self, member: Member) -> Member:
        self.session.add(member)
        await self.session.flush()
        return member

    async def rooms_of_user(self, user_id: int) -> Sequence[Room]:
        """Active rooms where the user is an active member, oldest membership first."""
        result = await self.session.scalars(
            select(Room)
            .join(Member, Member.room_id == Room.id)
            .where(
                Member.telegram_user_id == user_id,
                Member.is_active.is_(True),
                Room.is_active.is_(True),
            )
            .order_by(Member.joined_at, Member.id)
        )
        return result.all()

    async def count(self) -> int:
        return (
            await self.session.scalar(
                select(func.count()).select_from(Member).where(Member.is_active.is_(True))
            )
            or 0
        )

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import select

from bot.db.models import Achievement
from bot.db.repositories.base import Repository


class AchievementRepo(Repository):
    async def codes(self, member_id: int) -> set[str]:
        result = await self.session.scalars(
            select(Achievement.code).where(Achievement.member_id == member_id)
        )
        return set(result.all())

    async def add(self, achievement: Achievement) -> Achievement:
        self.session.add(achievement)
        await self.session.flush()
        return achievement

    async def for_members(self, member_ids: Iterable[int]) -> Sequence[Achievement]:
        ids = list(member_ids)
        if not ids:
            return []
        result = await self.session.scalars(
            select(Achievement)
            .where(Achievement.member_id.in_(ids))
            .order_by(Achievement.earned_at, Achievement.id)
        )
        return result.all()

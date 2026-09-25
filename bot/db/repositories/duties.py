from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select

from bot.db.models import COMPLETED_DUTY_STATUSES, Category, Duty, ReviewStatus
from bot.db.repositories.base import Repository


class DutyRepo(Repository):
    async def add(
        self,
        *,
        category_id: int,
        member_id: int,
        status: str,
        created_at: datetime,
        assignment_id: int | None = None,
    ) -> Duty:
        duty = Duty(
            category_id=category_id,
            member_id=member_id,
            status=status,
            created_at=created_at,
            assignment_id=assignment_id,
            amount_cents=None,
            review=ReviewStatus.OPEN,
        )
        self.session.add(duty)
        await self.session.flush()
        return duty

    async def get(self, duty_id: int) -> Duty | None:
        return await self.session.get(Duty, duty_id)

    async def completed_counts(self, category_id: int, since: datetime) -> dict[int, int]:
        """How many times each member did the chore since a moment (disputed ones excluded)."""
        result = await self.session.execute(
            select(Duty.member_id, func.count())
            .where(
                Duty.category_id == category_id,
                Duty.status.in_(COMPLETED_DUTY_STATUSES),
                Duty.review != ReviewStatus.DISPUTED,
                Duty.created_at >= since,
            )
            .group_by(Duty.member_id)
        )
        return {member_id: count for member_id, count in result.all()}

    async def list_recent(self, category_id: int, limit: int = 10) -> Sequence[Duty]:
        result = await self.session.scalars(
            select(Duty)
            .where(Duty.category_id == category_id)
            .order_by(Duty.created_at.desc(), Duty.id.desc())
            .limit(limit)
        )
        return result.all()

    async def list_for_room(
        self, room_id: int, since: datetime | None = None, until: datetime | None = None
    ) -> Sequence[Duty]:
        """All duty records of a room in [since, until), oldest first."""
        query = (
            select(Duty)
            .join(Category, Category.id == Duty.category_id)
            .where(Category.room_id == room_id)
        )
        if since is not None:
            query = query.where(Duty.created_at >= since)
        if until is not None:
            query = query.where(Duty.created_at < until)
        result = await self.session.scalars(query.order_by(Duty.created_at, Duty.id))
        return result.all()

    async def list_for_member(self, member_id: int) -> Sequence[Duty]:
        result = await self.session.scalars(
            select(Duty).where(Duty.member_id == member_id).order_by(Duty.created_at, Duty.id)
        )
        return result.all()

    async def count(self) -> int:
        return await self.session.scalar(select(func.count()).select_from(Duty)) or 0

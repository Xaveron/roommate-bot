from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select

from bot.db.models import Duty
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
        amount: Decimal | None = None,
    ) -> Duty:
        duty = Duty(
            category_id=category_id,
            member_id=member_id,
            status=status,
            created_at=created_at,
            assignment_id=assignment_id,
            amount=amount,
        )
        self.session.add(duty)
        await self.session.flush()
        return duty

    async def list_recent(self, category_id: int, limit: int = 10) -> Sequence[Duty]:
        result = await self.session.scalars(
            select(Duty)
            .where(Duty.category_id == category_id)
            .order_by(Duty.created_at.desc(), Duty.id.desc())
            .limit(limit)
        )
        return result.all()

    async def count(self) -> int:
        return await self.session.scalar(select(func.count()).select_from(Duty)) or 0

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, func, select

from bot.db.models import Expense
from bot.db.repositories.base import Repository


class ExpenseRepo(Repository):
    async def add(self, expense: Expense) -> Expense:
        self.session.add(expense)
        await self.session.flush()
        return expense

    async def list_for_room(
        self, room_id: int, since: datetime | None = None, until: datetime | None = None
    ) -> Sequence[Expense]:
        query = select(Expense).where(Expense.room_id == room_id)
        if since is not None:
            query = query.where(Expense.created_at >= since)
        if until is not None:
            query = query.where(Expense.created_at < until)
        result = await self.session.scalars(query.order_by(Expense.created_at, Expense.id))
        return result.all()

    async def paid_count(self, member_id: int) -> int:
        """Purchases (not repayments) paid by the member."""
        return (
            await self.session.scalar(
                select(func.count())
                .select_from(Expense)
                .where(Expense.payer_id == member_id, Expense.is_settlement.is_(False))
            )
            or 0
        )

    async def delete_for_duty(self, duty_id: int) -> None:
        await self.session.execute(
            delete(Expense)
            .where(Expense.duty_id == duty_id)
            .execution_options(synchronize_session="fetch")
        )

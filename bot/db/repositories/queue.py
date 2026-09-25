from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select, update

from bot.db.models import QueueState
from bot.db.repositories.base import Repository


class QueueRepo(Repository):
    async def list_for_category(
        self, category_id: int, *, for_update: bool = False
    ) -> Sequence[QueueState]:
        query = (
            select(QueueState)
            .where(QueueState.category_id == category_id)
            .order_by(QueueState.position, QueueState.id)
        )
        if for_update:
            query = query.with_for_update()
        result = await self.session.scalars(query)
        return result.all()

    async def get(self, category_id: int, member_id: int) -> QueueState | None:
        return await self.session.scalar(
            select(QueueState).where(
                QueueState.category_id == category_id, QueueState.member_id == member_id
            )
        )

    async def next_position(self, category_id: int) -> int:
        current = await self.session.scalar(
            select(func.max(QueueState.position)).where(QueueState.category_id == category_id)
        )
        return 0 if current is None else current + 1

    async def reset_balances(self, *, category_id: int | None = None, member_id: int | None = None):
        """Zero skip debts and credits of a category, of a member, or of one member in one queue."""
        query = update(QueueState).values(skip_debt=0, credit=0)
        if category_id is not None:
            query = query.where(QueueState.category_id == category_id)
        if member_id is not None:
            query = query.where(QueueState.member_id == member_id)
        await self.session.execute(query.execution_options(synchronize_session="fetch"))

    async def add(self, category_id: int, member_id: int, position: int) -> QueueState:
        state = QueueState(
            category_id=category_id, member_id=member_id, position=position, skip_debt=0, credit=0
        )
        self.session.add(state)
        await self.session.flush()
        return state

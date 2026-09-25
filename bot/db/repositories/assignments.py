from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm.attributes import set_committed_value

from bot.db.models import OPEN_ASSIGNMENT_STATUSES, Assignment, AssignmentStatus, Category
from bot.db.repositories.base import Repository


class AssignmentRepo(Repository):
    async def get(self, assignment_id: int) -> Assignment | None:
        return await self.session.get(Assignment, assignment_id)

    async def get_open(self, category_id: int) -> Assignment | None:
        return await self.session.scalar(
            select(Assignment).where(
                Assignment.category_id == category_id,
                Assignment.status.in_(OPEN_ASSIGNMENT_STATUSES),
            )
        )

    async def list_open_for_room(self, room_id: int) -> Sequence[Assignment]:
        result = await self.session.scalars(
            select(Assignment)
            .join(Category, Category.id == Assignment.category_id)
            .where(Category.room_id == room_id, Assignment.status.in_(OPEN_ASSIGNMENT_STATUSES))
        )
        return result.all()

    async def declined_member_ids(self, category_id: int, for_date: date) -> set[int]:
        result = await self.session.scalars(
            select(Assignment.member_id).where(
                Assignment.category_id == category_id,
                Assignment.for_date == for_date,
                Assignment.status == AssignmentStatus.DECLINED,
            )
        )
        return set(result.all())

    async def add(self, assignment: Assignment) -> Assignment:
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def transition(
        self,
        assignment: Assignment,
        from_statuses: Iterable[str],
        to_status: str,
        **values: Any,
    ) -> bool:
        """Atomically move an assignment between statuses.

        Returns False if somebody else changed the status first (e.g. a double click),
        which makes concurrent button presses safe on both SQLite and PostgreSQL.
        """
        values["status"] = to_status
        result = await self.session.execute(
            update(Assignment)
            .where(Assignment.id == assignment.id, Assignment.status.in_(list(from_statuses)))
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            return False
        for key, value in values.items():
            set_committed_value(assignment, key, value)
        return True

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

from sqlalchemy import select

from bot.db.models import Absence
from bot.db.repositories.base import Repository


class AbsenceRepo(Repository):
    async def add(self, absence: Absence) -> Absence:
        self.session.add(absence)
        await self.session.flush()
        return absence

    async def current(self, member_id: int, today: date) -> Absence | None:
        """The absence covering ``today`` (or ending later), if any."""
        return await self.session.scalar(
            select(Absence)
            .where(Absence.member_id == member_id, Absence.end_date >= today)
            .order_by(Absence.start_date)
            .limit(1)
        )

    async def overlapping(self, member_ids: Iterable[int], start: date) -> Sequence[Absence]:
        """Absences of these members that end on or after ``start``."""
        ids = list(member_ids)
        if not ids:
            return []
        result = await self.session.scalars(
            select(Absence).where(Absence.member_id.in_(ids), Absence.end_date >= start)
        )
        return result.all()

    async def delete(self, absence: Absence) -> None:
        await self.session.delete(absence)
        await self.session.flush()

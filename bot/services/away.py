"""'I'm away' mode: the member is skipped in every queue until a date (inclusive)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.locks import lock_room, refreshed
from bot.db.models import Absence, Member, Room
from bot.db.repositories import AbsenceRepo, QueueRepo
from bot.services.clock import local_date
from bot.services.errors import ServiceError

MAX_AWAY_DAYS = 365


def is_away(member: Member, today: date) -> bool:
    return member.away_until is not None and member.away_until >= today


def until_for_days(today: date, days: int) -> date:
    """'Away for 3 days' starting today: today and the next two days."""
    return today + timedelta(days=days - 1)


class AwayService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.absences = AbsenceRepo(session)
        self.queue = QueueRepo(session)

    async def go_away(self, room: Room, member: Member, until: date, now: datetime) -> None:
        """Skip the member until ``until``. Skip debts are dropped, out-of-turn credits are kept.

        An open turn of the member is handed over by the scheduler on its next tick.
        """
        today = local_date(room.timezone, now)
        if until < today:
            raise ServiceError("err-date-past")
        await lock_room(self.session, room.id)
        if until > today + timedelta(days=MAX_AWAY_DAYS):
            raise ServiceError("err-date-too-far", days=MAX_AWAY_DAYS)
        absence = await self.absences.current(member.id, today)
        if absence is None:
            await self.absences.add(
                Absence(member_id=member.id, start_date=today, end_date=until, created_at=now)
            )
        else:
            absence.end_date = until
        member.away_until = until
        await self.queue.reset_balances(member_id=member.id, credits=False)
        await self.session.flush()

    async def come_back(self, room: Room, member: Member, now: datetime) -> bool:
        """End the trip early. Returns False if the member wasn't away."""
        await lock_room(self.session, room.id)
        await refreshed(self.session, member)
        today = local_date(room.timezone, now)
        if not is_away(member, today):
            return False
        member.away_until = None
        absence = await self.absences.current(member.id, today)
        if absence is not None:
            if absence.start_date >= today:
                await self.absences.delete(absence)  # left and came back the same day
            else:
                absence.end_date = today - timedelta(days=1)
        await self.queue.reset_balances(member_id=member.id, credits=False)
        await self.session.flush()
        return True

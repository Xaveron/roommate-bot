"""Statistics for a period: who did what, skips, disputes, spending."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import (
    COMPLETED_DUTY_STATUSES,
    Category,
    DutyStatus,
    Member,
    ReviewStatus,
    Room,
)
from bot.db.repositories import CategoryRepo, DutyRepo, ExpenseRepo, MemberRepo
from bot.services.clock import local_now, zone

WEEKLY_SUMMARY_WEEKDAY = 6  # Sunday
WEEKLY_SUMMARY_TIME = time(20, 0)


@dataclass(slots=True)
class MemberStats:
    member: Member
    done: int = 0
    out_of_turn: int = 0
    skipped: int = 0
    spent_cents: int = 0
    by_category: Counter[int] = field(default_factory=Counter)


@dataclass(slots=True)
class PeriodStats:
    start: date  # inclusive, room-local
    end: date  # exclusive, room-local
    categories: list[Category]
    members: list[MemberStats]  # sorted: most done first
    disputed: int = 0
    spent_cents: int = 0

    @property
    def done(self) -> int:
        return sum(m.done for m in self.members)

    @property
    def skipped(self) -> int:
        return sum(m.skipped for m in self.members)

    def category_total(self, category_id: int) -> int:
        return sum(m.by_category[category_id] for m in self.members)


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    return start, end


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def is_weekly_summary_due(room: Room, now: datetime) -> bool:
    moment = local_now(room.timezone, now)
    return (
        room.is_active
        and room.weekly_summary
        and moment.weekday() == WEEKLY_SUMMARY_WEEKDAY
        and moment.time().replace(tzinfo=None) >= WEEKLY_SUMMARY_TIME
        and room.weekly_summary_sent_on != moment.date()
    )


class StatsService:
    def __init__(self, session: AsyncSession) -> None:
        self.duties = DutyRepo(session)
        self.expenses = ExpenseRepo(session)
        self.members = MemberRepo(session)
        self.categories = CategoryRepo(session)

    async def period(self, room: Room, start: date, end: date) -> PeriodStats:
        tz = zone(room.timezone)
        since = datetime.combine(start, time(0), tzinfo=tz)
        until = datetime.combine(end, time(0), tzinfo=tz)
        all_members = {m.id: m for m in await self.members.list(room.id, active_only=False)}
        stats = {m.id: MemberStats(m) for m in all_members.values() if m.is_active}

        def of(member_id: int) -> MemberStats | None:
            if member_id not in stats and member_id in all_members:
                stats[member_id] = MemberStats(all_members[member_id])
            return stats.get(member_id)

        disputed = 0
        for duty in await self.duties.list_for_room(room.id, since, until):
            entry = of(duty.member_id)
            if entry is None:
                continue
            if duty.status in COMPLETED_DUTY_STATUSES:
                if duty.review == ReviewStatus.DISPUTED:
                    disputed += 1
                    continue
                entry.done += 1
                entry.by_category[duty.category_id] += 1
                if duty.status == DutyStatus.OUT_OF_TURN:
                    entry.out_of_turn += 1
            elif duty.status == DutyStatus.SKIPPED:
                entry.skipped += 1

        spent = 0
        for expense in await self.expenses.list_for_room(room.id, since, until):
            if expense.is_settlement:
                continue
            spent += expense.amount_cents
            entry = of(expense.payer_id)
            if entry is not None:
                entry.spent_cents += expense.amount_cents

        return PeriodStats(
            start=start,
            end=end,
            categories=list(await self.categories.list(room.id)),
            members=sorted(
                stats.values(),
                key=lambda m: (-m.done, m.skipped, m.member.joined_at, m.member.id),
            ),
            disputed=disputed,
            spent_cents=spent,
        )

    async def month(self, room: Room, year: int, month: int) -> PeriodStats:
        return await self.period(room, *month_bounds(year, month))

    async def last_week(self, room: Room, now: datetime) -> PeriodStats:
        """Monday..Sunday of the current local week (the summary is posted on Sunday)."""
        today = local_now(room.timezone, now).date()
        start = today - timedelta(days=today.weekday())
        return await self.period(room, start, start + timedelta(days=7))

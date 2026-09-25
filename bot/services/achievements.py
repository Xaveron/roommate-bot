"""Badges roommates earn for their contribution. Names and descriptions live in the locales."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import (
    COMPLETED_DUTY_STATUSES,
    Achievement,
    CategoryKind,
    Duty,
    DutyStatus,
    Member,
    ReviewStatus,
)
from bot.db.repositories import (
    AchievementRepo,
    CategoryRepo,
    DutyRepo,
    ExpenseRepo,
    ShoppingRepo,
)

KIND_THRESHOLD = 10  # bread / water / trash champion
STREAK_THRESHOLD = 10
HELPER_THRESHOLD = 5
CENTURION_THRESHOLD = 100
SHOPPER_THRESHOLD = 10
TREASURER_THRESHOLD = 10

# Badge symbols (names and descriptions are localized).
EMOJI = {
    "first_duty": "🌱",
    "bread_king": "👑",
    "water_carrier": "💧",
    "trash_ninja": "🥷",
    "helper": "🦸",
    "streak_10": "🔥",
    "shopper": "🛒",
    "treasurer": "💰",
    "centurion": "💯",
}

# Display order.
CODES = (
    "first_duty",
    "bread_king",
    "water_carrier",
    "trash_ninja",
    "helper",
    "streak_10",
    "shopper",
    "treasurer",
    "centurion",
)


@dataclass(slots=True)
class Progress:
    """Everything the rules look at, computed from the member's history."""

    completed: int = 0
    out_of_turn: int = 0
    best_streak: int = 0
    by_kind: Counter[str] | None = None
    bought_items: int = 0
    paid_expenses: int = 0


def best_streak(duties: Sequence[Duty]) -> int:
    """Longest run of completed chores without a skip in between (disputed ones don't count)."""
    best = current = 0
    for duty in duties:
        if duty.status == DutyStatus.SKIPPED:
            current = 0
        elif duty.status in COMPLETED_DUTY_STATUSES and duty.review != ReviewStatus.DISPUTED:
            current += 1
            best = max(best, current)
    return best


def earned_codes(progress: Progress) -> set[str]:
    by_kind = progress.by_kind or Counter()
    rules = {
        "first_duty": progress.completed >= 1,
        "bread_king": by_kind[CategoryKind.BREAD] >= KIND_THRESHOLD,
        "water_carrier": by_kind[CategoryKind.WATER] >= KIND_THRESHOLD,
        "trash_ninja": by_kind[CategoryKind.TRASH] >= KIND_THRESHOLD,
        "helper": progress.out_of_turn >= HELPER_THRESHOLD,
        "streak_10": progress.best_streak >= STREAK_THRESHOLD,
        "shopper": progress.bought_items >= SHOPPER_THRESHOLD,
        "treasurer": progress.paid_expenses >= TREASURER_THRESHOLD,
        "centurion": progress.completed >= CENTURION_THRESHOLD,
    }
    return {code for code, ok in rules.items() if ok}


class AchievementService:
    def __init__(self, session: AsyncSession) -> None:
        self.achievements = AchievementRepo(session)
        self.duties = DutyRepo(session)
        self.categories = CategoryRepo(session)
        self.shopping = ShoppingRepo(session)
        self.expenses = ExpenseRepo(session)

    async def progress(self, member: Member) -> Progress:
        duties = await self.duties.list_for_member(member.id)
        kinds = {c.id: c.kind for c in await self.categories.list(member.room_id)}
        completed = [
            d
            for d in duties
            if d.status in COMPLETED_DUTY_STATUSES and d.review != ReviewStatus.DISPUTED
        ]
        return Progress(
            completed=len(completed),
            out_of_turn=sum(1 for d in completed if d.status == DutyStatus.OUT_OF_TURN),
            best_streak=best_streak(duties),
            by_kind=Counter(kinds.get(d.category_id, CategoryKind.CUSTOM) for d in completed),
            bought_items=await self.shopping.bought_count(member.id),
            paid_expenses=await self.expenses.paid_count(member.id),
        )

    async def evaluate(self, member: Member, now: datetime) -> list[str]:
        """Award whatever the member has newly earned; returns the new codes in display order."""
        have = await self.achievements.codes(member.id)
        new = earned_codes(await self.progress(member)) - have
        for code in (c for c in CODES if c in new):
            await self.achievements.add(Achievement(member_id=member.id, code=code, earned_at=now))
        return [c for c in CODES if c in new]

    async def earned_between(
        self, members: Sequence[Member], since: datetime, until: datetime
    ) -> list[tuple[Member, str]]:
        by_id = {m.id: m for m in members}
        return [
            (by_id[a.member_id], a.code)
            for a in await self.achievements.for_members(by_id)
            if since <= a.earned_at < until and a.code in CODES
        ]

    async def for_members(self, members: Sequence[Member]) -> dict[int, list[str]]:
        result: dict[int, list[str]] = {m.id: [] for m in members}
        for achievement in await self.achievements.for_members(result):
            result[achievement.member_id].append(achievement.code)
        return {
            m: sorted((c for c in codes if c in CODES), key=CODES.index)
            for m, codes in result.items()
        }

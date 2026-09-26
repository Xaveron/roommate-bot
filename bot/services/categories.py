"""Chore categories and their reminder settings."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, time

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.locks import lock_room
from bot.db.models import (
    ALL_WEEKDAYS,
    OPEN_ASSIGNMENT_STATUSES,
    AssignmentStatus,
    Category,
    CategoryKind,
    QueueMode,
    Room,
)
from bot.db.repositories import AssignmentRepo, CategoryRepo, QueueRepo
from bot.services.errors import ServiceError
from bot.services.queue import QueueService

MAX_NAME_LENGTH = 32
MAX_EMOJI_LENGTH = 8
DEFAULT_EMOJI = "📌"
DEFAULT_REMINDER_TIME = time(18, 0)


class CategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.categories = CategoryRepo(session)
        self.assignments = AssignmentRepo(session)
        self.queue = QueueService(session)

    async def list(self, room: Room, *, active_only: bool = False) -> Sequence[Category]:
        return await self.categories.list(room.id, active_only=active_only)

    async def get(self, room: Room, category_id: int) -> Category:
        category = await self.categories.get(category_id)
        if category is None or category.room_id != room.id:
            raise ServiceError("err-category-not-found")
        return category

    async def find(self, room: Room, query: str, *, active_only: bool = True) -> Category | None:
        """Find a category by name or emoji: exact match first, then prefix."""
        wanted = query.strip().casefold()
        if not wanted:
            return None
        categories = await self.categories.list(room.id, active_only=active_only)
        for category in categories:
            if wanted in (category.name.casefold(), category.emoji, category.title.casefold()):
                return category
        matches = [c for c in categories if c.name.casefold().startswith(wanted)]
        return matches[0] if len(matches) == 1 else None

    async def create(
        self,
        room: Room,
        *,
        name: str,
        emoji: str | None,
        now: datetime,
        kind: CategoryKind = CategoryKind.CUSTOM,
        reminder_time: time = DEFAULT_REMINDER_TIME,
    ) -> Category:
        name = self._clean_name(name)
        emoji = self._clean_emoji(emoji)
        await lock_room(self.session, room.id)
        if await self.categories.find_by_name(room.id, name) is not None:
            raise ServiceError("err-category-exists", name=name)
        category = await self.categories.add(
            Category(
                room=room,
                room_id=room.id,
                kind=kind,
                name=name,
                emoji=emoji,
                reminder_time=reminder_time,
                reminder_days=ALL_WEEKDAYS,
                is_active=True,
                sort_order=await self.categories.next_sort_order(room.id),
                last_reminded_on=None,
                created_at=now,
            )
        )
        await self.queue.init_category(category)
        return category

    @staticmethod
    def _clean_name(name: str) -> str:
        name = " ".join(name.split())
        if not name or len(name) > MAX_NAME_LENGTH:
            raise ServiceError("err-category-name", max=MAX_NAME_LENGTH)
        return name

    @staticmethod
    def _clean_emoji(emoji: str | None) -> str:
        emoji = (emoji or "").strip() or DEFAULT_EMOJI
        if len(emoji) > MAX_EMOJI_LENGTH or any(ch.isalnum() for ch in emoji):
            raise ServiceError("err-category-emoji")
        return emoji

    async def _lock(self, category: Category) -> None:
        await lock_room(self.session, category.room_id)

    async def rename(self, category: Category, name: str) -> None:
        name = self._clean_name(name)
        await self._lock(category)
        existing = await self.categories.find_by_name(category.room_id, name)
        if existing is not None and existing.id != category.id:
            raise ServiceError("err-category-exists", name=name)
        category.name = name
        await self.session.flush()

    async def set_emoji(self, category: Category, emoji: str | None) -> None:
        emoji = self._clean_emoji(emoji)
        await self._lock(category)
        category.emoji = emoji
        await self.session.flush()

    async def set_reminder_time(self, category: Category, value: time) -> None:
        await self._lock(category)
        category.reminder_time = value
        await self.session.flush()

    async def toggle_day(self, category: Category, weekday: int) -> None:
        if not 0 <= weekday <= 6:
            raise ServiceError("err-generic")
        await self._lock(category)
        days = set(category.reminder_days)
        days.symmetric_difference_update({str(weekday)})
        if not days:
            raise ServiceError("err-no-days")
        category.reminder_days = "".join(sorted(days))
        await self.session.flush()

    async def set_days(self, category: Category, weekdays: Iterable[int]) -> None:
        """Remind on these days of the week (0 = Monday)."""
        days = set(weekdays)
        if not days <= set(range(7)):
            raise ServiceError("err-generic")
        if not days:
            raise ServiceError("err-no-days")
        await self._lock(category)
        category.reminder_days = "".join(str(day) for day in sorted(days))
        await self.session.flush()

    async def toggle_queue_mode(self, category: Category) -> None:
        """Switch round robin <-> fair. Debts and credits start from scratch."""
        await self._lock(category)
        is_fair = category.queue_mode == QueueMode.FAIR
        category.queue_mode = QueueMode.ROUND_ROBIN if is_fair else QueueMode.FAIR
        await QueueRepo(self.session).reset_balances(category_id=category.id)
        await self.session.flush()

    async def set_every_day(self, category: Category) -> None:
        await self._lock(category)
        category.reminder_days = ALL_WEEKDAYS
        await self.session.flush()

    async def set_active(self, category: Category, active: bool, now: datetime) -> None:
        await self._lock(category)
        category.is_active = active
        if not active:
            await self._cancel_open(category, now)
        await self.session.flush()

    async def delete(self, category: Category) -> None:
        await self._lock(category)
        await self.categories.delete(category)

    async def _cancel_open(self, category: Category, now: datetime) -> None:
        assignment = await self.assignments.get_open(category.id)
        if assignment is not None:
            await self.assignments.transition(
                assignment, OPEN_ASSIGNMENT_STATUSES, AssignmentStatus.CANCELLED, closed_at=now
            )

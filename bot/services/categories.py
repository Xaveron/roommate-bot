"""Chore categories and their reminder settings."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, time

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import (
    ALL_WEEKDAYS,
    OPEN_ASSIGNMENT_STATUSES,
    AssignmentStatus,
    Category,
    CategoryKind,
    Room,
)
from bot.db.repositories import AssignmentRepo, CategoryRepo
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
        name = " ".join(name.split())
        if not name or len(name) > MAX_NAME_LENGTH:
            raise ServiceError("err-category-name", max=MAX_NAME_LENGTH)
        emoji = (emoji or "").strip() or DEFAULT_EMOJI
        if len(emoji) > MAX_EMOJI_LENGTH or any(ch.isalnum() for ch in emoji):
            raise ServiceError("err-category-emoji")
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

    async def set_reminder_time(self, category: Category, value: time) -> None:
        category.reminder_time = value
        await self.session.flush()

    async def toggle_day(self, category: Category, weekday: int) -> None:
        if not 0 <= weekday <= 6:
            raise ServiceError("err-generic")
        days = set(category.reminder_days)
        days.symmetric_difference_update({str(weekday)})
        if not days:
            raise ServiceError("err-no-days")
        category.reminder_days = "".join(sorted(days))
        await self.session.flush()

    async def set_every_day(self, category: Category) -> None:
        category.reminder_days = ALL_WEEKDAYS
        await self.session.flush()

    async def set_active(self, category: Category, active: bool, now: datetime) -> None:
        category.is_active = active
        if not active:
            await self._cancel_open(category, now)
        await self.session.flush()

    async def delete(self, category: Category) -> None:
        await self.categories.delete(category)

    async def _cancel_open(self, category: Category, now: datetime) -> None:
        assignment = await self.assignments.get_open(category.id)
        if assignment is not None:
            await self.assignments.transition(
                assignment, OPEN_ASSIGNMENT_STATUSES, AssignmentStatus.CANCELLED, closed_at=now
            )

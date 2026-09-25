"""Decides which reminders have to be delivered right now.

A scheduler tick calls :meth:`ReminderService.plan_room` for every room. The planner creates or
updates assignments and returns those whose reminder must be (re)delivered; the Telegram layer
sends them and calls :meth:`ReminderService.mark_delivered`.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Assignment, AssignmentStatus, Category, Room
from bot.db.repositories import AssignmentRepo, CategoryRepo
from bot.services.clock import is_quiet, local_now
from bot.services.tasks import TaskService

S = AssignmentStatus


def is_reminder_day(days: str, day: date) -> bool:
    return str(day.weekday()) in days


def is_regular_reminder_due(category: Category, moment: datetime) -> bool:
    """Today's scheduled reminder hasn't been issued yet and its time has come.

    A reminder scheduled before the category existed is skipped: a room created at 23:00
    doesn't get the 18:00 reminders of that day, but a time set to 23:05 fires today.
    """
    today = moment.date()
    scheduled = datetime.combine(today, category.reminder_time, tzinfo=moment.tzinfo)
    return (
        is_reminder_day(category.reminder_days, today)
        and moment >= scheduled >= category.created_at
        and category.last_reminded_on != today
    )


def room_is_quiet(room: Room, now: datetime) -> bool:
    moment = local_now(room.timezone, now).time().replace(tzinfo=None)
    return is_quiet(moment, room.quiet_hours_start, room.quiet_hours_end)


class ReminderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.assignments = AssignmentRepo(session)
        self.categories = CategoryRepo(session)
        self.tasks = TaskService(session)

    async def plan_room(self, room: Room, now: datetime) -> list[Assignment]:
        """Assignments whose reminder must be delivered now (empty during quiet hours)."""
        if not room.is_active or room_is_quiet(room, now):
            return []
        moment = local_now(room.timezone, now)
        due: list[Assignment] = []
        for category in await self.categories.list(room.id, active_only=True):
            assignment = await self._plan_category(category, moment, now)
            if assignment is not None:
                due.append(assignment)
        return due

    async def _plan_category(
        self, category: Category, moment: datetime, now: datetime
    ) -> Assignment | None:
        today = moment.date()
        open_assignment = await self.assignments.get_open(category.id)

        # The member left or went away: cancel, and hand over at once if today's turn is running.
        handover = False
        if open_assignment is not None and not open_assignment.member.is_available(today):
            was_snoozed = open_assignment.status == S.SNOOZED
            await self.assignments.transition(
                open_assignment, [open_assignment.status], S.CANCELLED, closed_at=now
            )
            handover = category.last_reminded_on == today and not was_snoozed
            open_assignment = None
            await self.session.flush()

        if open_assignment is None:
            if not (handover or is_regular_reminder_due(category, moment)):
                return None
            category.last_reminded_on = today
            return await self.tasks.assign_next(category, now)

        if open_assignment.status == S.SNOOZED:
            time_reached = moment.time().replace(tzinfo=None) >= category.reminder_time
            if open_assignment.remind_on is not None and (
                open_assignment.remind_on < today
                or (open_assignment.remind_on == today and time_reached)
            ):
                self._reissue(open_assignment, category, today)
                return open_assignment
            return None

        # Pending / accepted.
        if open_assignment.last_reminded_at is None:
            return open_assignment  # created earlier (e.g. during quiet hours), not sent yet
        if open_assignment.for_date < today and is_regular_reminder_due(category, moment):
            # A new day and the chore is still not done: remind the same member again.
            self._reissue(open_assignment, category, today)
            return open_assignment
        return None

    @staticmethod
    def _reissue(assignment: Assignment, category: Category, today: date) -> None:
        assignment.status = S.PENDING
        assignment.for_date = today
        assignment.remind_on = None
        assignment.last_reminded_at = None
        assignment.reminders_sent = 0
        category.last_reminded_on = today

    @staticmethod
    def mark_delivered(
        assignment: Assignment, now: datetime, chat_id: int | None, message_id: int | None
    ) -> None:
        assignment.last_reminded_at = now
        assignment.reminders_sent += 1
        assignment.message_chat_id = chat_id
        assignment.message_id = message_id

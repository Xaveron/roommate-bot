"""Decides which reminders have to be delivered right now.

A scheduler tick calls :meth:`ReminderService.plan_room` for every room. The planner creates or
updates assignments and returns what must be sent; the Telegram layer sends it and calls
:meth:`ReminderService.mark_delivered` / :meth:`ReminderService.mark_nudged`.

Escalation of an unanswered ("pending") reminder, with N = ``Room.repeat_after_hours``:

1. the reminder itself;
2. after N hours without an answer, the same reminder once more;
3. after another N hours, a friendly nudge in the group chat. Then silence until tomorrow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Assignment, AssignmentStatus, Category, Room
from bot.db.repositories import AssignmentRepo, CategoryRepo
from bot.services.clock import is_quiet, local_now
from bot.services.tasks import TaskService

S = AssignmentStatus

# reminders_sent values: 1 = first reminder, 2 = repeated once, 3 = group nudge posted.
REPEAT_REMINDER_AT = 1
NUDGE_AT = 2


class DeliveryKind(StrEnum):
    REMINDER = "reminder"  # (repeated) reminder to the member
    NUDGE = "nudge"  # "X is keeping quiet about bread" in the group chat


@dataclass(slots=True)
class Delivery:
    assignment: Assignment
    kind: DeliveryKind = DeliveryKind.REMINDER


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

    async def plan_room(self, room: Room, now: datetime) -> list[Delivery]:
        """What must be delivered now (nothing during quiet hours)."""
        if not room.is_active or room_is_quiet(room, now):
            return []
        moment = local_now(room.timezone, now)
        due: list[Delivery] = []
        for category in await self.categories.list(room.id, active_only=True):
            delivery = await self._plan_category(room, category, moment, now)
            if delivery is not None:
                due.append(delivery)
        return due

    async def _plan_category(
        self, room: Room, category: Category, moment: datetime, now: datetime
    ) -> Delivery | None:
        assignment = await self._plan_assignment(category, moment, now)
        if assignment is not None:
            return Delivery(assignment)
        return await self._plan_escalation(room, category, now)

    async def _plan_escalation(
        self, room: Room, category: Category, now: datetime
    ) -> Delivery | None:
        """Repeat an unanswered reminder, then nudge the member in the group chat."""
        assignment = await self.assignments.get_open(category.id)
        if (
            assignment is None
            or assignment.status != S.PENDING
            or assignment.last_reminded_at is None
            or room.repeat_after_hours <= 0
            or now - assignment.last_reminded_at < timedelta(hours=room.repeat_after_hours)
        ):
            return None
        if assignment.reminders_sent == REPEAT_REMINDER_AT:
            return Delivery(assignment, DeliveryKind.REMINDER)
        if assignment.reminders_sent == NUDGE_AT:
            return Delivery(assignment, DeliveryKind.NUDGE)
        return None

    async def _plan_assignment(
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

    @staticmethod
    def mark_nudged(assignment: Assignment, now: datetime) -> None:
        assignment.last_reminded_at = now
        assignment.reminders_sent += 1

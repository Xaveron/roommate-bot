"""Chore lifecycle: accepting, completing, snoozing and declining turns."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import (
    OPEN_ASSIGNMENT_STATUSES,
    Assignment,
    AssignmentStatus,
    Category,
    Duty,
    DutyStatus,
    Member,
)
from bot.db.repositories import AssignmentRepo, DutyRepo, MemberRepo
from bot.services.clock import local_date
from bot.services.errors import ServiceError
from bot.services.queue import QueueService

S = AssignmentStatus


@dataclass(slots=True)
class Completion:
    category: Category
    member: Member
    duty: Duty
    in_turn: bool
    next_member: Member | None
    # The finished assignment when the turn was completed via reminder buttons or /done.
    assignment: Assignment | None = None
    # Somebody else's open assignment closed because the chore was done out of turn.
    covered: Assignment | None = None


@dataclass(slots=True)
class Handover:
    declined: Assignment
    # New assignment for the next person, or None if nobody else is available today.
    next_assignment: Assignment | None


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.assignments = AssignmentRepo(session)
        self.duties = DutyRepo(session)
        self.members = MemberRepo(session)
        self.queue = QueueService(session)

    # --- helpers -------------------------------------------------------------------------

    async def _own_open(
        self, assignment_id: int, user_id: int, allowed: Iterable[str]
    ) -> Assignment:
        assignment = await self.assignments.get(assignment_id)
        if assignment is None or assignment.status not in set(allowed):
            raise ServiceError("err-assignment-closed")
        if assignment.member.telegram_user_id != user_id:
            raise ServiceError("err-not-your-turn")
        return assignment

    async def _transition(
        self, assignment: Assignment, from_statuses: Iterable[str], to: str, **values: object
    ) -> None:
        if not await self.assignments.transition(assignment, from_statuses, to, **values):
            raise ServiceError("err-assignment-closed")

    async def assign_next(self, category: Category, now: datetime) -> Assignment | None:
        """Create a pending assignment for whoever is next today (skipping today's decliners)."""
        today = local_date(category.room.timezone, now)
        declined = await self.assignments.declined_member_ids(category.id, today)
        member = await self.queue.current(category, today, exclude=declined)
        if member is None:
            return None
        return await self.assignments.add(
            Assignment(
                category=category,
                member=member,
                status=S.PENDING,
                for_date=today,
                reminders_sent=0,
                created_at=now,
            )
        )

    # --- reminder buttons ----------------------------------------------------------------

    async def accept(self, assignment_id: int, user_id: int) -> Assignment:
        """ "I'll buy it": waiting for the member to press "Done"."""
        assignment = await self._own_open(assignment_id, user_id, [S.PENDING])
        await self._transition(assignment, [S.PENDING], S.ACCEPTED)
        return assignment

    async def complete(self, assignment_id: int, user_id: int, now: datetime) -> Completion:
        assignment = await self._own_open(assignment_id, user_id, [S.PENDING, S.ACCEPTED])
        return await self._complete_assignment(assignment, now)

    async def still_have(self, assignment_id: int, user_id: int, now: datetime) -> Assignment:
        """ "We still have some": the queue doesn't move, remind the same member tomorrow."""
        assignment = await self._own_open(assignment_id, user_id, [S.PENDING, S.ACCEPTED])
        today = local_date(assignment.category.room.timezone, now)
        await self._transition(
            assignment,
            [S.PENDING, S.ACCEPTED],
            S.SNOOZED,
            remind_on=today + timedelta(days=1),
        )
        await self.duties.add(
            category_id=assignment.category_id,
            member_id=assignment.member_id,
            status=DutyStatus.STILL_HAVE,
            created_at=now,
            assignment_id=assignment.id,
        )
        return assignment

    async def decline(self, assignment_id: int, user_id: int, now: datetime) -> Handover:
        """ "Can't today": the member gets a skip debt, the turn goes to the next person."""
        assignment = await self._own_open(assignment_id, user_id, [S.PENDING, S.ACCEPTED])
        category = assignment.category
        today = local_date(category.room.timezone, now)
        await self._transition(assignment, [S.PENDING, S.ACCEPTED], S.DECLINED, closed_at=now)
        await self.duties.add(
            category_id=category.id,
            member_id=assignment.member_id,
            status=DutyStatus.SKIPPED,
            created_at=now,
            assignment_id=assignment.id,
        )
        await self.queue.skip(category, assignment.member_id, today)
        await self.session.flush()
        return Handover(declined=assignment, next_assignment=await self.assign_next(category, now))

    # --- manual marks --------------------------------------------------------------------

    async def mark_done(self, category: Category, member: Member, now: datetime) -> Completion:
        """/done: counts as the member's turn if it is theirs, otherwise as out of turn."""
        today = local_date(category.room.timezone, now)
        open_assignment = await self.assignments.get_open(category.id)
        if open_assignment is not None and open_assignment.member_id == member.id:
            return await self._complete_assignment(open_assignment, now)

        if open_assignment is None:
            declined = await self.assignments.declined_member_ids(category.id, today)
            current = await self.queue.current(category, today, exclude=declined)
            if current is not None and current.id == member.id:
                return await self._finish(category, member, now, in_turn=True)

        covered = None
        if open_assignment is not None and await self.assignments.transition(
            open_assignment, OPEN_ASSIGNMENT_STATUSES, S.COVERED, closed_at=now
        ):
            covered = open_assignment
        completion = await self._finish(category, member, now, in_turn=False)
        completion.covered = covered
        return completion

    async def _complete_assignment(self, assignment: Assignment, now: datetime) -> Completion:
        await self._transition(assignment, OPEN_ASSIGNMENT_STATUSES, S.DONE, closed_at=now)
        completion = await self._finish(
            assignment.category, assignment.member, now, in_turn=True, assignment=assignment
        )
        return completion

    async def _finish(
        self,
        category: Category,
        member: Member,
        now: datetime,
        *,
        in_turn: bool,
        assignment: Assignment | None = None,
    ) -> Completion:
        today = local_date(category.room.timezone, now)
        duty = await self.duties.add(
            category_id=category.id,
            member_id=member.id,
            status=DutyStatus.DONE if in_turn else DutyStatus.OUT_OF_TURN,
            created_at=now,
            assignment_id=assignment.id if assignment else None,
        )
        if in_turn:
            await self.queue.complete(category, member.id, today)
        else:
            await self.queue.out_of_turn(category, member.id, today)
        # The chore is covered for today: no scheduled reminder for the next person today.
        category.last_reminded_on = today
        await self.session.flush()
        return Completion(
            category=category,
            member=member,
            duty=duty,
            in_turn=in_turn,
            next_member=await self.queue.current(category, today),
            assignment=assignment,
        )

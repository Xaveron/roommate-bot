"""Roommates confirm (👍) or dispute (🤨) a completed chore.

A record becomes *confirmed* or *disputed* as soon as a strict majority of the roommates who
may vote (everybody except the performer) agrees. A disputed record doesn't count: it's
excluded from the statistics, in round robin the queue effect is taken back, and the money
entered for it is removed from the balances.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import (
    COMPLETED_DUTY_STATUSES,
    Duty,
    DutyStatus,
    DutyVote,
    Member,
    ReviewStatus,
    Vote,
)
from bot.db.repositories import CategoryRepo, DutyRepo, MemberRepo, VoteRepo
from bot.services.clock import local_date
from bot.services.errors import ServiceError
from bot.services.finance import FinanceService
from bot.services.queue import QueueService

REVIEW_WINDOW = timedelta(hours=48)


@dataclass(slots=True)
class VoteOutcome:
    duty: Duty
    up: int
    down: int
    voters: int
    # Set when this vote decided the review: CONFIRMED or DISPUTED.
    decided: ReviewStatus | None = None


def decide(up: int, down: int, voters: int) -> ReviewStatus | None:
    """Strict majority of the eligible voters."""
    if voters <= 0:
        return None
    if down * 2 > voters:
        return ReviewStatus.DISPUTED
    if up * 2 > voters:
        return ReviewStatus.CONFIRMED
    return None


class ReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.duties = DutyRepo(session)
        self.votes = VoteRepo(session)
        self.members = MemberRepo(session)
        self.categories = CategoryRepo(session)

    async def voters(self, room_id: int, performer_id: int) -> int:
        return sum(1 for m in await self.members.list(room_id) if m.id != performer_id)

    async def vote(self, duty_id: int, voter: Member, vote: Vote, now: datetime) -> VoteOutcome:
        duty = await self.duties.get(duty_id)
        category = await self.categories.get(duty.category_id) if duty else None
        if duty is None or category is None or category.room_id != voter.room_id:
            raise ServiceError("err-vote-closed")
        if (
            duty.status not in COMPLETED_DUTY_STATUSES
            or duty.review != ReviewStatus.OPEN
            or now - duty.created_at > REVIEW_WINDOW
        ):
            raise ServiceError("err-vote-closed")
        if duty.member_id == voter.id:
            raise ServiceError("err-vote-self")

        existing = await self.votes.get(duty.id, voter.id)
        if existing is not None and existing.vote == vote:
            raise ServiceError("err-vote-already")
        if existing is None:
            await self.votes.add(
                DutyVote(duty_id=duty.id, member_id=voter.id, vote=vote, created_at=now)
            )
        else:
            existing.vote = vote
            await self.session.flush()

        up, down = await self.votes.tally(duty.id)
        voters = await self.voters(category.room_id, duty.member_id)
        decided = decide(up, down, voters)
        if decided is not None:
            duty.review = decided
            if decided == ReviewStatus.DISPUTED:
                await QueueService(self.session).dispute(
                    category,
                    duty.member_id,
                    local_date(category.room.timezone, now),
                    in_turn=duty.status == DutyStatus.DONE,
                )
                await FinanceService(self.session).drop_duty_expense(duty)
            await self.session.flush()
        return VoteOutcome(duty=duty, up=up, down=down, voters=voters, decided=decided)

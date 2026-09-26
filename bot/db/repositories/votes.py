from __future__ import annotations

from collections.abc import Collection

from sqlalchemy import func, select

from bot.db.models import DutyVote, Vote
from bot.db.repositories.base import Repository


class VoteRepo(Repository):
    async def get(self, duty_id: int, member_id: int) -> DutyVote | None:
        return await self.session.scalar(
            select(DutyVote).where(DutyVote.duty_id == duty_id, DutyVote.member_id == member_id)
        )

    async def add(self, vote: DutyVote) -> DutyVote:
        self.session.add(vote)
        await self.session.flush()
        return vote

    async def tally(self, duty_id: int) -> tuple[int, int]:
        """(👍, 🤨) counts for a duty."""
        result = await self.session.execute(
            select(DutyVote.vote, func.count())
            .where(DutyVote.duty_id == duty_id)
            .group_by(DutyVote.vote)
        )
        counts = dict(result.all())
        return counts.get(Vote.UP, 0), counts.get(Vote.DOWN, 0)

    async def tallies(self, duty_ids: Collection[int]) -> dict[int, tuple[int, int]]:
        """(👍, 🤨) counts of several duties at once."""
        result = await self.session.execute(
            select(DutyVote.duty_id, DutyVote.vote, func.count())
            .where(DutyVote.duty_id.in_(list(duty_ids)))
            .group_by(DutyVote.duty_id, DutyVote.vote)
        )
        tallies: dict[int, tuple[int, int]] = {}
        for duty_id, vote, count in result.all():
            up, down = tallies.get(duty_id, (0, 0))
            tallies[duty_id] = (up + count, down) if vote == Vote.UP else (up, down + count)
        return tallies

    async def of_member(self, member_id: int, duty_ids: Collection[int]) -> dict[int, str]:
        """How the member voted on each of the duties they voted on."""
        result = await self.session.execute(
            select(DutyVote.duty_id, DutyVote.vote).where(
                DutyVote.member_id == member_id, DutyVote.duty_id.in_(list(duty_ids))
            )
        )
        return {duty_id: vote for duty_id, vote in result.all()}

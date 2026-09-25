from __future__ import annotations

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

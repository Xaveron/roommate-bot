"""Queue algorithm (pure functions) and its database-backed wrapper.

The round-robin queue is an ordered list: whoever did the chore least recently goes first.

* Completing a turn moves the member to the end of the list.
* "Can't today" gives the member a *skip debt*: the turn goes to the next person today, and
  debtors are always picked first afterwards until the debt is worked off.
* Doing the chore out of turn pays off a debt, or otherwise earns a *credit*: when the member
  reaches the front of the queue, the credit is spent and their turn is skipped.
* Unavailable members (left the room / away) are ignored but keep their place.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Category, Member, QueueState
from bot.db.repositories import CategoryRepo, MemberRepo, QueueRepo


@dataclass(slots=True)
class QueueEntry:
    member_id: int
    position: int
    skip_debt: int = 0
    credit: int = 0
    available: bool = True


def ordered(entries: Sequence[QueueEntry]) -> list[QueueEntry]:
    return sorted(entries, key=lambda e: (e.position, e.member_id))


def _eligible(
    entries: Sequence[QueueEntry], exclude: Collection[int] = frozenset()
) -> list[QueueEntry]:
    return [e for e in ordered(entries) if e.available and e.member_id not in exclude]


def _find(entries: Sequence[QueueEntry], member_id: int) -> QueueEntry:
    for entry in entries:
        if entry.member_id == member_id:
            return entry
    raise KeyError(f"Member {member_id} is not in the queue")


def _move_to_end(entries: Sequence[QueueEntry], entry: QueueEntry) -> None:
    entry.position = max(e.position for e in entries) + 1


def _renumber(entries: Sequence[QueueEntry]) -> None:
    for index, entry in enumerate(ordered(entries)):
        entry.position = index


def _spend_front_credits(entries: Sequence[QueueEntry]) -> None:
    """A member with a credit who reaches the front has this turn skipped."""
    for _ in range(sum(e.credit for e in entries)):
        eligible = _eligible(entries)
        if not eligible:
            return
        front = eligible[0]
        if front.skip_debt > 0 or front.credit == 0:
            return
        front.credit -= 1
        _move_to_end(entries, front)


def pick_next(
    entries: Sequence[QueueEntry], *, exclude: Collection[int] = frozenset()
) -> int | None:
    """Return whose turn it is, or None if nobody is available."""
    eligible = _eligible(entries, exclude)
    if not eligible:
        return None
    for entry in eligible:
        if entry.skip_debt > 0:
            return entry.member_id
    for entry in eligible:
        if entry.credit == 0:
            return entry.member_id
    return eligible[0].member_id


def apply_completion(entries: Sequence[QueueEntry], member_id: int) -> None:
    """The member did the chore in turn."""
    entry = _find(entries, member_id)
    if entry.skip_debt > 0:
        entry.skip_debt -= 1
    _move_to_end(entries, entry)
    _spend_front_credits(entries)
    _renumber(entries)


def apply_out_of_turn(entries: Sequence[QueueEntry], member_id: int) -> None:
    """The member did the chore although it wasn't their turn."""
    entry = _find(entries, member_id)
    if entry.skip_debt > 0:
        entry.skip_debt -= 1
    else:
        entry.credit += 1
    _spend_front_credits(entries)
    _renumber(entries)


def apply_skip(entries: Sequence[QueueEntry], member_id: int) -> None:
    """The member couldn't do it today and owes a turn."""
    _find(entries, member_id).skip_debt += 1


def upcoming(entries: Sequence[QueueEntry], first: int | None, count: int) -> list[int]:
    """Predict the next ``count`` turns starting with ``first``, if everyone does their turn."""
    if first is None or count <= 0:
        return []
    simulated = [dataclasses.replace(e) for e in entries]
    result = [first]
    current: int | None = first
    while current is not None and len(result) < count:
        apply_completion(simulated, current)
        current = pick_next(simulated)
        if current is not None:
            result.append(current)
    return result


@dataclass(slots=True)
class QueueSnapshot:
    current: Member | None
    upcoming: list[Member]
    entries: dict[int, QueueEntry]


class QueueService:
    """Loads queue state from the database, applies the algorithm and writes it back."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.queue = QueueRepo(session)
        self.members = MemberRepo(session)
        self.categories = CategoryRepo(session)

    async def _load(
        self, category: Category, today: date
    ) -> tuple[list[QueueEntry], dict[int, QueueState]]:
        states = list(await self.queue.list_for_category(category.id, for_update=True))
        members = {m.id: m for m in await self.members.list(category.room_id, active_only=False)}
        known = {s.member_id for s in states}
        # Self-healing: every active member must have a place in the queue.
        for member in members.values():
            if member.is_active and member.id not in known:
                position = await self.queue.next_position(category.id)
                states.append(await self.queue.add(category.id, member.id, position))
        entries = [
            QueueEntry(
                member_id=s.member_id,
                position=s.position,
                skip_debt=s.skip_debt,
                credit=s.credit,
                available=s.member_id in members and members[s.member_id].is_available(today),
            )
            for s in states
        ]
        return entries, {s.member_id: s for s in states}

    @staticmethod
    def _store(entries: Sequence[QueueEntry], rows: dict[int, QueueState]) -> None:
        for entry in entries:
            row = rows[entry.member_id]
            row.position = entry.position
            row.skip_debt = entry.skip_debt
            row.credit = entry.credit

    async def current(
        self, category: Category, today: date, *, exclude: Collection[int] = frozenset()
    ) -> Member | None:
        entries, _ = await self._load(category, today)
        member_id = pick_next(entries, exclude=exclude)
        return None if member_id is None else await self.members.get(member_id)

    async def complete(self, category: Category, member_id: int, today: date) -> None:
        entries, rows = await self._load(category, today)
        apply_completion(entries, member_id)
        self._store(entries, rows)

    async def out_of_turn(self, category: Category, member_id: int, today: date) -> None:
        entries, rows = await self._load(category, today)
        apply_out_of_turn(entries, member_id)
        self._store(entries, rows)

    async def skip(self, category: Category, member_id: int, today: date) -> None:
        entries, rows = await self._load(category, today)
        apply_skip(entries, member_id)
        self._store(entries, rows)

    async def snapshot(
        self,
        category: Category,
        today: date,
        *,
        current_member_id: int | None = None,
        exclude: Collection[int] = frozenset(),
    ) -> QueueSnapshot:
        """Current member (the open assignment if any) and the predicted order after them."""
        entries, _ = await self._load(category, today)
        known = {e.member_id for e in entries}
        first = current_member_id if current_member_id in known else None
        first = first or pick_next(entries, exclude=exclude)
        available = sum(1 for e in entries if e.available)
        order = upcoming(entries, first, available)
        members = [m for m in [await self.members.get(i) for i in order] if m is not None]
        return QueueSnapshot(
            current=members[0] if members else None,
            upcoming=members[1:],
            entries={e.member_id: e for e in entries},
        )

    async def enqueue_member(self, room_id: int, member_id: int) -> None:
        """Put a (re)joining member at the end of every queue of the room, without debts."""
        for category in await self.categories.list(room_id):
            state = await self.queue.get(category.id, member_id)
            position = await self.queue.next_position(category.id)
            if state is None:
                await self.queue.add(category.id, member_id, position)
            else:
                state.position, state.skip_debt, state.credit = position, 0, 0

    async def init_category(self, category: Category) -> None:
        """Queue for a new category: active members in the order they joined."""
        for position, member in enumerate(await self.members.list(category.room_id)):
            await self.queue.add(category.id, member.id, position)

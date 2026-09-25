"""Queue algorithm (pure functions) and its database-backed wrapper.

**Round robin** (default): the queue is an ordered list, whoever did the chore least recently
goes first.

* Completing a turn moves the member to the end of the list.
* "Can't today" gives the member a *skip debt*: the turn goes to the next person today, and
  debtors are always picked first afterwards until the debt is worked off.
* Doing the chore out of turn pays off a debt, or otherwise earns a *credit*: when the member
  reaches the front of the queue, the credit is spent and their turn is skipped.

**Fair**: the next one is whoever did the chore least often during the last 30 days; ties are
broken by the round-robin order. Counts are divided by the number of days the member was
actually present (not away, already living in the room), so coming back from a trip or joining
late doesn't create a debt. Skips and out-of-turn work are reflected by the counts themselves,
so debts and credits are not used in this mode.

Unavailable members (left the room / away) are ignored in both modes but keep their place.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from fractions import Fraction

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Category, Member, QueueMode, QueueState
from bot.db.repositories import AbsenceRepo, CategoryRepo, DutyRepo, MemberRepo, QueueRepo
from bot.services.clock import local_date, zone

FAIR_WINDOW_DAYS = 30


@dataclass(slots=True)
class QueueEntry:
    member_id: int
    position: int
    skip_debt: int = 0
    credit: int = 0
    available: bool = True


@dataclass(slots=True)
class FairStats:
    """Completed chores in the fair window and days each member was present in it."""

    counts: dict[int, int] = field(default_factory=dict)
    presence: dict[int, int] = field(default_factory=dict)

    def score(self, member_id: int) -> Fraction:
        days = self.presence.get(member_id, FAIR_WINDOW_DAYS)
        return Fraction(self.counts.get(member_id, 0), max(days, 1))

    def copy(self) -> FairStats:
        return FairStats(dict(self.counts), dict(self.presence))


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


def _move_to_front(entries: Sequence[QueueEntry], entry: QueueEntry) -> None:
    entry.position = min(e.position for e in entries) - 1


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
    entries: Sequence[QueueEntry],
    *,
    exclude: Collection[int] = frozenset(),
    stats: FairStats | None = None,
) -> int | None:
    """Return whose turn it is, or None if nobody is available.

    Passing ``stats`` switches to the fair mode.
    """
    eligible = _eligible(entries, exclude)
    if not eligible:
        return None
    if stats is not None:
        # `eligible` is in queue order and min() keeps the first of equal scores.
        return min(eligible, key=lambda e: stats.score(e.member_id)).member_id
    for entry in eligible:
        if entry.skip_debt > 0:
            return entry.member_id
    for entry in eligible:
        if entry.credit == 0:
            return entry.member_id
    return eligible[0].member_id


def apply_completion(entries: Sequence[QueueEntry], member_id: int, *, fair: bool = False):
    """The member did the chore in turn."""
    entry = _find(entries, member_id)
    if not fair and entry.skip_debt > 0:
        entry.skip_debt -= 1
    _move_to_end(entries, entry)
    if not fair:
        _spend_front_credits(entries)
    _renumber(entries)


def apply_out_of_turn(entries: Sequence[QueueEntry], member_id: int, *, fair: bool = False):
    """The member did the chore although it wasn't their turn."""
    entry = _find(entries, member_id)
    if fair:
        _move_to_end(entries, entry)
    elif entry.skip_debt > 0:
        entry.skip_debt -= 1
    else:
        entry.credit += 1
    if not fair:
        _spend_front_credits(entries)
    _renumber(entries)


def apply_skip(entries: Sequence[QueueEntry], member_id: int, *, fair: bool = False) -> None:
    """The member couldn't do it today and owes a turn (in fair mode the counts show it)."""
    if not fair:
        _find(entries, member_id).skip_debt += 1


def apply_dispute(
    entries: Sequence[QueueEntry], member_id: int, *, in_turn: bool, fair: bool = False
) -> None:
    """Roommates voted a completion down: take back what it gave the member.

    In the fair mode the disputed record is simply not counted any more; the member only goes
    back to the front, so that among equal counts they are the next one.
    """
    entry = _find(entries, member_id)
    if fair:
        _move_to_front(entries, entry)
        _renumber(entries)
        return
    if not in_turn and entry.credit > 0:
        entry.credit -= 1  # the credit for the fake out-of-turn work is withdrawn
    else:
        entry.skip_debt += 1  # the turn (or the spent credit) is owed again


def upcoming(
    entries: Sequence[QueueEntry],
    first: int | None,
    count: int,
    stats: FairStats | None = None,
) -> list[int]:
    """Predict the next ``count`` turns starting with ``first``, if everyone does their turn."""
    if first is None or count <= 0:
        return []
    simulated = [dataclasses.replace(e) for e in entries]
    simulated_stats = stats.copy() if stats is not None else None
    result = [first]
    current: int | None = first
    while current is not None and len(result) < count:
        apply_completion(simulated, current, fair=simulated_stats is not None)
        if simulated_stats is not None:
            simulated_stats.counts[current] = simulated_stats.counts.get(current, 0) + 1
        current = pick_next(simulated, stats=simulated_stats)
        if current is not None:
            result.append(current)
    return result


def presence_days(
    window_start: date,
    today: date,
    joined_on: date,
    absences: Iterable[tuple[date, date]],
) -> int:
    """Days in [window_start, today] the member lived in the room and wasn't away (≥ 1)."""
    start = max(window_start, joined_on)
    if start > today:
        return 1
    days = {start + timedelta(days=i) for i in range((today - start).days + 1)}
    for absence_start, absence_end in absences:
        day = max(absence_start, start)
        while day <= min(absence_end, today):
            days.discard(day)
            day += timedelta(days=1)
    return max(len(days), 1)


@dataclass(slots=True)
class QueueSnapshot:
    current: Member | None
    upcoming: list[Member]
    entries: dict[int, QueueEntry]
    stats: FairStats | None = None


class QueueService:
    """Loads queue state from the database, applies the algorithm and writes it back."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.queue = QueueRepo(session)
        self.members = MemberRepo(session)
        self.categories = CategoryRepo(session)
        self.duties = DutyRepo(session)
        self.absences = AbsenceRepo(session)

    async def _load(
        self, category: Category, today: date
    ) -> tuple[list[QueueEntry], dict[int, QueueState], dict[int, Member]]:
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
        return entries, {s.member_id: s for s in states}, members

    async def fair_stats(
        self, category: Category, today: date, members: dict[int, Member]
    ) -> FairStats | None:
        """Statistics for the fair mode, or None if the category uses round robin."""
        if category.queue_mode != QueueMode.FAIR:
            return None
        timezone = category.room.timezone
        window_start = today - timedelta(days=FAIR_WINDOW_DAYS - 1)
        since = datetime.combine(window_start, time(0), tzinfo=zone(timezone))
        absences: dict[int, list[tuple[date, date]]] = {}
        for absence in await self.absences.overlapping(members, window_start):
            absences.setdefault(absence.member_id, []).append(
                (absence.start_date, absence.end_date)
            )
        return FairStats(
            counts=await self.duties.completed_counts(category.id, since),
            presence={
                member.id: presence_days(
                    window_start,
                    today,
                    local_date(timezone, member.joined_at),
                    absences.get(member.id, []),
                )
                for member in members.values()
            },
        )

    @staticmethod
    def _store(entries: Sequence[QueueEntry], rows: dict[int, QueueState]) -> None:
        for entry in entries:
            row = rows[entry.member_id]
            row.position = entry.position
            row.skip_debt = entry.skip_debt
            row.credit = entry.credit

    @staticmethod
    def _is_fair(category: Category) -> bool:
        return category.queue_mode == QueueMode.FAIR

    async def current(
        self, category: Category, today: date, *, exclude: Collection[int] = frozenset()
    ) -> Member | None:
        entries, _, members = await self._load(category, today)
        stats = await self.fair_stats(category, today, members)
        member_id = pick_next(entries, exclude=exclude, stats=stats)
        return None if member_id is None else members.get(member_id)

    async def complete(self, category: Category, member_id: int, today: date) -> None:
        entries, rows, _ = await self._load(category, today)
        apply_completion(entries, member_id, fair=self._is_fair(category))
        self._store(entries, rows)

    async def out_of_turn(self, category: Category, member_id: int, today: date) -> None:
        entries, rows, _ = await self._load(category, today)
        apply_out_of_turn(entries, member_id, fair=self._is_fair(category))
        self._store(entries, rows)

    async def skip(self, category: Category, member_id: int, today: date) -> None:
        entries, rows, _ = await self._load(category, today)
        apply_skip(entries, member_id, fair=self._is_fair(category))
        self._store(entries, rows)

    async def dispute(
        self, category: Category, member_id: int, today: date, *, in_turn: bool
    ) -> None:
        entries, rows, _ = await self._load(category, today)
        if member_id in rows:
            apply_dispute(entries, member_id, in_turn=in_turn, fair=self._is_fair(category))
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
        entries, _, members = await self._load(category, today)
        stats = await self.fair_stats(category, today, members)
        known = {e.member_id for e in entries}
        first = current_member_id if current_member_id in known else None
        first = first or pick_next(entries, exclude=exclude, stats=stats)
        available = sum(1 for e in entries if e.available)
        order = upcoming(entries, first, available, stats)
        ordered_members = [members[i] for i in order if i in members]
        return QueueSnapshot(
            current=ordered_members[0] if ordered_members else None,
            upcoming=ordered_members[1:],
            entries={e.member_id: e for e in entries},
            stats=stats,
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

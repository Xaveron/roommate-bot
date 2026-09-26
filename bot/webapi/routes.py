"""Read-only Mini App API: queues, history, balance and statistics of a room."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from bot.db.models import COMPLETED_DUTY_STATUSES, Category, ReviewStatus, Room
from bot.db.repositories import (
    AssignmentRepo,
    CategoryRepo,
    DutyRepo,
    ExpenseRepo,
    MemberRepo,
    UserRepo,
)
from bot.services.achievements import AchievementService
from bot.services.away import is_away
from bot.services.clock import local_date, local_now, utcnow, zone
from bot.services.finance import FinanceService
from bot.services.queue import QueueService
from bot.services.stats import StatsService, month_bounds
from bot.webapi.deps import InitDataDep, MembershipDep, SessionDep
from bot.webapi.schemas import (
    AwayOut,
    BalanceLineOut,
    BalanceOut,
    CategoryOut,
    DailyOut,
    DutyOut,
    ExpenseOut,
    HistoryOut,
    MarkOut,
    MemberStatsOut,
    MeOut,
    PersonOut,
    QueueCategoryOut,
    QueueOut,
    RoomOut,
    ShareOut,
    StatsOut,
    TransferOut,
)

router = APIRouter()

MAX_HISTORY = 200
RECENT_EXPENSES = 20


def room_out(room: Room) -> RoomOut:
    return RoomOut(
        id=room.id,
        name=room.name,
        language=room.language,
        timezone=room.timezone,
        currency=room.currency,
    )


def category_out(category: Category) -> CategoryOut:
    return CategoryOut(
        id=category.id,
        name=category.name,
        emoji=category.emoji,
        kind=category.kind,
        is_active=category.is_active,
    )


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/me", response_model=MeOut)
async def me(session: SessionDep, init: InitDataDep) -> MeOut:
    rooms = list(await MemberRepo(session).rooms_of_user(init.user.id))
    ids = {room.id for room in rooms}
    user = await UserRepo(session).get(init.user.id)
    initial = None
    start = init.start_param or ""
    if start.startswith("r") and start[1:].isdigit() and int(start[1:]) in ids:
        initial = int(start[1:])  # t.me/<bot>?startapp=r<room id>
    elif user is not None and user.active_room_id in ids:
        initial = user.active_room_id
    elif rooms:
        initial = rooms[0].id
    return MeOut(
        user_id=init.user.id,
        first_name=init.user.first_name,
        language_code=init.user.language_code,
        rooms=[room_out(room) for room in rooms],
        initial_room_id=initial,
    )


@router.get("/rooms/{room_id}/queue", response_model=QueueOut)
async def queue(session: SessionDep, membership: MembershipDep) -> QueueOut:
    room, me_member = membership
    today = local_date(room.timezone, utcnow())
    assignments = AssignmentRepo(session)
    service = QueueService(session)
    categories = []
    for category in await CategoryRepo(session).list(room.id, active_only=True):
        open_assignment = await assignments.get_open(category.id)
        snapshot = await service.snapshot(
            category,
            today,
            current_member_id=open_assignment.member_id if open_assignment else None,
            exclude=await assignments.declined_member_ids(category.id, today),
        )
        categories.append(
            QueueCategoryOut(
                id=category.id,
                name=category.name,
                emoji=category.emoji,
                kind=category.kind,
                mode=category.queue_mode,
                reminder_time=category.reminder_time.strftime("%H:%M"),
                current=PersonOut(member_id=snapshot.current.id, name=snapshot.current.display_name)
                if snapshot.current
                else None,
                status=open_assignment.status if open_assignment else "none",
                remind_on=open_assignment.remind_on if open_assignment else None,
                upcoming=[
                    PersonOut(member_id=m.id, name=m.display_name) for m in snapshot.upcoming
                ],
                marks=[
                    MarkOut(member_id=e.member_id, skip_debt=e.skip_debt, credit=e.credit)
                    for e in snapshot.entries.values()
                    if e.skip_debt or e.credit
                ],
                fair_counts=dict(snapshot.stats.counts) if snapshot.stats else None,
            )
        )
    roommates = await MemberRepo(session).list(room.id)
    away = [
        AwayOut(member_id=m.id, name=m.display_name, until=m.away_until)
        for m in roommates
        if m.away_until is not None and is_away(m, today)
    ]
    return QueueOut(
        room=room_out(room),
        me_member_id=me_member.id,
        members=[
            PersonOut(member_id=m.id, name=m.display_name)
            for m in roommates
            if m.is_available(today)
        ],
        categories=categories,
        away=away,
    )


@router.get("/rooms/{room_id}/history", response_model=HistoryOut)
async def history(
    session: SessionDep,
    membership: MembershipDep,
    category_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_HISTORY)] = 50,
) -> HistoryOut:
    room, _ = membership
    categories = list(await CategoryRepo(session).list(room.id))
    if category_id is not None and category_id not in {c.id for c in categories}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    duties = await DutyRepo(session).recent_for_room(room.id, limit=limit, category_id=category_id)
    return HistoryOut(
        room=room_out(room),
        categories=[category_out(c) for c in categories],
        items=[
            DutyOut(
                id=duty.id,
                category_id=duty.category_id,
                member_id=duty.member_id,
                member_name=duty.member.display_name,
                status=duty.status,
                review=duty.review,
                amount_cents=duty.amount_cents,
                created_at=duty.created_at,
            )
            for duty in duties
        ],
    )


@router.get("/rooms/{room_id}/balance", response_model=BalanceOut)
async def balance(session: SessionDep, membership: MembershipDep) -> BalanceOut:
    room, me_member = membership
    finance = FinanceService(session)
    names = {
        m.id: m.display_name for m in await MemberRepo(session).list(room.id, active_only=False)
    }
    balances = await finance.balances(room)
    expenses = list(await ExpenseRepo(session).list_for_room(room.id))[-RECENT_EXPENSES:]
    return BalanceOut(
        room=room_out(room),
        me_member_id=me_member.id,
        balances=[
            BalanceLineOut(member_id=m, name=names.get(m, "?"), cents=cents)
            for m, cents in sorted(balances.items(), key=lambda item: -item[1])
        ],
        transfers=[
            TransferOut(
                debtor_id=t.debtor_id,
                debtor_name=names.get(t.debtor_id, "?"),
                creditor_id=t.creditor_id,
                creditor_name=names.get(t.creditor_id, "?"),
                cents=t.amount_cents,
            )
            for t in await finance.transfers(room)
        ],
        expenses=[
            ExpenseOut(
                id=e.id,
                payer_name=names.get(e.payer_id, "?"),
                amount_cents=e.amount_cents,
                description=e.description,
                is_settlement=e.is_settlement,
                created_at=e.created_at,
                shares=[
                    ShareOut(name=names.get(s.member_id, "?"), cents=s.amount_cents)
                    for s in e.shares
                ],
            )
            for e in reversed(expenses)
        ],
    )


@router.get("/rooms/{room_id}/stats", response_model=StatsOut)
async def stats(
    session: SessionDep,
    membership: MembershipDep,
    year: Annotated[int | None, Query(ge=2020, le=2100)] = None,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
) -> StatsOut:
    room, _ = membership
    today = local_now(room.timezone, utcnow()).date()
    year, month = year or today.year, month or today.month
    period = await StatsService(session).month(room, year, month)
    badges = await AchievementService(session).for_members([m.member for m in period.members])

    # Chores per day of the month (up to today for the current month).
    start, end = month_bounds(year, month)
    tz = zone(room.timezone)
    per_day: Counter = Counter()
    for duty in await DutyRepo(session).list_for_room(
        room.id,
        datetime.combine(start, time(0), tzinfo=tz),
        datetime.combine(end, time(0), tzinfo=tz),
    ):
        if duty.status in COMPLETED_DUTY_STATUSES and duty.review != ReviewStatus.DISPUTED:
            per_day[local_date(room.timezone, duty.created_at)] += 1
    last_day = min(end - timedelta(days=1), today) if start <= today else end - timedelta(days=1)
    days = [start + timedelta(days=i) for i in range((last_day - start).days + 1)]

    return StatsOut(
        room=room_out(room),
        year=year,
        month=month,
        has_next=(year, month) < (today.year, today.month),
        categories=[category_out(c) for c in period.categories],
        members=[
            MemberStatsOut(
                member_id=m.member.id,
                name=m.member.display_name,
                done=m.done,
                skipped=m.skipped,
                out_of_turn=m.out_of_turn,
                spent_cents=m.spent_cents,
                by_category=dict(m.by_category),
                badges=badges.get(m.member.id, []),
            )
            for m in period.members
        ],
        done=period.done,
        skipped=period.skipped,
        disputed=period.disputed,
        spent_cents=period.spent_cents,
        daily=[DailyOut(day=day, done=per_day[day]) for day in days],
    )

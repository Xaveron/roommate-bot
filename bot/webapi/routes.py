"""Mini App API, reading side: rooms, queues, history, money, shopping list, statistics,
settings and roommates.

The actions live in ``bot.webapi.actions`` and ``bot.webapi.manage``.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from bot.config import SUPPORTED_LANGUAGES
from bot.db.models import COMPLETED_DUTY_STATUSES, Category, ReviewStatus, Room
from bot.db.repositories import (
    AssignmentRepo,
    CategoryRepo,
    DutyRepo,
    ExpenseRepo,
    MemberRepo,
    RoomRepo,
    UserRepo,
    VoteRepo,
)
from bot.keyboards import settings as kb
from bot.notifications import Notifier
from bot.permissions import is_in_chat
from bot.services.achievements import AchievementService
from bot.services.away import MAX_AWAY_DAYS, is_away
from bot.services.categories import MAX_NAME_LENGTH
from bot.services.clock import local_date, local_now, utcnow, zone
from bot.services.finance import FinanceService
from bot.services.queue import QueueService
from bot.services.reviews import ReviewService
from bot.services.rooms import MAX_REPEAT_HOURS
from bot.services.shopping import ShoppingService
from bot.services.stats import StatsService, month_bounds
from bot.utils.parsing import format_time
from bot.webapi.deps import InitDataDep, MembershipDep, RightsCache, SessionDep
from bot.webapi.schemas import (
    AwayOut,
    BalanceLineOut,
    BalanceOut,
    CategoryOut,
    CategorySettingsOut,
    DailyOut,
    DutyOut,
    ExpenseOut,
    HistoryOut,
    MarkOut,
    MemberOut,
    MemberStatsOut,
    MeOut,
    PersonOut,
    QueueCategoryOut,
    QueueOut,
    QuietHoursOut,
    RoommateOut,
    RoomOut,
    SettingsOptionsOut,
    SettingsOut,
    ShareOut,
    ShoppingItemOut,
    ShoppingOut,
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
async def me(
    request: Request,
    session: SessionDep,
    init: InitDataDep,
    room: Annotated[int | None, Query(ge=1)] = None,
) -> MeOut:
    """The caller's rooms. ``room``: the room the app was opened for (its button)."""
    rooms = list(await MemberRepo(session).rooms_of_user(init.user.id))
    ids = {r.id for r in rooms}
    user = await UserRepo(session).get(init.user.id)
    start = init.start_param or ""
    wanted = room
    if wanted is None and start.startswith("r") and start[1:].isdigit():
        wanted = int(start[1:])  # t.me/<bot>?startapp=r<room id>
    initial = None
    if wanted in ids:
        initial = wanted
    elif user is not None and user.active_room_id in ids:
        initial = user.active_room_id
    elif rooms:
        initial = rooms[0].id

    invite = None
    if wanted is not None and wanted not in ids:
        other = await RoomRepo(session).get(wanted)
        notifier: Notifier = request.app.state.notifier
        if (
            other is not None
            and other.is_active
            and await is_in_chat(notifier.bot, other, init.user.id)
        ):
            invite = room_out(other)
    return MeOut(
        user_id=init.user.id,
        first_name=init.user.first_name,
        language_code=init.user.language_code,
        rooms=[room_out(r) for r in rooms],
        initial_room_id=initial,
        invite=invite,
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
                assignment_id=open_assignment.id if open_assignment else None,
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
        today=today,
        away_max_days=MAX_AWAY_DAYS,
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
    room, me_member = membership
    categories = list(await CategoryRepo(session).list(room.id))
    if category_id is not None and category_id not in {c.id for c in categories}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    duties = await DutyRepo(session).recent_for_room(room.id, limit=limit, category_id=category_id)
    votes = VoteRepo(session)
    ids = [duty.id for duty in duties]
    tallies = await votes.tallies(ids)
    mine = await votes.of_member(me_member.id, ids)
    now = utcnow()
    return HistoryOut(
        room=room_out(room),
        me_member_id=me_member.id,
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
                votes_up=tallies.get(duty.id, (0, 0))[0],
                votes_down=tallies.get(duty.id, (0, 0))[1],
                my_vote=mine.get(duty.id),
                can_vote=duty.member_id != me_member.id and ReviewService.is_open(duty, now),
            )
            for duty in duties
        ],
    )


@router.get("/rooms/{room_id}/balance", response_model=BalanceOut)
async def balance(session: SessionDep, membership: MembershipDep) -> BalanceOut:
    room, me_member = membership
    finance = FinanceService(session)
    everybody = await MemberRepo(session).list(room.id, active_only=False)
    names = {m.id: m.display_name for m in everybody}
    today = local_date(room.timezone, utcnow())
    balances = await finance.balances(room)
    expenses = list(await ExpenseRepo(session).list_for_room(room.id))[-RECENT_EXPENSES:]
    return BalanceOut(
        room=room_out(room),
        me_member_id=me_member.id,
        members=[
            RoommateOut(member_id=m.id, name=m.display_name, at_home=m.is_available(today))
            for m in everybody
            if m.is_active
        ],
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


@router.get("/rooms/{room_id}/shopping", response_model=ShoppingOut)
async def shopping(session: SessionDep, membership: MembershipDep) -> ShoppingOut:
    room, _ = membership
    names = {
        m.id: m.display_name for m in await MemberRepo(session).list(room.id, active_only=False)
    }
    return ShoppingOut(
        room=room_out(room),
        items=[
            ShoppingItemOut(
                id=item.id,
                text=item.text,
                added_by=names.get(item.added_by) if item.added_by else None,
                created_at=item.created_at,
            )
            for item in await ShoppingService(session).open_items(room)
        ],
    )


@router.get("/rooms/{room_id}/settings", response_model=SettingsOut)
async def settings(request: Request, session: SessionDep, membership: MembershipDep) -> SettingsOut:
    """The room screen: settings, categories and roommates (as /settings and /members)."""
    room, me_member = membership
    now = utcnow()
    notifier: Notifier = request.app.state.notifier
    rights: RightsCache = request.app.state.rights
    today = local_date(room.timezone, now)
    return SettingsOut(
        room=room_out(room),
        me_member_id=me_member.id,
        can_manage=await rights.can_manage(notifier.bot, room, me_member.telegram_user_id, now),
        quiet_hours=QuietHoursOut(
            start=format_time(room.quiet_hours_start), end=format_time(room.quiet_hours_end)
        )
        if room.quiet_hours_start is not None and room.quiet_hours_end is not None
        else None,
        repeat_after_hours=room.repeat_after_hours,
        weekly_summary=room.weekly_summary,
        categories=[
            CategorySettingsOut(
                id=c.id,
                name=c.name,
                emoji=c.emoji,
                kind=c.kind,
                is_active=c.is_active,
                reminder_time=format_time(c.reminder_time),
                reminder_days=[int(day) for day in c.reminder_days],
                mode=c.queue_mode,
            )
            for c in await CategoryRepo(session).list(room.id)
        ],
        members=[
            MemberOut(
                member_id=m.id,
                name=m.display_name,
                username=m.user.username,
                is_creator=m.telegram_user_id == room.created_by,
                away_until=m.away_until if is_away(m, today) else None,
                dm_available=m.user.dm_available,
            )
            for m in await MemberRepo(session).list(room.id)
        ],
        options=SettingsOptionsOut(
            languages=list(SUPPORTED_LANGUAGES),
            timezones=list(kb.TIMEZONE_PRESETS),
            currencies=list(kb.CURRENCY_PRESETS),
            repeat_hours=list(kb.REPEAT_PRESETS),
            max_repeat_hours=MAX_REPEAT_HOURS,
            quiet_hours=[
                QuietHoursOut(start=format_time(start), end=format_time(end))
                for start, end in kb.QUIET_PRESETS
            ],
            reminder_times=[format_time(value) for value in kb.TIME_PRESETS],
            max_category_name=MAX_NAME_LENGTH,
        ),
    )

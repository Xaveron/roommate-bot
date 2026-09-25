"""Business logic on top of a real (in-memory SQLite) database."""

from __future__ import annotations

from datetime import time, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import AssignmentStatus, Category, CategoryKind, DutyStatus
from bot.db.repositories import QueueRepo, UserRepo
from bot.services.categories import CategoryService
from bot.services.errors import ServiceError
from bot.services.history import HistoryService
from bot.services.reminders import ReminderService
from bot.services.rooms import RoomService
from bot.services.tasks import TaskService
from tests.conftest import NAMES, at, make_room

S = AssignmentStatus


async def bread(session: AsyncSession, room) -> Category:
    return next(c for c in await CategoryService(session).list(room) if c.kind == "bread")


async def plan(session: AsyncSession, room, local: str):
    """Run the planner and pretend every reminder was delivered."""
    now = at(local)
    due = await ReminderService(session).plan_room(room, now)
    for assignment in due:
        ReminderService.mark_delivered(assignment, now, chat_id=None, message_id=None)
    await session.flush()
    return due


def by_category(due, category: Category):
    return [a for a in due if a.category_id == category.id]


async def test_room_is_created_with_default_categories_and_queues(session):
    room, members = await make_room(session)
    categories = await CategoryService(session).list(room)
    assert [(c.kind, c.name, c.emoji, c.reminder_time) for c in categories] == [
        ("bread", "Хлеб", "🍞", time(18)),
        ("water", "Вода", "💧", time(18)),
        ("trash", "Мусор", "🗑", time(20)),
    ]
    states = await QueueRepo(session).list_for_category(categories[0].id)
    assert [s.member_id for s in states] == [m.id for m in members]


async def test_get_or_create_is_idempotent(session):
    room, _ = await make_room(session)
    again, created = await RoomService(session).get_or_create(
        chat_id=room.chat_id,
        title="906B new",
        created_by=5,
        language="ro",
        timezone="UTC",
        default_names=NAMES,
        now=at("2026-09-25 11:00"),
    )
    assert again.id == room.id and not created
    assert again.name == "906B new" and again.created_by == 1


async def test_reminders_are_sent_at_configured_time_once_a_day(session):
    room, (anya, _, _) = await make_room(session)
    category = await bread(session, room)

    assert await plan(session, room, "2026-09-25 17:59") == []
    due = await plan(session, room, "2026-09-25 18:00")
    assert {a.category.kind for a in due} == {"bread", "water"}
    assert all(a.member_id == anya.id and a.status == S.PENDING for a in due)
    assert await plan(session, room, "2026-09-25 18:30") == []

    due = await plan(session, room, "2026-09-25 20:00")
    assert [a.category.kind for a in due] == ["trash"]
    assert category.last_reminded_on.isoformat() == "2026-09-25"


async def test_room_created_after_reminder_time_starts_tomorrow(session):
    room, _ = await make_room(session, now=at("2026-09-25 19:00"))
    due = await plan(session, room, "2026-09-25 19:01")
    # Bread and water (18:00) start tomorrow, trash (20:00) still today.
    assert await plan(session, room, "2026-09-25 19:30") == []
    assert due == []
    assert [a.category.kind for a in await plan(session, room, "2026-09-25 20:00")] == ["trash"]


async def test_reminder_time_moved_later_on_a_late_room_fires_today(session):
    room, (anya, _, _) = await make_room(session, now=at("2026-09-25 23:00"))
    category = await bread(session, room)
    await CategoryService(session).set_reminder_time(category, time(23, 5))
    assert by_category(await plan(session, room, "2026-09-25 23:04"), category) == []
    (assignment,) = by_category(await plan(session, room, "2026-09-25 23:05"), category)
    assert assignment.member_id == anya.id


async def test_accept_then_done_moves_queue_and_suppresses_duplicates(session):
    room, (anya, borya, _) = await make_room(session)
    category = await bread(session, room)
    (assignment,) = by_category(await plan(session, room, "2026-09-25 18:00"), category)

    tasks = TaskService(session)
    await tasks.accept(assignment.id, anya.telegram_user_id)
    assert assignment.status == S.ACCEPTED
    completion = await tasks.complete(assignment.id, anya.telegram_user_id, at("2026-09-25 18:40"))
    assert completion.in_turn and completion.duty.status == DutyStatus.DONE
    assert completion.next_member.id == borya.id

    with pytest.raises(ServiceError) as error:
        await tasks.complete(assignment.id, anya.telegram_user_id, at("2026-09-25 18:41"))
    assert error.value.key == "err-assignment-closed"

    (tomorrow,) = by_category(await plan(session, room, "2026-09-26 18:00"), category)
    assert tomorrow.member_id == borya.id


async def test_only_the_assignee_can_press_the_buttons(session):
    room, (_, borya, _) = await make_room(session)
    (assignment, *_) = await plan(session, room, "2026-09-25 18:00")
    with pytest.raises(ServiceError) as error:
        await TaskService(session).accept(assignment.id, borya.telegram_user_id)
    assert error.value.key == "err-not-your-turn"


async def test_still_have_keeps_queue_and_reminds_same_member_tomorrow(session):
    room, (anya, _, _) = await make_room(session)
    category = await bread(session, room)
    (assignment,) = by_category(await plan(session, room, "2026-09-25 18:00"), category)

    await TaskService(session).still_have(
        assignment.id, anya.telegram_user_id, at("2026-09-25 18:05")
    )
    assert assignment.status == S.SNOOZED
    assert assignment.remind_on.isoformat() == "2026-09-26"

    assert by_category(await plan(session, room, "2026-09-25 23:00"), category) == []
    assert by_category(await plan(session, room, "2026-09-26 17:00"), category) == []
    (again,) = by_category(await plan(session, room, "2026-09-26 18:00"), category)
    assert again.id == assignment.id and again.member_id == anya.id
    assert again.status == S.PENDING and again.reminders_sent == 1

    history = await HistoryService(session).for_category(category)
    assert [d.status for d in history.duties] == [DutyStatus.STILL_HAVE]


async def test_still_have_reminds_tomorrow_even_if_it_is_not_a_reminder_day(session):
    room, (anya, _, _) = await make_room(session)
    category = await bread(session, room)
    category.reminder_days = "4"  # Fridays only; 2026-09-25 is a Friday
    (assignment,) = by_category(await plan(session, room, "2026-09-25 18:00"), category)
    await TaskService(session).still_have(
        assignment.id, anya.telegram_user_id, at("2026-09-25 18:05")
    )
    (again,) = by_category(await plan(session, room, "2026-09-26 18:00"), category)
    assert again.member_id == anya.id


async def test_decline_hands_over_and_debtor_goes_first_next_time(session):
    room, (anya, borya, vika) = await make_room(session)
    category = await bread(session, room)
    (assignment,) = by_category(await plan(session, room, "2026-09-25 18:00"), category)
    tasks = TaskService(session)

    handover = await tasks.decline(assignment.id, anya.telegram_user_id, at("2026-09-25 18:10"))
    assert assignment.status == S.DECLINED
    new = handover.next_assignment
    assert new.member_id == borya.id and new.last_reminded_at is None
    state = await QueueRepo(session).get(category.id, anya.id)
    assert state.skip_debt == 1

    # The new assignment hasn't been delivered yet, so the next tick delivers it.
    assert by_category(await plan(session, room, "2026-09-25 18:11"), category) == [new]

    completion = await tasks.complete(new.id, borya.telegram_user_id, at("2026-09-25 19:00"))
    assert completion.next_member.id == anya.id

    (tomorrow,) = by_category(await plan(session, room, "2026-09-26 18:00"), category)
    assert tomorrow.member_id == anya.id
    completion = await tasks.complete(tomorrow.id, anya.telegram_user_id, at("2026-09-26 19:00"))
    assert completion.next_member.id == vika.id
    assert state.skip_debt == 0


async def test_everybody_declines(session):
    room, (anya, borya) = await make_room(session, members=2)
    category = await bread(session, room)
    (assignment,) = by_category(await plan(session, room, "2026-09-25 18:00"), category)
    tasks = TaskService(session)
    handover = await tasks.decline(assignment.id, anya.telegram_user_id, at("2026-09-25 18:10"))
    handover = await tasks.decline(
        handover.next_assignment.id, borya.telegram_user_id, at("2026-09-25 18:20")
    )
    assert handover.next_assignment is None
    assert by_category(await plan(session, room, "2026-09-25 21:00"), category) == []
    # Tomorrow the first debtor in queue order gets the turn.
    (tomorrow,) = by_category(await plan(session, room, "2026-09-26 18:00"), category)
    assert tomorrow.member_id == anya.id


async def test_out_of_turn_covers_open_assignment_and_earns_credit(session):
    room, (anya, borya, vika) = await make_room(session)
    category = await bread(session, room)
    (assignment,) = by_category(await plan(session, room, "2026-09-25 18:00"), category)
    tasks = TaskService(session)

    completion = await tasks.mark_done(category, vika, at("2026-09-25 18:30"))
    assert not completion.in_turn
    assert completion.duty.status == DutyStatus.OUT_OF_TURN
    assert completion.covered is assignment and assignment.status == S.COVERED
    assert completion.next_member.id == anya.id  # Аня keeps her turn
    assert by_category(await plan(session, room, "2026-09-25 22:00"), category) == []

    for member in (anya, borya):
        (turn,) = by_category(await plan(session, room, _next_day(category)), category)
        assert turn.member_id == member.id
        await tasks.complete(turn.id, member.telegram_user_id, at(_next_day(category, "19:00")))
    # Вика's turn is skipped thanks to the credit.
    (turn,) = by_category(await plan(session, room, _next_day(category)), category)
    assert turn.member_id == anya.id


def _next_day(category: Category, clock: str = "18:00") -> str:
    day = category.last_reminded_on + timedelta(days=1)
    return f"{day.isoformat()} {clock}"


async def test_done_in_turn_before_reminder_suppresses_todays_reminder(session):
    room, (anya, borya, _) = await make_room(session)
    category = await bread(session, room)
    completion = await TaskService(session).mark_done(category, anya, at("2026-09-25 12:00"))
    assert completion.in_turn and completion.next_member.id == borya.id
    assert by_category(await plan(session, room, "2026-09-25 18:00"), category) == []
    (tomorrow,) = by_category(await plan(session, room, "2026-09-26 18:00"), category)
    assert tomorrow.member_id == borya.id


async def test_member_leaving_hands_over_todays_turn(session):
    room, (anya, borya, _) = await make_room(session)
    category = await bread(session, room)
    (assignment,) = by_category(await plan(session, room, "2026-09-25 18:00"), category)
    await RoomService(session).leave(anya)
    (handover,) = by_category(await plan(session, room, "2026-09-25 18:01"), category)
    assert assignment.status == S.CANCELLED
    assert handover.member_id == borya.id


async def test_rejoining_member_goes_to_the_end_without_debts(session):
    room, (anya, borya, vika) = await make_room(session)
    category = await bread(session, room)
    state = await QueueRepo(session).get(category.id, anya.id)
    state.skip_debt = 2
    await RoomService(session).leave(anya)
    user = await UserRepo(session).get(anya.telegram_user_id)
    member, joined = await RoomService(session).join(room, user, at("2026-09-25 12:00"))
    assert joined and member.id == anya.id
    states = await QueueRepo(session).list_for_category(category.id)
    assert [s.member_id for s in states] == [borya.id, vika.id, anya.id]
    assert state.skip_debt == 0


async def test_quiet_hours_postpone_reminders(session):
    room, _ = await make_room(session)
    await RoomService(session).set_quiet_hours(room, time(17), time(19))
    assert await plan(session, room, "2026-09-25 18:00") == []
    assert len(await plan(session, room, "2026-09-25 19:00")) == 2


async def test_reminder_days(session):
    room, _ = await make_room(session)
    category = await bread(session, room)
    categories = CategoryService(session)
    await categories.toggle_day(category, 4)  # 2026-09-25 is a Friday: switch it off
    assert "4" not in category.reminder_days
    assert by_category(await plan(session, room, "2026-09-25 18:00"), category) == []
    assert len(by_category(await plan(session, room, "2026-09-26 18:00"), category)) == 1

    for day in "01235":
        await categories.toggle_day(category, int(day))
    assert category.reminder_days == "6"
    with pytest.raises(ServiceError) as error:
        await categories.toggle_day(category, 6)
    assert error.value.key == "err-no-days"


async def test_unanswered_reminder_is_repeated_next_day(session):
    room, (anya, _, _) = await make_room(session)
    category = await bread(session, room)
    (first,) = by_category(await plan(session, room, "2026-09-25 18:00"), category)
    (second,) = by_category(await plan(session, room, "2026-09-26 18:00"), category)
    assert second.id == first.id and second.member_id == anya.id
    assert second.for_date.isoformat() == "2026-09-26"


async def test_category_management(session):
    room, members = await make_room(session)
    categories = CategoryService(session)
    now = at("2026-09-25 10:00")

    soap = await categories.create(room, name="  Мыло  ", emoji="🧼", now=now)
    assert soap.name == "Мыло" and soap.kind == CategoryKind.CUSTOM
    states = await QueueRepo(session).list_for_category(soap.id)
    assert [s.member_id for s in states] == [m.id for m in members]

    for name, emoji, key in [
        ("мыло", None, "err-category-exists"),
        ("", None, "err-category-name"),
        ("x" * 40, None, "err-category-name"),
        ("Соль", "abc", "err-category-emoji"),
    ]:
        with pytest.raises(ServiceError) as error:
            await categories.create(room, name=name, emoji=emoji, now=now)
        assert error.value.key == key

    assert (await categories.find(room, "мы")).id == soap.id
    assert (await categories.find(room, "🧼")).id == soap.id
    assert await categories.find(room, "нет такой") is None

    (assignment,) = [
        a for a in await plan(session, room, "2026-09-25 18:00") if a.category_id == soap.id
    ]
    await categories.set_active(soap, False, at("2026-09-25 18:05"))
    assert assignment.status == S.CANCELLED
    assert await categories.find(room, "Мыло") is None

    await categories.delete(soap)
    assert [c.name for c in await categories.list(room)] == ["Хлеб", "Вода", "Мусор"]


async def test_language_switch_renames_untouched_default_categories(session):
    room, _ = await make_room(session)
    categories = await CategoryService(session).list(room)
    categories[1].name = "Вода 5л"  # renamed by the users: keep it
    await RoomService(session).set_language(
        room, "ro", NAMES, {"bread": "Pâine", "water": "Apă", "trash": "Gunoi"}
    )
    assert room.language == "ro"
    assert [c.name for c in categories] == ["Pâine", "Вода 5л", "Gunoi"]


async def test_timezone_validation_and_local_time(session):
    room, _ = await make_room(session)
    with pytest.raises(ServiceError):
        await RoomService(session).set_timezone(room, "Mars/Olympus")
    await RoomService(session).set_timezone(room, "UTC")
    # 18:00 in Chisinau (UTC+3 in September) is 15:00 UTC: too early for a UTC room.
    assert await plan(session, room, "2026-09-25 18:00") == []
    assert len(await plan(session, room, "2026-09-25 21:00")) == 2


async def test_history_is_newest_first(session):
    room, (anya, borya, _) = await make_room(session)
    category = await bread(session, room)
    tasks = TaskService(session)
    await tasks.mark_done(category, anya, at("2026-09-25 09:00"))
    await tasks.mark_done(category, anya, at("2026-09-25 10:00"))
    await tasks.mark_done(category, borya, at("2026-09-25 11:00"))
    history = await HistoryService(session).for_category(category)
    assert [(d.member.display_name, d.status) for d in history.duties] == [
        ("Боря", DutyStatus.DONE),
        ("Аня", DutyStatus.OUT_OF_TURN),
        ("Аня", DutyStatus.DONE),
    ]


async def test_group_migration(session):
    room, _ = await make_room(session)
    service = RoomService(session)
    moved = await service.migrate_chat(room.chat_id, -100555)
    assert moved is room and room.chat_id == -100555
    assert await service.migrate_chat(-1, -2) is None

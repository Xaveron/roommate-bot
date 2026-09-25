"""Stage 2: fair queue, repeated reminders, away mode, confirmations."""

from __future__ import annotations

from datetime import date, time, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import AssignmentStatus, QueueMode, ReviewStatus, Vote
from bot.db.repositories import AbsenceRepo, QueueRepo
from bot.services.away import AwayService, is_away
from bot.services.categories import CategoryService
from bot.services.errors import ServiceError
from bot.services.queue import QueueService
from bot.services.reminders import DeliveryKind
from bot.services.reviews import ReviewService, decide
from bot.services.rooms import RoomService
from bot.services.tasks import TaskService
from tests.conftest import at, make_room
from tests.test_services import bread, by_category, deliveries, plan

S = AssignmentStatus


async def queue_member(session: AsyncSession, category, local: str):
    return await QueueService(session).current(category, date.fromisoformat(local[:10]))


# --- fair mode ------------------------------------------------------------------------


async def test_switching_to_fair_resets_debts_and_uses_counts(session):
    room, (anya, borya, vika) = await make_room(session)
    category = await bread(session, room)
    tasks = TaskService(session)
    await QueueService(session).skip(category, anya.id, date(2026, 9, 25))

    await CategoryService(session).toggle_queue_mode(category)
    assert category.queue_mode == QueueMode.FAIR
    assert (await QueueRepo(session).get(category.id, anya.id)).skip_debt == 0

    # Borya did it twice and Anya once: Vika (0) is next, then Anya.
    await tasks.mark_done(category, borya, at("2026-09-25 09:00"))
    await tasks.mark_done(category, borya, at("2026-09-25 10:00"))
    await tasks.mark_done(category, anya, at("2026-09-25 11:00"))
    assert (await queue_member(session, category, "2026-09-25")).id == vika.id
    completion = await tasks.mark_done(category, vika, at("2026-09-25 12:00"))
    assert completion.in_turn
    assert completion.next_member.id == anya.id

    await CategoryService(session).toggle_queue_mode(category)
    assert category.queue_mode == QueueMode.ROUND_ROBIN


async def test_fair_counts_only_last_30_days(session):
    room, (anya, borya) = await make_room(session, members=2, now=at("2026-08-01 10:00"))
    category = await bread(session, room)
    await CategoryService(session).toggle_queue_mode(category)
    tasks = TaskService(session)
    for day in range(1, 6):  # Anya did a lot in August...
        await tasks.mark_done(category, anya, at(f"2026-08-0{day} 12:00"))
    await tasks.mark_done(category, borya, at("2026-09-20 12:00"))
    # ...but in the last 30 days only Borya did it once.
    assert (await queue_member(session, category, "2026-09-25")).id == anya.id


async def test_fair_mode_does_not_punish_returning_from_away(session):
    room, (anya, borya, vika) = await make_room(session, now=at("2026-09-01 10:00"))
    category = await bread(session, room)
    await CategoryService(session).toggle_queue_mode(category)
    await AwayService(session).go_away(room, vika, date(2026, 9, 20), at("2026-09-01 11:00"))
    tasks = TaskService(session)
    for day in range(2, 21):  # Anya and Borya take turns while Vika is away
        member = anya if day % 2 else borya
        await tasks.mark_done(category, member, at(f"2026-09-{day:02d} 12:00"))

    # Vika returns on the 21st and does it once; after that she isn't picked again and
    # again to "catch up" on the weeks she was away.
    today = "2026-09-21"
    assert (await queue_member(session, category, today)).id == vika.id
    await tasks.mark_done(category, vika, at(f"{today} 12:00"))
    assert (await queue_member(session, category, today)).id != vika.id


async def test_disputed_records_do_not_count_in_fair_mode(session):
    room, (anya, borya) = await make_room(session, members=2)
    category = await bread(session, room)
    await CategoryService(session).toggle_queue_mode(category)
    completion = await TaskService(session).mark_done(category, anya, at("2026-09-25 12:00"))
    assert (await queue_member(session, category, "2026-09-25")).id == borya.id
    outcome = await ReviewService(session).vote(
        completion.duty.id, borya, Vote.DOWN, at("2026-09-25 12:10")
    )
    assert outcome.decided == ReviewStatus.DISPUTED
    assert (await queue_member(session, category, "2026-09-25")).id == anya.id


# --- repeated reminders ---------------------------------------------------------------


async def test_unanswered_reminder_is_repeated_then_group_is_nudged(session):
    room, (anya, _, _) = await make_room(session)
    await RoomService(session).set_repeat_hours(room, 2)
    category = await bread(session, room)

    (first,) = by_category(await plan(session, room, "2026-09-25 18:00"), category)
    assert first.reminders_sent == 1
    assert by_category(await plan(session, room, "2026-09-25 19:59"), category) == []

    due = [d for d in await deliveries(session, room, "2026-09-25 20:00") if d.assignment is first]
    assert [d.kind for d in due] == [DeliveryKind.REMINDER]
    assert first.reminders_sent == 2

    due = [d for d in await deliveries(session, room, "2026-09-25 22:00") if d.assignment is first]
    assert [d.kind for d in due] == [DeliveryKind.NUDGE]
    assert first.reminders_sent == 3

    # After the nudge: silence until tomorrow's regular reminder.
    assert [d for d in await deliveries(session, room, "2026-09-25 23:59")] == []
    (tomorrow,) = by_category(await plan(session, room, "2026-09-26 18:00"), category)
    assert tomorrow is first and first.reminders_sent == 1 and first.member_id == anya.id


async def test_answered_reminders_are_not_repeated(session):
    room, (anya, _, _) = await make_room(session)
    await RoomService(session).set_repeat_hours(room, 1)
    category = await bread(session, room)
    (assignment,) = by_category(await plan(session, room, "2026-09-25 18:00"), category)
    await TaskService(session).accept(assignment.id, anya.telegram_user_id)
    due = await deliveries(session, room, "2026-09-25 23:00")
    assert [d for d in due if d.assignment is assignment] == []


async def test_repeat_can_be_turned_off_and_respects_quiet_hours(session):
    room, _ = await make_room(session)
    rooms = RoomService(session)
    await rooms.set_repeat_hours(room, 0)
    await plan(session, room, "2026-09-25 18:00")  # bread and water
    await plan(session, room, "2026-09-25 20:00")  # trash
    assert await deliveries(session, room, "2026-09-25 23:59") == []

    await rooms.set_repeat_hours(room, 3)
    await rooms.set_quiet_hours(room, time(21), time(8))
    assert await deliveries(session, room, "2026-09-25 21:30") == []
    due = await deliveries(session, room, "2026-09-26 08:00")
    assert {d.kind for d in due} == {DeliveryKind.REMINDER}

    with pytest.raises(ServiceError):
        await rooms.set_repeat_hours(room, 99)


# --- away mode ------------------------------------------------------------------------


async def test_away_member_is_skipped_and_returns_without_debts(session):
    room, (anya, borya, _) = await make_room(session)
    category = await bread(session, room)
    (assignment,) = by_category(await plan(session, room, "2026-09-25 18:00"), category)
    state = await QueueRepo(session).get(category.id, anya.id)
    state.skip_debt = 2

    away = AwayService(session)
    await away.go_away(room, anya, date(2026, 9, 28), at("2026-09-25 18:05"))
    assert is_away(anya, date(2026, 9, 28)) and not is_away(anya, date(2026, 9, 29))
    assert state.skip_debt == 0

    # Her open turn goes to the next roommate right away.
    (handover,) = by_category(await plan(session, room, "2026-09-25 18:06"), category)
    assert assignment.status == S.CANCELLED and handover.member_id == borya.id
    assert (await queue_member(session, category, "2026-09-27")).id != anya.id
    assert (await queue_member(session, category, "2026-09-29")).id == anya.id


async def test_back_early_and_absence_history(session):
    room, (anya, _, _) = await make_room(session)
    away = AwayService(session)
    absences = AbsenceRepo(session)

    await away.go_away(room, anya, date(2026, 10, 10), at("2026-09-25 12:00"))
    await away.go_away(room, anya, date(2026, 10, 15), at("2026-09-26 12:00"))  # extended
    absence = await absences.current(anya.id, date(2026, 9, 26))
    assert (absence.start_date, absence.end_date) == (date(2026, 9, 25), date(2026, 10, 15))

    assert await away.come_back(room, anya, at("2026-09-30 09:00"))
    assert anya.away_until is None and absence.end_date == date(2026, 9, 29)
    assert not await away.come_back(room, anya, at("2026-09-30 10:00"))

    # Left and came back the same day: no absence is kept.
    await away.go_away(room, anya, date(2026, 10, 5), at("2026-10-01 09:00"))
    await away.come_back(room, anya, at("2026-10-01 20:00"))
    assert await absences.current(anya.id, date(2026, 10, 1)) is None


async def test_away_date_validation(session):
    room, (anya, _, _) = await make_room(session)
    away = AwayService(session)
    for until, key in [
        (date(2026, 9, 24), "err-date-past"),
        (date(2028, 1, 1), "err-date-too-far"),
    ]:
        with pytest.raises(ServiceError) as error:
            await away.go_away(room, anya, until, at("2026-09-25 12:00"))
        assert error.value.key == key
    await away.go_away(room, anya, date(2026, 9, 25), at("2026-09-25 12:00"))  # today only


# --- confirmations --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("up", "down", "voters", "expected"),
    [
        (0, 1, 1, ReviewStatus.DISPUTED),
        (1, 0, 1, ReviewStatus.CONFIRMED),
        (0, 1, 2, None),
        (1, 1, 2, None),
        (0, 2, 2, ReviewStatus.DISPUTED),
        (1, 1, 3, None),
        (2, 1, 3, ReviewStatus.CONFIRMED),
        (0, 0, 0, None),
    ],
)
def test_majority_rule(up, down, voters, expected):
    assert decide(up, down, voters) == expected


async def test_majority_against_disputes_record_and_restores_turn(session):
    room, (anya, borya, vika) = await make_room(session)
    category = await bread(session, room)
    completion = await TaskService(session).mark_done(category, anya, at("2026-09-25 12:00"))
    assert completion.voters == 2
    assert completion.next_member.id == borya.id

    reviews = ReviewService(session)
    first = await reviews.vote(completion.duty.id, borya, Vote.DOWN, at("2026-09-25 12:05"))
    assert (first.up, first.down, first.decided) == (0, 1, None)
    second = await reviews.vote(completion.duty.id, vika, Vote.DOWN, at("2026-09-25 12:06"))
    assert second.decided == ReviewStatus.DISPUTED
    assert completion.duty.review == ReviewStatus.DISPUTED
    # Anya owes the turn again and goes first.
    assert (await queue_member(session, category, "2026-09-25")).id == anya.id

    with pytest.raises(ServiceError) as error:
        await reviews.vote(completion.duty.id, borya, Vote.UP, at("2026-09-25 12:07"))
    assert error.value.key == "err-vote-closed"


async def test_confirmation_and_vote_rules(session):
    room, (anya, borya, vika) = await make_room(session)
    category = await bread(session, room)
    completion = await TaskService(session).mark_done(category, anya, at("2026-09-25 12:00"))
    duty_id = completion.duty.id
    reviews = ReviewService(session)

    for voter, key in [(anya, "err-vote-self")]:
        with pytest.raises(ServiceError) as error:
            await reviews.vote(duty_id, voter, Vote.UP, at("2026-09-25 12:01"))
        assert error.value.key == key

    await reviews.vote(duty_id, borya, Vote.DOWN, at("2026-09-25 12:02"))
    with pytest.raises(ServiceError) as error:
        await reviews.vote(duty_id, borya, Vote.DOWN, at("2026-09-25 12:03"))
    assert error.value.key == "err-vote-already"
    changed = await reviews.vote(duty_id, borya, Vote.UP, at("2026-09-25 12:04"))
    assert (changed.up, changed.down) == (1, 0)
    outcome = await reviews.vote(duty_id, vika, Vote.UP, at("2026-09-25 12:05"))
    assert outcome.decided == ReviewStatus.CONFIRMED
    assert (await queue_member(session, category, "2026-09-25")).id == borya.id


async def test_voting_window_and_other_rooms(session):
    room, (anya, borya, _) = await make_room(session)
    category = await bread(session, room)
    completion = await TaskService(session).mark_done(category, anya, at("2026-09-25 12:00"))
    reviews = ReviewService(session)
    late = at("2026-09-25 12:00") + timedelta(hours=49)
    with pytest.raises(ServiceError) as error:
        await reviews.vote(completion.duty.id, borya, Vote.DOWN, late)
    assert error.value.key == "err-vote-closed"

    other_room, (stranger, *_) = await make_room(session, members=1, chat_id=-2002)
    assert other_room.id != room.id
    with pytest.raises(ServiceError):
        await reviews.vote(completion.duty.id, stranger, Vote.DOWN, at("2026-09-25 12:01"))


async def test_out_of_turn_dispute_withdraws_credit(session):
    room, (anya, borya, vika) = await make_room(session, members=3)
    category = await bread(session, room)
    completion = await TaskService(session).mark_done(category, vika, at("2026-09-25 12:00"))
    assert not completion.in_turn
    state = await QueueRepo(session).get(category.id, vika.id)
    assert state.credit == 1
    reviews = ReviewService(session)
    await reviews.vote(completion.duty.id, anya, Vote.DOWN, at("2026-09-25 12:01"))
    await reviews.vote(completion.duty.id, borya, Vote.DOWN, at("2026-09-25 12:02"))
    assert state.credit == 0 and state.skip_debt == 0


async def test_single_member_room_has_no_voters(session):
    room, (anya,) = await make_room(session, members=1)
    completion = await TaskService(session).mark_done(
        await bread(session, room), anya, at("2026-09-25 12:00")
    )
    assert completion.voters == 0

"""Stage 3: money, shopping list, statistics, achievements, export, weekly summary."""

from __future__ import annotations

import csv
import io
import random
from collections import Counter
from datetime import date

import pytest

from bot.charts import PALETTE, Series, fold_series, stacked_bars_png
from bot.db.models import CategoryKind, Duty, DutyStatus, ReviewStatus, Vote
from bot.i18n import I18n
from bot.render import balance_text, stats_chart, top_text, weekly_summary_text
from bot.services.achievements import (
    STREAK_THRESHOLD,
    AchievementService,
    Progress,
    best_streak,
    earned_codes,
)
from bot.services.away import AwayService
from bot.services.errors import ServiceError
from bot.services.export import ExportLabels, ExportService
from bot.services.finance import FinanceService, settle, split_equally
from bot.services.reviews import ReviewService
from bot.services.rooms import RoomService
from bot.services.shopping import ShoppingService, split_items
from bot.services.stats import (
    StatsService,
    is_weekly_summary_due,
    month_bounds,
    shift_month,
)
from bot.services.tasks import TaskService
from bot.utils.money import format_money, parse_amount
from tests.conftest import at, make_room
from tests.test_services import bread

T = I18n().get("ru")


# --- money: pure functions ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "cents"),
    [
        ("45", 4500),
        ("45.5", 4550),
        ("45,50", 4550),
        ("1 200", 120000),
        ("120 лей", 12000),
        ("23.5 MDL", 2350),
        ("0", None),
        ("-5", None),
        ("abc", None),
        ("12.345", None),
        ("99999999", None),
    ],
)
def test_parse_amount(raw: str, cents: int | None):
    assert parse_amount(raw) == cents


def test_format_money():
    assert format_money(4000, "MDL") == "40 MDL"
    assert format_money(12345, "MDL") == "123.45 MDL"
    assert format_money(-4005, "EUR") == "−40.05 EUR"
    assert format_money(123456700, "RON") == "1 234 567 RON"


def test_split_equally_adds_up_exactly():
    shares = split_equally(10000, [3, 1, 2])
    assert sum(shares.values()) == 10000
    assert sorted(shares.values()) == [3333, 3333, 3334]
    with pytest.raises(ValueError):
        split_equally(100, [])


def test_settle_classic_cases():
    # A paid 90 for A, B, C: B and C owe A 30 each.
    assert [
        (t.debtor_id, t.creditor_id, t.amount_cents) for t in settle({1: 60, 2: -30, 3: -30})
    ] == [
        (2, 1, 30),
        (3, 1, 30),
    ]
    # A owes B 10 and B owes C 10: a single transfer A -> C.
    assert [
        (t.debtor_id, t.creditor_id, t.amount_cents) for t in settle({1: -10, 2: 0, 3: 10})
    ] == [(1, 3, 10)]
    assert settle({}) == []


def test_settle_zeroes_every_balance_with_few_transfers():
    rng = random.Random(906)
    for _ in range(300):
        people = rng.randint(2, 6)
        values = [rng.randint(-5000, 5000) for _ in range(people - 1)]
        balances = dict(enumerate([*values, -sum(values)], start=1))
        transfers = settle(balances)
        left = Counter(balances)
        for t in transfers:
            assert t.amount_cents > 0
            left[t.debtor_id] += t.amount_cents
            left[t.creditor_id] -= t.amount_cents
        assert all(v == 0 for v in left.values())
        assert len(transfers) <= max(sum(1 for v in balances.values() if v) - 1, 0)


# --- money: services ------------------------------------------------------------------------


async def test_expense_balance_and_settlement(session):
    room, (anya, borya, vika) = await make_room(session)
    finance = FinanceService(session)
    now = at("2026-09-25 12:00")
    await finance.add_expense(room, anya, 9000, "продукты", [anya.id, borya.id, vika.id], now)
    await finance.add_expense(room, borya, 3000, "пицца", [anya.id, borya.id], now)

    # Anya +90-30-15 = +45, Borya +30-30-15 = -15, Vika -30.
    assert await finance.balances(room) == {anya.id: 4500, borya.id: -1500, vika.id: -3000}
    transfers = await finance.transfers(room)
    assert {(t.debtor_id, t.creditor_id, t.amount_cents) for t in transfers} == {
        (vika.id, anya.id, 3000),
        (borya.id, anya.id, 1500),
    }

    await finance.settle_debt(room, vika.id, anya.id, 3000, now)
    assert await finance.balances(room) == {anya.id: 1500, borya.id: -1500}
    with pytest.raises(ServiceError) as error:
        await finance.settle_debt(room, vika.id, anya.id, 3000, now)
    assert error.value.key == "err-settle-outdated"
    # Paying more than suggested only settles what is owed.
    await finance.settle_debt(room, borya.id, anya.id, 999999, now)
    assert await finance.balances(room) == {}


async def test_expense_validation(session):
    room, (anya, *_) = await make_room(session)
    other_room, (stranger,) = await make_room(session, members=1, chat_id=-2002)
    finance = FinanceService(session)
    now = at("2026-09-25 12:00")
    with pytest.raises(ServiceError) as error:
        await finance.add_expense(room, anya, 0, "x", [anya.id], now)
    assert error.value.key == "err-bad-amount"
    with pytest.raises(ServiceError) as error:
        await finance.add_expense(room, anya, 100, "x", [stranger.id], now)
    assert error.value.key == "err-expense-nobody"
    assert other_room.id != room.id


async def test_amount_after_done_is_split_between_those_at_home(session):
    room, (anya, borya, vika) = await make_room(session)
    await AwayService(session).go_away(room, vika, date(2026, 9, 30), at("2026-09-25 09:00"))
    completion = await TaskService(session).mark_done(
        await bread(session, room), anya, at("2026-09-25 12:00")
    )
    finance = FinanceService(session)
    expense = await finance.record_duty_amount(
        room, completion.duty, anya, 2350, at("2026-09-25 12:01")
    )
    assert completion.duty.amount_cents == 2350
    assert {s.member_id for s in expense.shares} == {anya.id, borya.id}  # Vika is away
    assert await finance.balances(room) == {anya.id: 1175, borya.id: -1175}
    with pytest.raises(ServiceError) as error:
        await finance.record_duty_amount(room, completion.duty, anya, 100, at("2026-09-25 12:02"))
    assert error.value.key == "err-amount-already"

    # A disputed purchase is taken out of the balances.
    await ReviewService(session).vote(completion.duty.id, borya, Vote.DOWN, at("2026-09-25 12:05"))
    await ReviewService(session).vote(completion.duty.id, vika, Vote.DOWN, at("2026-09-25 12:06"))
    assert completion.duty.review == ReviewStatus.DISPUTED
    assert await finance.balances(room) == {}
    assert completion.duty.amount_cents is None


# --- shopping list --------------------------------------------------------------------------


def test_split_items():
    assert split_items("соль, молоко\nхлеб;; Соль ") == ["соль", "молоко", "хлеб"]
    assert split_items(" , ") == []


async def test_shopping_list(session):
    room, (anya, borya, _) = await make_room(session)
    shopping = ShoppingService(session)
    now = at("2026-09-25 12:00")
    added = await shopping.add(room, anya, "соль, молоко", now)
    assert [i.text for i in added] == ["соль", "молоко"]
    assert await shopping.add(room, borya, "Соль", now) == []  # already there
    item = await shopping.mark_bought(room, added[0].id, borya, now)
    assert item.bought_by == borya.id
    assert [i.text for i in await shopping.open_items(room)] == ["молоко"]
    with pytest.raises(ServiceError) as error:
        await shopping.mark_bought(room, added[0].id, borya, now)
    assert error.value.key == "err-item-gone"
    with pytest.raises(ServiceError):
        await shopping.add(room, anya, ", ".join(f"item {i}" for i in range(60)), now)


# --- statistics ----------------------------------------------------------------------------


def test_month_helpers():
    assert month_bounds(2026, 12) == (date(2026, 12, 1), date(2027, 1, 1))
    assert shift_month(2026, 1, -1) == (2025, 12)
    assert shift_month(2026, 12, 1) == (2027, 1)


async def test_month_statistics(session):
    room, (anya, borya, vika) = await make_room(session, now=at("2026-08-20 10:00"))
    category = await bread(session, room)
    tasks = TaskService(session)
    await tasks.mark_done(category, anya, at("2026-08-31 12:00"))  # previous month
    await tasks.mark_done(category, anya, at("2026-09-02 12:00"))
    await tasks.mark_done(category, borya, at("2026-09-03 12:00"))
    disputed = await tasks.mark_done(category, borya, at("2026-09-04 12:00"))
    disputed.duty.review = ReviewStatus.DISPUTED
    session.add(
        Duty(
            category_id=category.id,
            member_id=vika.id,
            status=DutyStatus.SKIPPED,
            created_at=at("2026-09-05 12:00"),
        )
    )
    finance = FinanceService(session)
    await finance.add_expense(room, vika, 5000, "x", [anya.id, vika.id], at("2026-09-06 12:00"))
    await finance.settle_debt(room, anya.id, vika.id, 2500, at("2026-09-07 12:00"))
    await session.flush()

    stats = await StatsService(session).month(room, 2026, 9)
    by_name = {m.member.display_name: m for m in stats.members}
    assert (stats.done, stats.skipped, stats.disputed) == (2, 1, 1)
    assert by_name["Аня"].done == 1 and by_name["Боря"].done == 1
    assert by_name["Вика"].skipped == 1
    assert stats.spent_cents == 5000  # the repayment is not spending
    assert stats.category_total(category.id) == 2

    chart = stats_chart(T, stats, "Сентябрь 2026")
    assert chart is not None and chart.startswith(b"\x89PNG")
    text = top_text(T, stats, {anya.id: ["first_duty"]}, "Сентябрь 2026")
    assert "🥇 Аня — 1 дело 🌱" in text


def test_weekly_summary_schedule():
    class FakeRoom:
        is_active = True
        weekly_summary = True
        timezone = "Europe/Chisinau"
        weekly_summary_sent_on = None

    room = FakeRoom()
    assert not is_weekly_summary_due(room, at("2026-09-27 19:59"))  # Sunday, too early
    assert is_weekly_summary_due(room, at("2026-09-27 20:00"))
    assert not is_weekly_summary_due(room, at("2026-09-26 21:00"))  # Saturday
    room.weekly_summary_sent_on = date(2026, 9, 27)
    assert not is_weekly_summary_due(room, at("2026-09-27 21:00"))
    room.weekly_summary_sent_on, room.weekly_summary = None, False
    assert not is_weekly_summary_due(room, at("2026-09-27 21:00"))


async def test_weekly_summary_text(session):
    room, (anya, borya, _) = await make_room(session, now=at("2026-09-20 10:00"))
    category = await bread(session, room)
    tasks = TaskService(session)
    await tasks.mark_done(category, anya, at("2026-09-22 12:00"))
    await tasks.mark_done(category, anya, at("2026-09-23 12:00"))
    await tasks.mark_done(category, borya, at("2026-09-24 12:00"))
    stats = await StatsService(session).last_week(room, at("2026-09-27 20:00"))
    assert (stats.start, stats.end) == (date(2026, 9, 21), date(2026, 9, 28))
    text = weekly_summary_text(T, room, stats, [(anya, "first_duty")])
    assert "(21.09–27.09)" in text
    assert "Сделано дел: 3 — 🍞 3" in text
    assert "Больше всех: <b>Аня</b> (2)" in text
    assert "🌱 Первый шаг" in text


# --- achievements ---------------------------------------------------------------------------


def _duty(status: DutyStatus, review: ReviewStatus = ReviewStatus.OPEN) -> Duty:
    return Duty(status=status, review=review)


def test_best_streak():
    done, skip = DutyStatus.DONE, DutyStatus.SKIPPED
    history = [_duty(done)] * 3 + [_duty(skip)] + [_duty(done)] * 5 + [_duty(DutyStatus.STILL_HAVE)]
    assert best_streak(history) == 5
    assert best_streak([_duty(done, ReviewStatus.DISPUTED)] * 4) == 0


def test_achievement_rules():
    assert earned_codes(Progress()) == set()
    progress = Progress(
        completed=100,
        out_of_turn=5,
        best_streak=STREAK_THRESHOLD,
        by_kind=Counter({CategoryKind.BREAD: 10, CategoryKind.TRASH: 9}),
        bought_items=10,
        paid_expenses=9,
    )
    assert earned_codes(progress) == {
        "first_duty",
        "bread_king",
        "helper",
        "streak_10",
        "shopper",
        "centurion",
    }


async def test_achievements_are_awarded_once(session):
    room, (anya, *_) = await make_room(session)
    category = await bread(session, room)
    service = AchievementService(session)
    tasks = TaskService(session)
    await tasks.mark_done(category, anya, at("2026-09-25 09:00"))
    assert await service.evaluate(anya, at("2026-09-25 09:01")) == ["first_duty"]
    assert await service.evaluate(anya, at("2026-09-25 09:02")) == []
    for hour in range(10, 19):
        await tasks.mark_done(category, anya, at(f"2026-09-25 {hour}:00"))
    # 10 bread runs in a row; all but the first were out of turn (the queue moved on).
    assert await service.evaluate(anya, at("2026-09-25 19:00")) == [
        "bread_king",
        "helper",
        "streak_10",
    ]
    badges = await service.for_members([anya])
    assert badges[anya.id] == ["first_duty", "bread_king", "helper", "streak_10"]


# --- export & charts ------------------------------------------------------------------------


async def test_csv_export(session):
    room, (anya, borya, _) = await make_room(session)
    category = await bread(session, room)
    await TaskService(session).mark_done(category, anya, at("2026-09-25 12:00"))
    await FinanceService(session).add_expense(
        room, borya, 3000, "пицца", [anya.id, borya.id], at("2026-09-25 13:00")
    )
    labels = ExportLabels(
        duty_headers=("date", "who", "what", "amount", "review"),
        expense_headers=("date", "payer", "amount", "what", "type", "split"),
        status=lambda s: f"status:{s}",
        review=lambda r: "" if r == "open" else r,
        expense_type=lambda settlement: "repayment" if settlement else "expense",
        expenses_filename="expenses",
    )
    files = await ExportService(session).build(room, labels)
    assert [f.filename for f in files] == [
        "01_Хлеб.csv",
        "02_Вода.csv",
        "03_Мусор.csv",
        "expenses.csv",
    ]
    assert files[0].content.startswith(b"\xef\xbb\xbf")  # BOM for Excel
    rows = list(csv.reader(io.StringIO(files[0].content.decode("utf-8-sig"))))
    assert rows == [
        ["date", "who", "what", "amount", "review"],
        ["2026-09-25 12:00", "Аня", "status:done", "", ""],
    ]
    expenses = list(csv.reader(io.StringIO(files[-1].content.decode("utf-8-sig"))))
    assert expenses[1] == ["2026-09-25 13:00", "Боря", "30", "пицца", "expense", "Аня 15; Боря 15"]


def test_chart_folds_extra_categories_and_skips_empty():
    many = [Series(f"c{i}", i, [1, 0]) for i in range(10)]
    folded = fold_series(many, "other")
    assert len(folded) == len(PALETTE) + 1
    assert folded[-1] == ("other", "#898781", [2, 0])
    assert stacked_bars_png("t", ["A"], [Series("x", 0, [0])]) is None
    assert stacked_bars_png("t", ["A", "B"], many).startswith(b"\x89PNG")


async def test_balance_text_and_currency(session):
    room, (anya, borya, _) = await make_room(session)
    await RoomService(session).set_currency(room, "eur")
    names = {anya.id: "Аня", borya.id: "Боря"}
    text = balance_text(
        T, room, {anya.id: 1500, borya.id: -1500}, settle({anya.id: 1500, borya.id: -1500}), names
    )
    assert "Аня: +15 EUR" in text and "Боря: −15 EUR" in text
    assert "• Боря → Аня: 15 EUR" in text
    assert "Все в расчёте" in balance_text(T, room, {}, [], names)

from __future__ import annotations

from datetime import time

import pytest

from bot.services.clock import is_quiet
from bot.utils.parsing import (
    compact_time,
    parse_compact_time,
    parse_time,
    parse_time_range,
    split_emoji,
)
from bot.utils.text import render_table


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (time(23, 30), True),
        (time(3), True),
        (time(7, 59), True),
        (time(8), False),
        (time(12), False),
    ],
)
def test_quiet_hours_over_midnight(moment: time, expected: bool):
    assert is_quiet(moment, time(23), time(8)) is expected


def test_quiet_hours_same_day_and_disabled():
    assert is_quiet(time(14), time(13), time(15))
    assert not is_quiet(time(15), time(13), time(15))
    assert not is_quiet(time(3), None, None)
    assert not is_quiet(time(3), time(5), time(5))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("18:30", time(18, 30)),
        ("8:05", time(8, 5)),
        ("18.30", time(18, 30)),
        ("1830", time(18, 30)),
        ("7", time(7)),
        (" 21 : 15 ", time(21, 15)),
        ("24:00", None),
        ("18:60", None),
        ("abc", None),
        ("", None),
        ("183", None),
    ],
)
def test_parse_time(raw: str, expected: time | None):
    assert parse_time(raw) == expected


def test_compact_time_roundtrip():
    assert compact_time(time(7, 5)) == "0705"
    assert parse_compact_time("0705") == time(7, 5)
    assert parse_compact_time("99") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("23:00-08:00", (time(23), time(8))),
        ("23 - 8", (time(23), time(8))),
        ("22:30 — 07:15", (time(22, 30), time(7, 15))),
        ("10:00-10:00", None),
        ("nonsense", None),
    ],
)
def test_parse_time_range(raw: str, expected):
    assert parse_time_range(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("🧻 Туалетная бумага", ("🧻", "Туалетная бумага")),
        ("🧻Бумага", ("🧻", "Бумага")),
        ("Соль", (None, "Соль")),
        ("Hârtie igienică", (None, "Hârtie igienică")),
        ("", (None, "")),
    ],
)
def test_split_emoji(raw: str, expected):
    assert split_emoji(raw) == expected


def test_render_table_aligns_columns_and_truncates():
    table = render_table(
        ["Date", "Who", "What"],
        [["25.09 18:00", "Александра-Мария", "✅ done"], ["26.09 09:15", "Боря", "⏭ skip"]],
        max_widths=[11, 8, 20],
    )
    lines = table.splitlines()
    assert lines[1] == "25.09 18:00 Алексан… ✅ done"
    assert lines[2].startswith("26.09 09:15 Боря     ⏭")


def test_first_reminder_tick_is_not_skipped_after_a_slow_start():
    from bot.config import Settings
    from bot.scheduler.setup import setup_scheduler

    scheduler = setup_scheduler(
        Settings(bot_token="1:x"),  # type: ignore[arg-type]
        db=None,  # type: ignore[arg-type]
        notifier=None,  # type: ignore[arg-type]
    )
    job = scheduler.get_job("reminder_tick")
    assert job is not None and job.misfire_grace_time >= 5

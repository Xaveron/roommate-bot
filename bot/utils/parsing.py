"""Parsing of user input (times, ranges, category names). Pure functions."""

from __future__ import annotations

import re
from datetime import date, time

_TIME_RE = re.compile(r"^\s*(\d{1,2})(?:\s*[:.\-h]?\s*(\d{2}))?\s*$")
_DAY_MONTH_RE = re.compile(r"^\s*(\d{1,2})\s*[./\-]\s*(\d{1,2})(?:\s*[./\-]\s*(\d{2}|\d{4}))?\s*$")
_ISO_DATE_RE = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*$")
_RANGE_SPLIT_RE = re.compile(r"\s*(?:-|–|—|\.\.|to|до|până la)\s*", re.IGNORECASE)


def parse_time(value: str) -> time | None:
    """Parse '18:30', '18.30', '1830', '18' into a time; None if invalid."""
    match = _TIME_RE.match(value)
    if not match:
        return None
    hours, minutes = match.group(1), match.group(2)
    if minutes is None and len(hours) > 2:
        return None
    h, m = int(hours), int(minutes or 0)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return time(h, m)


def parse_compact_time(value: str) -> time | None:
    """Parse the 'HHMM' form used inside callback data."""
    if len(value) != 4 or not value.isdigit():
        return None
    return parse_time(f"{value[:2]}:{value[2:]}")


def compact_time(value: time) -> str:
    return f"{value.hour:02d}{value.minute:02d}"


def parse_time_range(value: str) -> tuple[time, time] | None:
    """Parse '23:00-08:00' (also '23-8', '23:00 — 08:00')."""
    parts = _RANGE_SPLIT_RE.split(value.strip(), maxsplit=1)
    if len(parts) != 2:
        return None
    start, end = parse_time(parts[0]), parse_time(parts[1])
    if start is None or end is None or start == end:
        return None
    return start, end


def split_emoji(value: str) -> tuple[str | None, str]:
    """'🧻 Toilet paper' -> ('🧻', 'Toilet paper'); 'Soap' -> (None, 'Soap')."""
    value = value.strip()
    if not value:
        return None, ""
    first, _, rest = value.partition(" ")
    if not any(ch.isalnum() for ch in first) and rest.strip():
        return first, rest.strip()
    # Emoji glued to the name: '🧻Paper'.
    index = 0
    while index < len(value) and not value[index].isalnum() and not value[index].isspace():
        index += 1
    if 0 < index < len(value):
        return value[:index], value[index:].strip()
    return None, value


def parse_date(value: str, today: date) -> date | None:
    """Parse '15.10', '15.10.2026', '15/10/26' or '2026-10-15'.

    Without a year the nearest such date that isn't in the past is meant.
    """
    try:
        if match := _ISO_DATE_RE.match(value):
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        match = _DAY_MONTH_RE.match(value)
        if not match:
            return None
        day, month, year = int(match.group(1)), int(match.group(2)), match.group(3)
        if year is not None:
            return date(int(year) + (2000 if len(year) == 2 else 0), month, day)
        candidate = date(today.year, month, day)
        return candidate if candidate >= today else date(today.year + 1, month, day)
    except ValueError:
        return None


def format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def format_time(value: time | None) -> str:
    return "—" if value is None else value.strftime("%H:%M")

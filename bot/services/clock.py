"""Time helpers: every room lives in its own timezone."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def utcnow() -> datetime:
    return datetime.now(UTC)


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def is_valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def local_now(timezone: str, now: datetime) -> datetime:
    return now.astimezone(zone(timezone))


def local_date(timezone: str, now: datetime) -> date:
    return local_now(timezone, now).date()


def is_quiet(moment: time, start: time | None, end: time | None) -> bool:
    """Whether a local time falls into quiet hours [start, end), which may wrap midnight."""
    if start is None or end is None or start == end:
        return False
    if start < end:
        return start <= moment < end
    return moment >= start or moment < end

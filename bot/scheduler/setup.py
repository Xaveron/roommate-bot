from __future__ import annotations

from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from bot.config import Settings
from bot.db import Database
from bot.notifications import Notifier
from bot.scheduler.jobs import reminder_tick


def setup_scheduler(settings: Settings, db: Database, notifier: Notifier) -> AsyncIOScheduler:
    """One short periodic job checks what is due in every room's own timezone.

    This survives restarts (state lives in the database), catches up after downtime and
    doesn't need to re-register jobs whenever a room changes its settings.
    """
    scheduler = AsyncIOScheduler(timezone=UTC)
    scheduler.add_job(
        reminder_tick,
        IntervalTrigger(seconds=settings.scheduler_tick_seconds, timezone=UTC),
        kwargs={"db": db, "notifier": notifier},
        id="reminder_tick",
        max_instances=1,
        coalesce=True,
        # Startup work (e.g. registering bot commands) may delay the first run by a few
        # seconds; run it late rather than skip it.
        misfire_grace_time=max(settings.scheduler_tick_seconds // 2, 5),
        next_run_time=datetime.now(UTC),
    )
    return scheduler

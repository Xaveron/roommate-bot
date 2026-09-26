"""Scheduled jobs."""

from __future__ import annotations

import logging
from datetime import datetime, time

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import Database
from bot.db.models import Room
from bot.db.repositories import RoomRepo
from bot.notifications import Notifier
from bot.render import weekly_summary_text
from bot.services.achievements import AchievementService
from bot.services.clock import local_now, utcnow, zone
from bot.services.reminders import DeliveryKind, ReminderService, room_is_quiet
from bot.services.stats import StatsService, is_weekly_summary_due

logger = logging.getLogger(__name__)


async def reminder_tick(db: Database, notifier: Notifier) -> None:
    """Deliver every reminder that is due now, room by room.

    Each room is processed in its own transaction so that one broken room (or a Telegram
    error) never blocks reminders of the others.
    """
    now = utcnow()
    async with db.session() as session:
        rooms = [(room.id, room.chat_id) for room in await RoomRepo(session).list_active()]

    for room_id, chat_id in rooms:
        try:
            # The same lock as the room's updates: a tick never races a button press.
            async with db.lock_for(chat_id), db.session() as session:
                room = await RoomRepo(session).get(room_id)
                if room is None:
                    continue
                for delivery in await ReminderService(session).plan_room(room, now):
                    if delivery.kind == DeliveryKind.NUDGE:
                        await notifier.nudge(delivery.assignment, now)
                    else:
                        await notifier.deliver_reminder(delivery.assignment, now)
                if is_weekly_summary_due(room, now) and not room_is_quiet(room, now):
                    await send_weekly_summary(session, notifier, room, now)
                await session.commit()
        except Exception:
            logger.exception("Reminder tick failed for room %s", room_id)


async def send_weekly_summary(
    session: AsyncSession, notifier: Notifier, room: Room, now: datetime
) -> None:
    """Sunday evening: what the room did this week."""
    stats = await StatsService(session).last_week(room, now)
    tz = zone(room.timezone)
    since = datetime.combine(stats.start, time(0), tzinfo=tz)
    until = datetime.combine(stats.end, time(0), tzinfo=tz)
    members = [m.member for m in stats.members]
    badges = await AchievementService(session).earned_between(members, since, until)
    text = weekly_summary_text(notifier.translator(room), room, stats, badges)
    await notifier.send_group(room, text)
    room.weekly_summary_sent_on = local_now(room.timezone, now).date()

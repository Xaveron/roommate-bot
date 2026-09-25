"""Scheduled jobs."""

from __future__ import annotations

import logging

from bot.db import Database
from bot.db.repositories import RoomRepo
from bot.notifications import Notifier
from bot.services.clock import utcnow
from bot.services.reminders import ReminderService

logger = logging.getLogger(__name__)


async def reminder_tick(db: Database, notifier: Notifier) -> None:
    """Deliver every reminder that is due now, room by room.

    Each room is processed in its own transaction so that one broken room (or a Telegram
    error) never blocks reminders of the others.
    """
    now = utcnow()
    async with db.session() as session:
        room_ids = [room.id for room in await RoomRepo(session).list_active()]

    for room_id in room_ids:
        try:
            async with db.session() as session:
                room = await RoomRepo(session).get(room_id)
                if room is None:
                    continue
                for assignment in await ReminderService(session).plan_room(room, now):
                    await notifier.deliver_reminder(assignment, now)
                await session.commit()
        except Exception:
            logger.exception("Reminder tick failed for room %s", room_id)

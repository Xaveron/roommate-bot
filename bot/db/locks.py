"""Locks that work across processes.

The bot and the Mini App API are separate processes that change the same rooms, so an
``asyncio.Lock`` (see ``Database.lock_for``) can't keep them apart. Every unit of work that
changes a room takes the room's lock first; the lock is held until the transaction ends.

* PostgreSQL: a transaction-level advisory lock, keyed by the room id. Taking it twice in one
  transaction is fine, and it's released on commit or rollback.
* SQLite: nothing to do. It allows a single writer, and ``Database`` already serializes the
  units of work of one process. Running the bot and the Mini App against one SQLite file is
  meant for development only; production uses PostgreSQL.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# First half of the two-part advisory lock key, so room locks can't collide with other locks.
ROOM_LOCK_SPACE = 0x524D  # "RM"


async def lock_room(session: AsyncSession, room_id: int) -> None:
    """Wait until no other transaction works on the room, then hold it until commit."""
    if session.bind.dialect.name == "postgresql":
        await session.execute(select(func.pg_advisory_xact_lock(ROOM_LOCK_SPACE, room_id)))


async def refreshed[T](session: AsyncSession, instance: T) -> T:
    """Re-read a row that was loaded before the lock was taken.

    Changes made to it in this transaction are flushed first, so they aren't lost.
    """
    await session.flush()
    await session.refresh(instance)
    return instance

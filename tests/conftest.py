from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool, StaticPool

from bot.db import Database
from bot.db.models import Base, Member, Room
from bot.db.repositories import UserRepo
from bot.db.session import create_engine
from bot.services.rooms import RoomService

TZ = "Europe/Chisinau"
NAMES = {"bread": "Хлеб", "water": "Вода", "trash": "Мусор"}
PEOPLE = ("Аня", "Боря", "Вика", "Гриша")

# Run the suite against PostgreSQL instead of in-memory SQLite, e.g.
# TEST_DATABASE_URL=postgresql+asyncpg://postgres:test@127.0.0.1:55432/roommate_test pytest
# The database is wiped before and after every test.
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


def at(local: str) -> datetime:
    """'2026-09-25 18:00' in the room timezone -> aware UTC datetime."""
    return datetime.fromisoformat(local).replace(tzinfo=ZoneInfo(TZ)).astimezone(UTC)


@pytest.fixture
async def db() -> AsyncIterator[Database]:
    if TEST_DATABASE_URL:
        url = TEST_DATABASE_URL
        engine = create_engine(url, poolclass=NullPool)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
    else:
        url = "sqlite+aiosqlite://"
        engine = create_engine(url, poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    database = Database(url, engine=engine)
    yield database
    if TEST_DATABASE_URL:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
    await database.dispose()


@pytest.fixture
async def session(db: Database) -> AsyncIterator[AsyncSession]:
    async with db.session() as session:
        yield session


async def make_room(
    session: AsyncSession,
    members: int = 3,
    now: datetime | None = None,
    chat_id: int = -1001,
) -> tuple[Room, list[Member]]:
    now = now or at("2026-09-25 10:00")
    service = RoomService(session)
    room, _ = await service.get_or_create(
        chat_id=chat_id,
        title="906B",
        created_by=1,
        language="ru",
        timezone=TZ,
        default_names=NAMES,
        now=now,
    )
    result = []
    for index, name in enumerate(PEOPLE[:members], start=1):
        user_id = index if chat_id == -1001 else abs(chat_id) * 10 + index
        user = await UserRepo(session).upsert(user_id=user_id, first_name=name)
        member, _ = await service.join(room, user, now)
        result.append(member)
    return room, result

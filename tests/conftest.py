from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import StaticPool

from bot.db import Database
from bot.db.models import Base, Member, Room
from bot.db.repositories import UserRepo
from bot.db.session import create_engine
from bot.services.rooms import RoomService

TZ = "Europe/Chisinau"
NAMES = {"bread": "Хлеб", "water": "Вода", "trash": "Мусор"}
PEOPLE = ("Аня", "Боря", "Вика", "Гриша")


def at(local: str) -> datetime:
    """'2026-09-25 18:00' in the room timezone -> aware UTC datetime."""
    return datetime.fromisoformat(local).replace(tzinfo=ZoneInfo(TZ)).astimezone(UTC)


@pytest.fixture
async def db() -> AsyncIterator[Database]:
    url = "sqlite+aiosqlite://"
    engine = create_engine(url, poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    database = Database(url, engine=engine)
    yield database
    await database.dispose()


@pytest.fixture
async def session(db: Database) -> AsyncIterator[AsyncSession]:
    async with db.session() as session:
        yield session


async def make_room(
    session: AsyncSession, members: int = 3, now: datetime | None = None
) -> tuple[Room, list[Member]]:
    now = now or at("2026-09-25 10:00")
    service = RoomService(session)
    room, _ = await service.get_or_create(
        chat_id=-1001,
        title="906B",
        created_by=1,
        language="ru",
        timezone=TZ,
        default_names=NAMES,
        now=now,
    )
    result = []
    for index, name in enumerate(PEOPLE[:members], start=1):
        user = await UserRepo(session).upsert(user_id=index, first_name=name)
        member, _ = await service.join(room, user, now)
        result.append(member)
    return room, result

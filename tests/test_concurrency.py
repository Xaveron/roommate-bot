"""Updates of one chat can arrive at the same moment (e.g. "bot added" + /start).

On PostgreSQL they are handled concurrently, so creating rows must be idempotent. Run with
TEST_DATABASE_URL to exercise real concurrency; on SQLite the sessions are serialized anyway.
"""

from __future__ import annotations

import asyncio

from bot.db import Database
from bot.db.repositories import MemberRepo, UserRepo
from bot.services.rooms import RoomService
from tests.conftest import NAMES, TZ, at


async def _create_room(db: Database, chat_id: int) -> tuple[int, bool]:
    async with db.session() as session:
        room, created = await RoomService(session).get_or_create(
            chat_id=chat_id,
            title="906B",
            created_by=1,
            language="ru",
            timezone=TZ,
            default_names=NAMES,
            now=at("2026-09-26 12:00"),
        )
        await session.commit()
        return room.id, created


async def test_concurrent_room_creation_is_idempotent(db: Database):
    results = await asyncio.gather(*(_create_room(db, -5116846028) for _ in range(3)))
    assert len({room_id for room_id, _ in results}) == 1
    assert sorted(created for _, created in results) == [False, False, True]


async def test_concurrent_user_upsert_and_join(db: Database):
    room_id, _ = await _create_room(db, -777)

    async def upsert_and_join() -> int:
        async with db.session() as session:
            user = await UserRepo(session).upsert(user_id=42, first_name="Аня")
            service = RoomService(session)
            room = await service.rooms.get(room_id)
            member, _ = await service.join(room, user, at("2026-09-26 12:00"))  # type: ignore[arg-type]
            await session.commit()
            return member.id

    member_ids = await asyncio.gather(*(upsert_and_join() for _ in range(3)))
    assert len(set(member_ids)) == 1
    async with db.session() as session:
        assert len(await MemberRepo(session).list(room_id)) == 1


async def test_updates_of_one_chat_are_serialized(db: Database):
    """The middleware lock: work for one chat never interleaves, other chats aren't blocked."""
    events: list[str] = []

    async def work(chat_id: int, name: str) -> None:
        async with db.lock_for(chat_id):
            events.append(f"{name}:start")
            await asyncio.sleep(0.05)
            events.append(f"{name}:end")

    await asyncio.gather(work(1, "a"), work(1, "b"), work(2, "c"))
    first, second = ("a", "b") if events.index("a:start") < events.index("b:start") else ("b", "a")
    assert events.index(f"{first}:end") < events.index(f"{second}:start")
    assert events.index("c:start") < events.index(f"{first}:end")  # chat 2 ran in parallel

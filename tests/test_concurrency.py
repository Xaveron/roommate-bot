"""Concurrent work on one room.

* Updates of one chat can arrive at the same moment (e.g. "bot added" + /start). On
  PostgreSQL they are handled concurrently, so creating rows must be idempotent.
* The bot and the Mini App are separate processes; the room lock (``bot.db.locks``) keeps
  them from doing the same thing twice.

Run with TEST_DATABASE_URL to exercise real concurrency; on SQLite the sessions are
serialized anyway.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from sqlalchemy.pool import NullPool

from bot.config import Settings
from bot.db import Database
from bot.db.locks import lock_room
from bot.db.models import DutyStatus
from bot.db.repositories import CategoryRepo, DutyRepo, MemberRepo, RoomRepo, UserRepo
from bot.keyboards.callbacks import JoinCb, TurnCb
from bot.notifications import Notifier
from bot.services.clock import local_date, utcnow
from bot.services.queue import QueueService
from bot.services.rooms import RoomService
from bot.services.tasks import TaskService
from bot.webapi.app import create_app
from tests.conftest import NAMES, TEST_DATABASE_URL, TZ, at, make_room
from tests.test_bot_flow import ANYA, BORYA, GROUP, Harness, private
from tests.test_webapi import headers

BOT_TOKEN = "42:TEST"  # the token of the test harness; initData is signed with it


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


# --- the bot and the Mini App are two processes ---------------------------------------------


@asynccontextmanager
async def mini_app(db: Database, notifier: Notifier, tmp_path: Path):
    """The Mini App API with its own connection pool, like the separate webapp container.

    On SQLite (a single in-memory database) it has to share the bot's ``Database``.
    """
    app_db = Database(TEST_DATABASE_URL, poolclass=NullPool) if TEST_DATABASE_URL else db
    settings = Settings(bot_token=BOT_TOKEN, webapp_dist=str(tmp_path / "no-dist"))  # type: ignore[arg-type]
    app = create_app(settings, app_db, notifier)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://test"
        ) as client:
            yield client
    finally:
        if app_db is not db:
            await app_db.dispose()


def as_user(user_id: int) -> dict[str, str]:
    return headers(user_id, token=BOT_TOKEN)


async def test_done_from_the_bot_and_the_app_at_once_counts_once(db: Database, tmp_path: Path):
    """Anya presses "Done" under the reminder in Telegram and in the Mini App simultaneously."""
    h = Harness(db)
    try:
        await h.message(ANYA, "/start")
        await h.press(ANYA, JoinCb().pack())
        await h.press(BORYA, JoinCb().pack())
        async with db.session() as session:
            room = await RoomRepo(session).get_by_chat_id(GROUP.id)
            assert room is not None
            bread = (await CategoryRepo(session).list(room.id))[0]
            turn = await TaskService(session).assign_next(bread, utcnow())
            assert turn is not None and turn.member.telegram_user_id == ANYA.id
            await session.commit()
            room_id, bread_id, turn_id = room.id, bread.id, turn.id

        async with mini_app(db, h.notifier, tmp_path) as client:
            _, response = await asyncio.gather(
                h.press(
                    ANYA,
                    TurnCb(action="done", assignment_id=turn_id).pack(),
                    chat=private(ANYA),
                ),
                client.post(
                    f"/api/rooms/{room_id}/categories/{bread_id}/done",
                    json={"in_turn": True},
                    headers=as_user(ANYA.id),
                ),
            )

        async with db.session() as session:
            duties = await DutyRepo(session).list_for_room(room_id)
            assert [d.status for d in duties] == [DutyStatus.DONE]
            bread = await CategoryRepo(session).get(bread_id)
            assert bread is not None
            current = await QueueService(session).current(bread, local_date(TZ, utcnow()))
            assert current is not None and current.telegram_user_id == BORYA.id
        # Exactly one side was told that it's done already.
        refused_by_bot = "Эта задача уже неактуальна 🙂" in h.alerts()
        refused_by_app = response.status_code == 409
        assert refused_by_bot != refused_by_app, (h.alerts(), response.text)
        if refused_by_app:
            assert response.json()["detail"]["code"] == "err-turn-changed"
        assert len([m for m in h.session.sent(GROUP.id) if "готово!" in m.text]) == 1
    finally:
        for root in h.dp.sub_routers:
            for router in root.sub_routers:
                router._parent_router = None


async def test_two_devices_mark_the_same_turn_once(db: Database, tmp_path: Path):
    """No reminder yet (nothing to lock a row on): only the room lock keeps them apart."""
    h = Harness(db)
    try:
        async with db.session() as session:
            room, (anya, _) = await make_room(session, members=2)
            bread = (await CategoryRepo(session).list(room.id))[0]
            await session.commit()
            room_id, bread_id, anya_user = room.id, bread.id, anya.telegram_user_id

        async with mini_app(db, h.notifier, tmp_path) as client:
            responses = await asyncio.gather(
                *(
                    client.post(
                        f"/api/rooms/{room_id}/categories/{bread_id}/done",
                        json={"in_turn": True},
                        headers={**as_user(anya_user), "Idempotency-Key": f"device-{n}-key"},
                    )
                    for n in range(2)
                )
            )
        assert sorted(r.status_code for r in responses) == [200, 409]
        async with db.session() as session:
            assert len(await DutyRepo(session).list_for_room(room_id)) == 1
    finally:
        for root in h.dp.sub_routers:
            for router in root.sub_routers:
                router._parent_router = None


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="needs PostgreSQL: two connections")
async def test_the_app_waits_while_the_bot_works_on_the_room(db: Database, tmp_path: Path):
    async with db.session() as session:
        room, _ = await make_room(session, members=2)
        await session.commit()
        room_id = room.id

    notifier = Harness(db).notifier
    async with mini_app(db, notifier, tmp_path) as client, db.session() as bot_session:
        await lock_room(bot_session, room_id)  # the bot is in the middle of an update
        request = asyncio.create_task(
            client.post(f"/api/rooms/{room_id}/shopping", json={"text": "соль"}, headers=as_user(1))
        )
        await asyncio.sleep(0.5)
        assert not request.done(), "the Mini App must wait for the room lock"
        await bot_session.commit()  # the update is handled: the lock is released
        response = await asyncio.wait_for(request, timeout=5)
    assert response.status_code == 200

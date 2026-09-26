"""Mini App actions: same services, same rights and same Telegram effects as the bot."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import EditMessageReplyMarkup, EditMessageText, SendMessage
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from bot.db import Database
from bot.db.models import AssignmentStatus, DutyStatus, Room
from bot.db.repositories import (
    AssignmentRepo,
    CategoryRepo,
    DutyRepo,
    ExpenseRepo,
    MemberRepo,
    RoomRepo,
)
from bot.i18n import I18n
from bot.notifications import Notifier
from bot.services.clock import utcnow
from bot.services.shopping import ShoppingService
from bot.services.tasks import TaskService
from bot.webapi.app import create_app
from tests.conftest import make_room
from tests.test_bot_flow import FakeSession
from tests.test_webapi import TOKEN, headers

GROUP_CHAT = -1001  # make_room's chat


@dataclass
class Env:
    client: httpx.AsyncClient
    tg: FakeSession
    db: Database
    notifier: Notifier

    async def post(
        self, path: str, user: int = 1, json: Any = None, key: str | None = None
    ) -> httpx.Response:
        extra = {"Idempotency-Key": key} if key else {}
        return await self.client.post(f"/api{path}", json=json, headers={**headers(user), **extra})

    async def get(self, path: str, user: int = 1) -> Any:
        response = await self.client.get(f"/api{path}", headers=headers(user))
        assert response.status_code == 200, response.text
        return response.json()

    def group(self) -> list[SendMessage]:
        return self.tg.sent(GROUP_CHAT)


@pytest.fixture
async def env(db: Database, tmp_path: Path) -> AsyncIterator[Env]:
    tg = FakeSession(forbidden_chats=set())
    bot = Bot("42:TEST", session=tg, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    notifier = Notifier(bot, I18n())
    settings = Settings(bot_token=TOKEN, webapp_dist=str(tmp_path / "no-dist"))  # type: ignore[arg-type]
    app = create_app(settings, db, notifier)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        yield Env(client, tg, db, notifier)


@dataclass
class Ids:
    room: int
    other_room: int
    bread: int
    water: int
    trash: int
    anya: int
    borya: int
    vika: int


async def seed(db: Database) -> Ids:
    """Anya, Borya and Vika; everybody has started the bot in private chat."""
    async with db.session() as session:
        room, (anya, borya, vika) = await make_room(session, now=utcnow() - timedelta(days=3))
        for member in (anya, borya, vika):
            member.user.dm_available = True
        other_room, _ = await make_room(session, members=1, chat_id=-2002)
        bread, water, trash = await CategoryRepo(session).list(room.id)
        await session.commit()
        return Ids(room.id, other_room.id, bread.id, water.id, trash.id, anya.id, borya.id, vika.id)


async def remind(env: Env, category_id: int) -> int:
    """Issue today's turn of a category and deliver the reminder; returns the assignment id."""
    async with env.db.session() as session:
        category = await CategoryRepo(session).get(category_id)
        assert category is not None
        assignment = await TaskService(session).assign_next(category, utcnow())
        assert assignment is not None
        await env.notifier.deliver_reminder(assignment, utcnow())
        await session.commit()
        return assignment.id


async def assignment_status(db: Database, assignment_id: int) -> str:
    async with db.session() as session:
        assignment = await AssignmentRepo(session).get(assignment_id)
        assert assignment is not None
        return assignment.status


def detail(response: httpx.Response) -> dict[str, str]:
    return response.json()["detail"]


# --- turns ---------------------------------------------------------------------------------


async def test_accept_then_done_with_amount(env: Env):
    ids = await seed(env.db)
    turn = await remind(env, ids.bread)
    reminder = env.tg.sent(1)[-1]
    assert "купить хлеб" in reminder.text

    # Borya can't answer Anya's reminder.
    response = await env.post(f"/rooms/{ids.room}/turns/{turn}/accept", user=2)
    assert response.status_code == 403
    assert detail(response) == {"code": "err-not-your-turn", "message": "Это не твоя очередь 🙂"}

    # "I'll buy it": the reminder in private chat shows the new state and buttons.
    response = await env.post(f"/rooms/{ids.room}/turns/{turn}/accept")
    assert response.json() == {"message": "👍 Жду «Готово»"}
    edit = env.tg.of(EditMessageText)[-1]
    assert edit.chat_id == 1
    assert "Нажми «Готово ✅»" in edit.text
    assert [b.text for row in edit.reply_markup.inline_keyboard for b in row] == [
        "Готово ✅",
        "⏭ Не могу сегодня",
    ]
    queue = await env.get(f"/rooms/{ids.room}/queue")
    bread = next(c for c in queue["categories"] if c["id"] == ids.bread)
    assert (bread["status"], bread["assignment_id"]) == ("accepted", turn)

    # "Done" with what it cost: announced in the group with 👍 / 🤨, split between 3.
    response = await env.post(
        f"/rooms/{ids.room}/categories/{ids.bread}/done", json={"in_turn": True, "amount": "30,5"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["message"].startswith("✅ Записал: 30.50 MDL за 🍞 Хлеб")
    announcement = next(m for m in env.group() if "готово" in m.text)
    assert "🍞 Хлеб — готово! Спасибо, <b>Аня</b>" in announcement.text
    assert "Следующая очередь: <b>Боря</b>" in announcement.text
    assert [b.text for b in announcement.reply_markup.inline_keyboard[0]] == [
        "👍",
        "🤨 А вот и нет",
    ]
    assert any("30.50 MDL" in m.text and "Аня" in m.text for m in env.group())
    assert any("Первый шаг" in m.text for m in env.group())  # achievement
    assert "Готово, спасибо" in env.tg.of(EditMessageText)[-1].text  # reminder closed
    assert await assignment_status(env.db, turn) == AssignmentStatus.DONE

    async with env.db.session() as session:
        (duty,) = await DutyRepo(session).list_for_room(ids.room)
        assert (duty.status, duty.amount_cents) == (DutyStatus.DONE, 3050)
        assert duty.message_chat_id == GROUP_CHAT and duty.message_id is not None

    # Pressing "Done" again from a stale screen doesn't count twice.
    response = await env.post(
        f"/rooms/{ids.room}/categories/{ids.bread}/done", json={"in_turn": True}
    )
    assert response.status_code == 409
    assert detail(response)["code"] == "err-turn-changed"


async def test_decline_hands_the_turn_over(env: Env):
    ids = await seed(env.db)
    turn = await remind(env, ids.bread)
    response = await env.post(f"/rooms/{ids.room}/turns/{turn}/decline")
    assert response.json() == {"message": "⏭ Передаю очередь дальше"}
    assert "сегодня очередь у: <b>Боря</b>" in env.tg.of(EditMessageText)[-1].text
    assert "Аня</b> сегодня пропускает" in env.group()[-1].text
    assert "купить хлеб" in env.tg.sent(2)[-1].text  # Borya is reminded at once

    queue = await env.get(f"/rooms/{ids.room}/queue", user=2)
    bread = next(c for c in queue["categories"] if c["id"] == ids.bread)
    assert bread["current"]["member_id"] == ids.borya and bread["status"] == "pending"
    assert {m["member_id"]: m["skip_debt"] for m in bread["marks"]} == {ids.anya: 1}

    # The old turn is closed now.
    response = await env.post(f"/rooms/{ids.room}/turns/{turn}/still")
    assert response.status_code == 409 and detail(response)["code"] == "err-assignment-closed"


async def test_still_have_snoozes_until_tomorrow(env: Env):
    ids = await seed(env.db)
    turn = await remind(env, ids.water)
    response = await env.post(f"/rooms/{ids.room}/turns/{turn}/still")
    assert response.json() == {"message": "🔄 Напомню завтра"}
    assert "напомню завтра" in env.tg.of(EditMessageText)[-1].text
    queue = await env.get(f"/rooms/{ids.room}/queue")
    water = next(c for c in queue["categories"] if c["id"] == ids.water)
    today = queue["today"]
    assert water["status"] == "snoozed" and water["remind_on"] > today


async def test_out_of_turn_covers_the_open_reminder(env: Env):
    ids = await seed(env.db)
    turn = await remind(env, ids.bread)

    # Borya's screen showed "Did it out of turn"; "Done" (in turn) would be refused.
    response = await env.post(
        f"/rooms/{ids.room}/categories/{ids.bread}/done", user=2, json={"in_turn": True}
    )
    assert response.status_code == 409 and detail(response)["code"] == "err-turn-changed"
    response = await env.post(
        f"/rooms/{ids.room}/categories/{ids.bread}/done", user=2, json={"in_turn": False}
    )
    assert response.status_code == 200
    assert "Боря</b> — вне очереди" in env.tg.last_with(GROUP_CHAT, "вне очереди").text
    assert "Уже сделано вне очереди: <b>Боря</b>" in env.tg.of(EditMessageText)[-1].text
    assert await assignment_status(env.db, turn) == AssignmentStatus.COVERED


async def test_trash_ignores_the_amount_and_bad_amounts_are_refused(env: Env):
    ids = await seed(env.db)
    response = await env.post(
        f"/rooms/{ids.room}/categories/{ids.bread}/done", json={"in_turn": True, "amount": "abc"}
    )
    assert response.status_code == 422
    assert detail(response) == {
        "code": "err-bad-amount",
        "message": "Не понял сумму. Пример: 23.50",
    }
    response = await env.post(
        f"/rooms/{ids.room}/categories/{ids.trash}/done", json={"in_turn": True, "amount": "5"}
    )
    assert response.status_code == 200 and response.json()["message"] == "✅ Засчитано!"
    async with env.db.session() as session:
        assert not await ExpenseRepo(session).list_for_room(ids.room)


async def test_votes_update_the_group_message(env: Env):
    ids = await seed(env.db)
    await env.post(f"/rooms/{ids.room}/categories/{ids.bread}/done", json={"in_turn": True})
    history = await env.get(f"/rooms/{ids.room}/history", user=2)
    (item,) = history["items"]
    assert (item["can_vote"], item["votes_up"], item["my_vote"]) == (True, 0, None)
    own = (await env.get(f"/rooms/{ids.room}/history", user=1))["items"][0]
    assert own["can_vote"] is False

    response = await env.post(f"/rooms/{ids.room}/duties/{item['id']}/vote", json={"vote": "up"})
    assert response.status_code == 409 and detail(response)["code"] == "err-vote-self"

    # Borya: the counter under the announcement changes.
    response = await env.post(
        f"/rooms/{ids.room}/duties/{item['id']}/vote", user=2, json={"vote": "down"}
    )
    assert response.json() == {"message": "Голос учтён 👌"}
    counters = env.tg.of(EditMessageReplyMarkup)[-1]
    async with env.db.session() as session:
        duty = await DutyRepo(session).get(item["id"])
        assert duty is not None
    assert (counters.chat_id, counters.message_id) == (GROUP_CHAT, duty.message_id)
    assert [b.text for b in counters.reply_markup.inline_keyboard[0]] == [
        "👍",
        "🤨 А вот и нет · 1",
    ]
    item = (await env.get(f"/rooms/{ids.room}/history", user=2))["items"][0]
    assert (item["votes_down"], item["my_vote"]) == (1, "down")

    # Vika: the majority decided, the buttons go and the verdict is a reply.
    await env.post(f"/rooms/{ids.room}/duties/{item['id']}/vote", user=3, json={"vote": "down"})
    assert env.tg.of(EditMessageReplyMarkup)[-1].reply_markup is None
    verdict = env.group()[-1]
    assert "Большинство против" in verdict.text
    assert verdict.reply_parameters.message_id == duty.message_id
    item = (await env.get(f"/rooms/{ids.room}/history", user=2))["items"][0]
    assert item["review"] == "disputed" and item["can_vote"] is False


# --- money ---------------------------------------------------------------------------------


async def test_expense_and_settling_up(env: Env):
    ids = await seed(env.db)
    balance = await env.get(f"/rooms/{ids.room}/balance", user=2)
    assert [(m["name"], m["at_home"]) for m in balance["members"]] == [
        ("Аня", True),
        ("Боря", True),
        ("Вика", True),
    ]
    response = await env.post(
        f"/rooms/{ids.room}/expenses",
        user=2,
        json={"amount": "90", "description": "пицца", "member_ids": [ids.anya, ids.borya]},
    )
    assert response.json() == {"message": "Сохранено ✅"}
    assert "пицца" in env.group()[-1].text and "Аня, Боря" in env.group()[-1].text
    balance = await env.get(f"/rooms/{ids.room}/balance", user=2)
    assert balance["transfers"] == [
        {
            "debtor_id": ids.anya,
            "debtor_name": "Аня",
            "creditor_id": ids.borya,
            "creditor_name": "Боря",
            "cents": 4500,
        }
    ]

    settle = {"debtor_id": ids.anya, "creditor_id": ids.borya, "cents": 4500}
    response = await env.post(f"/rooms/{ids.room}/settle", user=3, json=settle)
    assert response.status_code == 403 and detail(response)["code"] == "err-settle-not-yours"
    response = await env.post(f"/rooms/{ids.room}/settle", user=1, json=settle)
    assert response.status_code == 200
    assert "Долг закрыт: <b>Аня</b> → <b>Боря</b>, 45 MDL" in env.group()[-1].text
    response = await env.post(f"/rooms/{ids.room}/settle", user=1, json=settle)
    assert response.status_code == 409 and detail(response)["code"] == "err-settle-outdated"

    for body, code in (
        ({"amount": "0", "member_ids": [ids.anya]}, "err-bad-amount"),
        ({"amount": "10", "member_ids": [999]}, "err-expense-nobody"),
    ):
        response = await env.post(f"/rooms/{ids.room}/expenses", json=body)
        assert response.status_code == 422 and detail(response)["code"] == code


async def test_idempotency_key_prevents_a_second_expense(env: Env):
    ids = await seed(env.db)
    body = {"amount": "12", "description": "соль", "member_ids": [ids.anya, ids.borya]}
    first = await env.post(f"/rooms/{ids.room}/expenses", json=body, key="key-0001-expense")
    again = await env.post(f"/rooms/{ids.room}/expenses", json=body, key="key-0001-expense")
    assert first.status_code == again.status_code == 200
    assert again.json() == first.json() and again.headers["idempotent-replayed"] == "true"
    other = await env.post(f"/rooms/{ids.room}/expenses", json=body, key="key-0002-expense")
    assert "idempotent-replayed" not in other.headers
    async with env.db.session() as session:
        assert len(await ExpenseRepo(session).list_for_room(ids.room)) == 2
    assert sum("соль" in m.text for m in env.group()) == 2


# --- shopping list -------------------------------------------------------------------------


async def test_shopping_list(env: Env):
    ids = await seed(env.db)
    response = await env.post(f"/rooms/{ids.room}/shopping", json={"text": "соль, молоко"})
    assert response.json() == {"message": "🛒 Добавлено в список: соль, молоко"}
    response = await env.post(f"/rooms/{ids.room}/shopping", json={"text": "Соль"})
    assert response.json() == {"message": "Это уже есть в списке 🙂"}
    response = await env.post(f"/rooms/{ids.room}/shopping", json={"text": " , "})
    assert response.status_code == 422

    listing = await env.get(f"/rooms/{ids.room}/shopping", user=2)
    assert [(i["text"], i["added_by"]) for i in listing["items"]] == [
        ("соль", "Аня"),
        ("молоко", "Аня"),
    ]
    salt = listing["items"][0]["id"]
    response = await env.post(f"/rooms/{ids.room}/shopping/{salt}/bought", user=2)
    assert response.json() == {"message": "Отмечено ✅"}
    response = await env.post(f"/rooms/{ids.room}/shopping/{salt}/bought", user=3)
    assert response.status_code == 409 and detail(response)["code"] == "err-item-gone"

    response = await env.post(f"/rooms/{ids.room}/shopping/going", user=2)
    assert response.json() == {"message": "📣 Сообщил всем!"}
    assert "<b>Боря</b> идёт в магазин" in env.group()[-1].text
    assert "молоко" in env.group()[-1].text and "соль" not in env.group()[-1].text
    assert "Боря" in env.tg.sent(1)[-1].text and "Боря" in env.tg.sent(3)[-1].text


# --- away ----------------------------------------------------------------------------------


async def test_away_and_back(env: Env):
    ids = await seed(env.db)
    response = await env.post(f"/rooms/{ids.room}/away", user=2, json={"days": 7})
    queue = await env.get(f"/rooms/{ids.room}/queue", user=2)
    today = queue["today"]
    ((away),) = queue["away"]
    assert away["member_id"] == ids.borya and away["until"] > today
    assert response.json()["message"].startswith("🏖 Готово: пропускаю тебя в очередях до ")
    assert "<b>Боря</b> в отъезде до" in env.group()[-1].text
    assert all(p["member_id"] != ids.borya for p in queue["members"])

    response = await env.post(f"/rooms/{ids.room}/back", user=2)
    assert response.json()["message"].startswith("🏠 С возвращением!")
    assert "<b>Боря</b> снова дома" in env.group()[-1].text
    response = await env.post(f"/rooms/{ids.room}/back", user=2)
    assert response.json() == {"message": "Ты и так в очередях 🙂"}

    response = await env.post(f"/rooms/{ids.room}/away", json={"until": "2020-01-01"})
    assert response.status_code == 422 and detail(response)["code"] == "err-date-past"
    response = await env.post(f"/rooms/{ids.room}/away", json={})
    assert response.status_code == 422  # neither `until` nor `days`
    far = await env.post(f"/rooms/{ids.room}/away", json={"until": "2099-01-01"})
    assert far.status_code == 422 and "365" in detail(far)["message"]


# --- rights --------------------------------------------------------------------------------


async def test_strangers_and_foreign_ids_are_refused(env: Env):
    ids = await seed(env.db)
    turn = await remind(env, ids.bread)
    async with env.db.session() as session:
        other_bread = (await CategoryRepo(session).list(ids.other_room))[0]
        (outsider,) = await MemberRepo(session).list(ids.other_room)
        outsider_user = outsider.telegram_user_id
        other_turn = await TaskService(session).assign_next(other_bread, utcnow())
        other_duty = await TaskService(session).mark_done(other_bread, outsider, utcnow())
        (item,) = await ShoppingService(session).add(
            await _room(session, ids.other_room), outsider, "мыло", utcnow()
        )
        await session.commit()
        other_bread_id, other_turn_id = other_bread.id, other_turn.id  # type: ignore[union-attr]
        other_duty_id, other_item = other_duty.duty.id, item.id

    actions: list[tuple[str, Any]] = [
        (f"/turns/{turn}/accept", None),
        (f"/turns/{turn}/still", None),
        (f"/turns/{turn}/decline", None),
        (f"/categories/{ids.bread}/done", {"in_turn": False}),
        ("/duties/1/vote", {"vote": "up"}),
        ("/expenses", {"amount": "1", "member_ids": [ids.anya]}),
        ("/settle", {"debtor_id": ids.anya, "creditor_id": ids.borya, "cents": 1}),
        ("/shopping", {"text": "хлеб"}),
        ("/shopping/going", None),
        ("/shopping/1/bought", None),
        ("/away", {"days": 1}),
        ("/back", None),
    ]
    for path, body in actions:
        # A stranger (and a member of another room) can't even see that the room exists.
        for user in (424242, outsider_user):
            response = await env.post(f"/rooms/{ids.room}{path}", user=user, json=body)
            assert response.status_code == 404, (path, user)
        response = await env.client.post(f"/api/rooms/{ids.room}{path}", json=body)
        assert response.status_code == 401, path

    # A member of room 1 can't reach records of room 2 through room 1's address.
    for path, body in (
        (f"/turns/{other_turn_id}/accept", None),
        (f"/categories/{other_bread_id}/done", {"in_turn": False}),
        (f"/duties/{other_duty_id}/vote", {"vote": "up"}),
    ):
        response = await env.post(f"/rooms/{ids.room}{path}", json=body)
        assert response.status_code == 404, path
    response = await env.post(f"/rooms/{ids.room}/shopping/{other_item}/bought")
    assert response.status_code == 409 and detail(response)["code"] == "err-item-gone"

    # Nothing happened in either room.
    async with env.db.session() as session:
        assert not await DutyRepo(session).list_for_room(ids.room)
        assert (
            len(await ShoppingService(session).open_items(await _room(session, ids.other_room)))
            == 1
        )
        assert (await AssignmentRepo(session).get(turn)).status == AssignmentStatus.PENDING  # type: ignore[union-attr]
        assert not [e for e in await ExpenseRepo(session).list_for_room(ids.room)]


async def _room(session: AsyncSession, room_id: int) -> Room:
    room = await RoomRepo(session).get(room_id)
    assert room is not None
    return room


async def test_disabled_category_cannot_be_marked(env: Env):
    ids = await seed(env.db)
    async with env.db.session() as session:
        category = await CategoryRepo(session).get(ids.water)
        category.is_active = False  # type: ignore[union-attr]
        await session.commit()
    response = await env.post(
        f"/rooms/{ids.room}/categories/{ids.water}/done", json={"in_turn": False}
    )
    assert response.status_code == 404 and detail(response)["code"] == "err-category-not-found"

"""Mini App: settings, categories, roommates, export — with the bot's rights."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import GetChatMember, SendDocument, SendMediaGroup, TelegramMethod
from aiogram.types import (
    ChatMemberAdministrator,
    ChatMemberLeft,
    ChatMemberMember,
    ChatMemberOwner,
    ChatMemberRestricted,
    User,
)

from bot.config import Settings
from bot.db.models import AssignmentStatus
from bot.db.repositories import CategoryRepo, QueueRepo, RoomRepo, UserRepo
from bot.i18n import I18n
from bot.notifications import Notifier
from bot.webapi.app import create_app
from tests.test_bot_flow import FakeSession
from tests.test_webapi import TOKEN, headers
from tests.test_webapi_actions import GROUP_CHAT, Env, assignment_status, detail, remind, seed

STRANGER = 424242
NEWCOMER = 5  # in the group chat, never joined the room and never started the bot


def admin(user: User) -> ChatMemberAdministrator:
    rights = dict.fromkeys(
        (
            "can_be_edited",
            "is_anonymous",
            "can_manage_chat",
            "can_delete_messages",
            "can_manage_video_chats",
            "can_restrict_members",
            "can_promote_members",
            "can_change_info",
            "can_invite_users",
            "can_post_stories",
            "can_edit_stories",
            "can_delete_stories",
            "can_send_welcome_messages",
        ),
        False,
    )
    return ChatMemberAdministrator(user=user, **rights)


class Telegram(FakeSession):
    """The group chat of room 906B: Anya created the room, Borya is a chat admin, Vika and the
    newcomer are plain members; anybody else isn't in the chat."""

    def __init__(self) -> None:
        super().__init__(forbidden_chats=set())
        self.statuses = {1: "member", 2: "administrator", 3: "member", NEWCOMER: "member"}

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[Any],
        timeout: int | None = None,  # noqa: ASYNC109 - signature defined by aiogram
    ):
        if not isinstance(method, GetChatMember):
            return await super().make_request(bot, method, timeout)
        self.requests.append(method)
        user = User(id=method.user_id, is_bot=False, first_name=f"user {method.user_id}")
        match self.statuses.get(method.user_id) if method.chat_id == GROUP_CHAT else None:
            case "creator":
                return ChatMemberOwner(user=user, is_anonymous=False)
            case "administrator":
                return admin(user)
            case "member":
                return ChatMemberMember(user=user)
            case "muted":
                return ChatMemberRestricted.model_construct(
                    status="restricted", user=user, is_member=True
                )
            case _:
                return ChatMemberLeft(user=user)


@pytest.fixture
async def env(db, tmp_path: Path) -> AsyncIterator[Env]:
    tg = Telegram()
    bot = Bot("42:TEST", session=tg, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    notifier = Notifier(bot, I18n())
    settings = Settings(bot_token=TOKEN, webapp_dist=str(tmp_path / "no-dist"))  # type: ignore[arg-type]
    app = create_app(settings, db, notifier)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        yield Env(client, tg, db, notifier)


async def send(env: Env, method: str, path: str, user: int = 1, json: Any = None):
    return await env.client.request(method, f"/api{path}", json=json, headers=headers(user))


def telegram(env: Env) -> Telegram:
    assert isinstance(env.tg, Telegram)
    return env.tg


# --- settings ------------------------------------------------------------------------------


async def test_settings_screen_shows_who_may_change_it(env: Env):
    ids = await seed(env.db)
    screen = await env.get(f"/rooms/{ids.room}/settings")
    assert screen["can_manage"] is True  # Anya created the room
    assert screen["room"]["timezone"] == "Europe/Chisinau"
    assert (screen["quiet_hours"], screen["repeat_after_hours"], screen["weekly_summary"]) == (
        None,
        3,
        True,
    )
    bread = screen["categories"][0]
    assert bread == {
        "id": ids.bread,
        "name": "Хлеб",
        "emoji": "🍞",
        "kind": "bread",
        "is_active": True,
        "reminder_time": "18:00",
        "reminder_days": [0, 1, 2, 3, 4, 5, 6],
        "mode": "round_robin",
    }
    assert [(m["name"], m["is_creator"]) for m in screen["members"]] == [
        ("Аня", True),
        ("Боря", False),
        ("Вика", False),
    ]
    options = screen["options"]
    assert "Europe/Bucharest" in options["timezones"] and "EUR" in options["currencies"]
    assert {"start": "23:00", "end": "08:00"} in options["quiet_hours"]
    assert options["languages"] == ["ru", "ro", "en"]

    assert (await env.get(f"/rooms/{ids.room}/settings", user=2))["can_manage"] is True  # admin
    assert (await env.get(f"/rooms/{ids.room}/settings", user=3))["can_manage"] is False


async def test_only_admins_and_the_creator_change_settings(env: Env):
    ids = await seed(env.db)
    path = f"/rooms/{ids.room}/settings"
    response = await send(env, "PATCH", path, user=3, json={"currency": "EUR"})
    assert response.status_code == 403
    assert detail(response) == {
        "code": "err-not-admin",
        "message": "Настройки могут менять только админы чата и создатель комнаты.",
    }

    change = {
        "timezone": "Europe/Bucharest",
        "quiet_hours": {"start": "23:00", "end": "07:30"},
        "repeat_after_hours": 2,
        "currency": "eur",
        "weekly_summary": False,
    }
    response = await send(env, "PATCH", path, user=2, json=change)
    assert response.status_code == 200 and response.json() == {"message": "Сохранено ✅"}
    screen = await env.get(path, user=3)
    assert (screen["room"]["timezone"], screen["room"]["currency"]) == ("Europe/Bucharest", "EUR")
    assert screen["quiet_hours"] == {"start": "23:00", "end": "07:30"}
    assert (screen["repeat_after_hours"], screen["weekly_summary"]) == (2, False)

    # Only what is sent changes; null switches the quiet hours off.
    await send(env, "PATCH", path, json={"quiet_hours": None})
    screen = await env.get(path)
    assert screen["quiet_hours"] is None and screen["room"]["currency"] == "EUR"

    # Borya is no longer an admin: Telegram is asked again for every change.
    telegram(env).statuses[2] = "member"
    response = await send(env, "PATCH", path, user=2, json={"currency": "MDL"})
    assert response.status_code == 403 and detail(response)["code"] == "err-not-admin"


async def test_bad_settings_are_explained(env: Env):
    ids = await seed(env.db)
    path = f"/rooms/{ids.room}/settings"
    for body, code in (
        ({"timezone": "Mars/Olympus"}, "err-bad-timezone"),
        ({"quiet_hours": {"start": "23:00", "end": "23:00"}}, "err-bad-time-range"),
    ):
        response = await send(env, "PATCH", path, json=body)
        assert response.status_code == 422 and detail(response)["code"] == code, body
    for body in (
        {"repeat_after_hours": 25},
        {"currency": "12"},
        {"language": "de"},
        {"quiet_hours": {"start": "25:00", "end": "08:00"}},
    ):
        response = await send(env, "PATCH", path, json=body)
        assert response.status_code == 422, body
    assert (await env.get(path))["room"]["timezone"] == "Europe/Chisinau"


async def test_language_switch_translates_default_categories(env: Env):
    ids = await seed(env.db)
    response = await send(env, "PATCH", f"/rooms/{ids.room}/settings", json={"language": "en"})
    assert response.json() == {"message": "Saved ✅"}
    screen = await env.get(f"/rooms/{ids.room}/settings")
    assert screen["room"]["language"] == "en"
    assert [c["name"] for c in screen["categories"]] == ["Bread", "Water", "Trash"]
    response = await send(env, "PATCH", f"/rooms/{ids.room}/settings", user=3, json={})
    message = detail(response)["message"]
    assert message == "Only chat admins and the room creator can change settings."


# --- categories ----------------------------------------------------------------------------


async def test_any_roommate_adds_a_category(env: Env):
    ids = await seed(env.db)
    path = f"/rooms/{ids.room}/categories"
    response = await env.post(path, user=3, json={"name": "Туалетная  бумага", "emoji": "🧻"})
    assert response.json() == {
        "message": "✅ Категория 🧻 Туалетная бумага добавлена! Напоминание в 18:00, каждый день."
    }
    queue = await env.get(f"/rooms/{ids.room}/queue")
    paper = queue["categories"][-1]
    assert (paper["name"], paper["current"]["name"]) == ("Туалетная бумага", "Аня")

    for body, status, code in (
        ({"name": "туалетная бумага"}, 409, "err-category-exists"),
        ({"name": "Губки", "emoji": "abc"}, 422, "err-category-emoji"),
        ({"name": "   "}, 422, "err-category-name"),
        ({"name": "x" * 40}, 422, "err-category-name"),
    ):
        response = await env.post(path, json=body)
        assert response.status_code == status and detail(response)["code"] == code, body


async def test_admins_configure_and_delete_categories(env: Env):
    ids = await seed(env.db)
    path = f"/rooms/{ids.room}/categories/{ids.water}"

    response = await send(env, "PATCH", path, user=3, json={"reminder_time": "09:00"})
    assert response.status_code == 403 and detail(response)["code"] == "err-not-admin"
    response = await send(env, "DELETE", path, user=3)
    assert response.status_code == 403

    async with env.db.session() as session:
        state = await QueueRepo(session).get(ids.water, ids.borya)
        assert state is not None
        state.skip_debt = 1
        await session.commit()
    change = {
        "name": "Питьевая вода",
        "emoji": "🚰",
        "reminder_time": "07:45:30",
        "reminder_days": [4, 0, 2],
        "mode": "fair",
    }
    response = await send(env, "PATCH", path, user=2, json=change)
    assert response.json() == {"message": "Сохранено ✅"}
    water = (await env.get(f"/rooms/{ids.room}/settings"))["categories"][1]
    assert water == {
        "id": ids.water,
        "name": "Питьевая вода",
        "emoji": "🚰",
        "kind": "water",
        "is_active": True,
        "reminder_time": "07:45",
        "reminder_days": [0, 2, 4],
        "mode": "fair",
    }
    queue = await env.get(f"/rooms/{ids.room}/queue")
    assert next(c for c in queue["categories"] if c["id"] == ids.water)["marks"] == []  # reset

    for body, code in (
        ({"reminder_days": []}, "err-no-days"),
        ({"name": "Хлеб"}, "err-category-exists"),
        ({"emoji": "ok"}, "err-category-emoji"),
    ):
        response = await send(env, "PATCH", path, json=body)
        assert detail(response)["code"] == code, body
    for body in ({"reminder_days": [7]}, {"reminder_time": "18:00+02:00"}, {"mode": "random"}):
        assert (await send(env, "PATCH", path, json=body)).status_code == 422, body

    # Disabling cancels the issued turn, like the bot's settings.
    turn = await remind(env, ids.bread)
    bread = f"/rooms/{ids.room}/categories/{ids.bread}"
    await send(env, "PATCH", bread, json={"is_active": False})
    assert await assignment_status(env.db, turn) == AssignmentStatus.CANCELLED
    queue = await env.get(f"/rooms/{ids.room}/queue")
    assert ids.bread not in [c["id"] for c in queue["categories"]]
    await send(env, "PATCH", bread, json={"is_active": True})

    response = await send(env, "DELETE", path)
    assert response.json() == {"message": "Категория 🚰 Питьевая вода удалена"}
    async with env.db.session() as session:
        assert await CategoryRepo(session).get(ids.water) is None
    response = await send(env, "DELETE", path)
    assert response.status_code == 404 and detail(response)["code"] == "err-category-not-found"


# --- roommates -----------------------------------------------------------------------------


async def test_admins_remove_roommates(env: Env):
    ids = await seed(env.db)
    path = f"/rooms/{ids.room}/members/{ids.borya}/remove"
    response = await env.post(path, user=3)
    assert response.status_code == 403 and detail(response)["code"] == "err-not-admin"

    response = await env.post(path)
    assert response.json() == {"message": "🚪 Боря больше не в комнате. Очереди обновлены."}
    assert "<b>Боря</b> больше не живёт в комнате" in env.group()[-1].text
    members = (await env.get(f"/rooms/{ids.room}/settings"))["members"]
    assert [m["name"] for m in members] == ["Аня", "Вика"]
    response = await env.client.get(f"/api/rooms/{ids.room}/queue", headers=headers(2))
    assert response.status_code == 404

    response = await env.post(path)
    assert response.status_code == 404  # not a roommate any more


async def test_leave_and_join_again(env: Env):
    ids = await seed(env.db)
    response = await env.post(f"/rooms/{ids.room}/leave", user=3)
    assert response.json() == {"message": "👋 Ты больше не живёшь в «906B». История сохранится."}
    assert "<b>Вика</b> больше не живёт в комнате" in env.group()[-1].text
    me = await env.get("/me", user=3)
    assert me["rooms"] == [] and me["invite"] is None

    # The bot's button opened the app on this room: Vika is in the chat, so she may join.
    me = await env.get(f"/me?room={ids.room}", user=3)
    assert me["invite"]["id"] == ids.room and me["initial_room_id"] is None
    vika = headers(3, first_name="Вика")  # her profile is refreshed from initData
    response = await env.client.post(f"/api/rooms/{ids.room}/join", headers=vika)
    assert response.json() == {"message": "Добро пожаловать! 🎉"}
    assert "🎉 <b>Вика</b> теперь в комнате!" in env.group()[-1].text
    me = await env.get(f"/me?room={ids.room}", user=3)
    assert me["invite"] is None and me["initial_room_id"] == ids.room
    response = await env.client.post(f"/api/rooms/{ids.room}/join", headers=vika)
    assert response.json() == {"message": "Ты уже в этой комнате 🙂"}


async def test_newcomer_joins_from_the_app(env: Env):
    ids = await seed(env.db)
    me = await env.get(f"/me?room={ids.room}", user=NEWCOMER)
    assert me["rooms"] == [] and me["invite"]["name"] == "906B"
    grisha = {**headers(NEWCOMER, first_name="Гриша"), "Idempotency-Key": "join-key-0001"}
    response = await env.client.post(f"/api/rooms/{ids.room}/join", headers=grisha)
    assert response.json() == {"message": "Добро пожаловать! 🎉"}
    welcome = env.group()[-1]
    assert "🎉 <b>Гриша</b> теперь в комнате!" in welcome.text
    assert "открой меня в личке" in welcome.text  # the bot can't write to them yet
    assert welcome.reply_markup.inline_keyboard[0][0].url == (
        "https://t.me/roommate_test_bot?start=dm"
    )
    again = await env.client.post(f"/api/rooms/{ids.room}/join", headers=grisha)
    assert again.headers["idempotent-replayed"] == "true"
    assert sum("теперь в комнате" in m.text for m in env.group()) == 1

    async with env.db.session() as session:
        user = await UserRepo(session).get(NEWCOMER)
        assert user is not None and user.dm_available is False
    queue = await env.get(f"/rooms/{ids.room}/queue", user=NEWCOMER)
    assert len(queue["members"]) == 4


async def test_strangers_cannot_join_or_see_the_room(env: Env):
    ids = await seed(env.db)
    me = await env.get(f"/me?room={ids.room}", user=STRANGER)
    assert me["invite"] is None
    response = await env.post(f"/rooms/{ids.room}/join", user=STRANGER)
    assert response.status_code == 404
    me = await env.get("/me?room=999", user=NEWCOMER)
    assert me["invite"] is None
    assert (await env.post("/rooms/999/join", user=NEWCOMER)).status_code == 404

    # A muted chat member is still in the chat; somebody who was in another room is not.
    telegram(env).statuses[STRANGER] = "muted"
    assert (await env.get(f"/me?room={ids.room}", user=STRANGER))["invite"]["id"] == ids.room

    async with env.db.session() as session:
        room = await RoomRepo(session).get(ids.room)
        assert room is not None
        room.is_active = False  # the bot was removed from the group
        await session.commit()
    assert (await env.post(f"/rooms/{ids.room}/join", user=NEWCOMER)).status_code == 404


# --- export and rooms ----------------------------------------------------------------------


async def test_export_goes_to_private_chat(env: Env):
    ids = await seed(env.db)
    response = await env.post(f"/rooms/{ids.room}/export", user=3)
    assert response.json() == {"message": "📦 Отправил CSV-файлы тебе в личку."}
    assert "Экспорт «906B»" in env.tg.sent(3)[-1].text
    (album,) = env.tg.of(SendMediaGroup)
    assert album.chat_id == 3
    names = [media.media.filename for media in album.media]
    assert names == ["01_Хлеб.csv", "02_Вода.csv", "03_Мусор.csv", "траты.csv"]
    assert not env.tg.of(SendDocument)

    env.tg.forbidden_chats.add(2)  # Borya blocked the bot
    response = await env.post(f"/rooms/{ids.room}/export", user=2)
    assert response.status_code == 409 and detail(response)["code"] == "err-dm-needed"


async def test_switching_rooms_sets_the_bots_active_room(env: Env):
    ids = await seed(env.db)
    response = await env.post("/me/room", json={"room_id": ids.room})
    assert response.json() == {"message": "✅ Активная комната: 906B"}
    async with env.db.session() as session:
        user = await UserRepo(session).get(1)
        assert user is not None and user.active_room_id == ids.room
    assert (await env.post("/me/room", json={"room_id": ids.other_room})).status_code == 404
    response = await env.post("/me/room", user=STRANGER, json={"room_id": ids.room})
    assert response.status_code == 404
    assert (await env.client.post("/api/me/room", json={"room_id": ids.room})).status_code == 401


async def test_strangers_and_other_rooms_are_refused(env: Env):
    ids = await seed(env.db)
    async with env.db.session() as session:
        other_category = (await CategoryRepo(session).list(ids.other_room))[0].id
    requests: list[tuple[str, str, Any]] = [
        ("GET", "/settings", None),
        ("PATCH", "/settings", {"currency": "EUR"}),
        ("POST", "/categories", {"name": "Губки"}),
        ("PATCH", f"/categories/{ids.bread}", {"is_active": False}),
        ("DELETE", f"/categories/{ids.bread}", None),
        ("POST", f"/members/{ids.borya}/remove", None),
        ("POST", "/leave", None),
        ("POST", "/export", None),
    ]
    other_member = 20021  # the only roommate of the other room
    for method, path, body in requests:
        for user in (STRANGER, other_member):
            response = await send(env, method, f"/rooms/{ids.room}{path}", user=user, json=body)
            assert response.status_code == 404, (method, path, user)
        response = await env.client.request(method, f"/api/rooms/{ids.room}{path}", json=body)
        assert response.status_code == 401, (method, path)

    # Records of room 2 through room 1's address.
    response = await send(env, "PATCH", f"/rooms/{ids.room}/categories/{other_category}", json={})
    assert response.status_code == 404
    response = await send(env, "DELETE", f"/rooms/{ids.room}/categories/{other_category}")
    assert response.status_code == 404
    response = await env.post(f"/rooms/{ids.room}/members/{ids.borya + 100}/remove")
    assert response.status_code == 404

    screen = await env.get(f"/rooms/{ids.room}/settings")
    assert len(screen["members"]) == 3 and len(screen["categories"]) == 3
    assert screen["room"]["currency"] == "MDL"

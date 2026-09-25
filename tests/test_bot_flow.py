"""End-to-end flow through the real dispatcher with a fake Telegram API session.

No network: every Bot API call is recorded and answered by :class:`FakeSession`.
"""

from __future__ import annotations

import itertools
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import (
    AnswerCallbackQuery,
    DeleteMessage,
    EditMessageReplyMarkup,
    EditMessageText,
    GetChatMember,
    GetMe,
    SendMessage,
    SetMyCommands,
    TelegramMethod,
)
from aiogram.types import (
    CallbackQuery,
    Chat,
    ChatMemberMember,
    ChatMemberOwner,
    InlineKeyboardMarkup,
    Message,
    Update,
    User,
)

from bot.config import Settings
from bot.db import Database
from bot.db.models import AssignmentStatus
from bot.db.repositories import AssignmentRepo, CategoryRepo, QueueRepo, RoomRepo
from bot.i18n import I18n
from bot.keyboards.callbacks import HistoryCb, JoinCb, SettingsCb, TurnCb
from bot.main import build_dispatcher
from bot.notifications import Notifier
from bot.scheduler import jobs
from bot.services.clock import local_now, utcnow

GROUP = Chat(id=-100500, type="supergroup", title="Комната 906B")
ANYA = User(id=1, is_bot=False, first_name="Аня", language_code="ru")
BORYA = User(id=2, is_bot=False, first_name="Боря", language_code="ru")
BOT_USER = User(id=42, is_bot=True, first_name="RoomMate", username="roommate_test_bot")


class FakeSession(BaseSession):
    def __init__(self, forbidden_chats: set[int]) -> None:
        super().__init__()
        self.requests: list[TelegramMethod[Any]] = []
        self.forbidden_chats = forbidden_chats
        self.ids = itertools.count(1000)

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[Any],
        timeout: int | None = None,  # noqa: ASYNC109 - signature defined by aiogram
    ):
        self.requests.append(method)
        now = datetime.now(UTC)
        match method:
            case GetMe():
                return BOT_USER
            case SendMessage():
                if method.chat_id in self.forbidden_chats:
                    raise TelegramForbiddenError(method=method, message="Forbidden")
                chat = (
                    GROUP if method.chat_id == GROUP.id else Chat(id=method.chat_id, type="private")
                )
                return Message(
                    message_id=next(self.ids),
                    date=now,
                    chat=chat,
                    text=method.text,
                    reply_markup=method.reply_markup
                    if isinstance(method.reply_markup, InlineKeyboardMarkup)
                    else None,
                )
            case EditMessageText():
                return True
            case GetChatMember():
                if method.user_id == ANYA.id:
                    return ChatMemberOwner(user=ANYA, is_anonymous=False)
                return ChatMemberMember(user=BORYA)
            case (
                AnswerCallbackQuery() | SetMyCommands() | EditMessageReplyMarkup() | DeleteMessage()
            ):
                return True
        raise AssertionError(f"Unexpected API call: {type(method).__name__}")

    async def close(self) -> None:
        pass

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:
        yield b""

    # --- helpers for assertions --------------------------------------------------------

    def sent(self, chat_id: int | None = None) -> list[SendMessage]:
        return [
            r
            for r in self.requests
            if isinstance(r, SendMessage) and (chat_id is None or r.chat_id == chat_id)
        ]

    def of(self, kind: type) -> list[Any]:
        return [r for r in self.requests if isinstance(r, kind)]


class Harness:
    def __init__(self, db: Database) -> None:
        self.session = FakeSession(forbidden_chats={BORYA.id})
        self.bot = Bot(
            "42:TEST",
            session=self.session,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.db = db
        self.i18n = I18n()
        self.notifier = Notifier(self.bot, self.i18n)
        settings = Settings(bot_token="42:TEST", admin_ids=[])  # type: ignore[arg-type]
        self.dp = build_dispatcher(settings, db, self.i18n, self.notifier)
        self.update_ids = itertools.count(1)
        self.message_ids = itertools.count(1)

    async def message(self, user: User, text: str, chat: Chat = GROUP, **extra: Any) -> None:
        msg = Message(
            message_id=next(self.message_ids),
            date=datetime.now(UTC),
            chat=chat,
            from_user=user,
            text=text,
            **extra,
        )
        await self.dp.feed_update(self.bot, Update(update_id=next(self.update_ids), message=msg))

    async def press(self, user: User, data: str, chat: Chat = GROUP) -> None:
        msg = Message(
            message_id=next(self.message_ids), date=datetime.now(UTC), chat=chat, text="…"
        )
        query = CallbackQuery(
            id=str(next(self.update_ids)),
            from_user=user,
            chat_instance="ci",
            data=data,
            message=msg,
        )
        await self.dp.feed_update(
            self.bot, Update(update_id=next(self.update_ids), callback_query=query)
        )

    def alerts(self) -> list[str]:
        return [r.text for r in self.session.of(AnswerCallbackQuery) if r.show_alert]


@pytest.fixture
async def harness(db: Database) -> AsyncGenerator[Harness, None]:
    harness = Harness(db)
    yield harness
    # Handler routers are module-level singletons: detach them so the next test can
    # build a fresh dispatcher.
    for root in harness.dp.sub_routers:
        for router in root.sub_routers:
            router._parent_router = None


def private(user: User) -> Chat:
    return Chat(id=user.id, type="private")


async def local_time_tomorrow(db: Database, hour: int) -> datetime:
    """Tomorrow at ``hour``:00 in the room's timezone, as UTC."""
    async with db.session() as session:
        room = await RoomRepo(session).get_by_chat_id(GROUP.id)
        assert room is not None
        local = local_now(room.timezone, utcnow() + timedelta(days=1))
    return local.replace(hour=hour, minute=0, second=0, microsecond=0).astimezone(UTC)


async def test_full_stage_one_flow(harness: Harness, db: Database, monkeypatch):
    h = harness

    # /start in the group creates the room and offers the join button.
    await h.message(ANYA, "/start")
    welcome = h.session.sent(GROUP.id)[-1]
    assert "RoomMate Bot" in welcome.text
    assert welcome.reply_markup.inline_keyboard[0][0].callback_data == JoinCb().pack()

    # Anya opens the bot in private chat, both roommates join.
    await h.message(ANYA, "/start", chat=private(ANYA))
    assert "Привет, <b>Аня</b>" in h.session.sent(ANYA.id)[-1].text
    await h.press(ANYA, JoinCb().pack())
    await h.press(BORYA, JoinCb().pack())
    joined = h.session.sent(GROUP.id)[-1].text
    assert "Боря" in joined and "Start" in joined  # Borya hasn't opened the bot yet

    # /queue shows Anya first.
    await h.message(BORYA, "/queue")
    queue_text = h.session.sent(GROUP.id)[-1].text
    assert "👉 Сейчас: <b>Аня</b>" in queue_text and "Дальше: Боря" in queue_text

    # The scheduler fires tomorrow at 18:00 local time.
    fake_now = await local_time_tomorrow(db, 18)
    monkeypatch.setattr(jobs, "utcnow", lambda: fake_now)
    await jobs.reminder_tick(db, h.notifier)

    reminders = h.session.sent(ANYA.id)[-2:]
    assert {r.text.splitlines()[0] for r in reminders} == {
        "🍞 Сегодня твоя очередь купить хлеб",
        "💧 Сегодня твоя очередь купить воду",
    }
    bread_reminder = next(r for r in reminders if "хлеб" in r.text)
    accept_data = bread_reminder.reply_markup.inline_keyboard[0][0].callback_data
    turn = TurnCb.unpack(accept_data)

    # Borya can't press Anya's buttons.
    await h.press(BORYA, accept_data, chat=private(ANYA))
    assert h.alerts()[-1] == "Это не твоя очередь 🙂"

    # Anya: "I'll buy" -> "Done": the group is told and the queue moves on.
    await h.press(ANYA, accept_data, chat=private(ANYA))
    await h.press(
        ANYA, TurnCb(action="done", assignment_id=turn.assignment_id).pack(), chat=private(ANYA)
    )
    announcement = h.session.sent(GROUP.id)[-1].text
    assert "🍞 Хлеб — готово! Спасибо, <b>Аня</b>" in announcement
    assert "Следующая очередь: <b>Боря</b>" in announcement
    async with db.session() as session:
        assignment = await AssignmentRepo(session).get(turn.assignment_id)
        assert assignment is not None and assignment.status == AssignmentStatus.DONE

    # History: one table per category.
    await h.message(BORYA, "/history")
    await h.press(BORYA, HistoryCb(category_id=0).pack())
    history = h.session.of(EditMessageText)[-1].text
    assert all(title in history for title in ("🍞 Хлеб", "💧 Вода", "🗑 Мусор"))
    assert "<pre>" in history and "Аня" in history and "✅ сделано" in history

    # /done out of turn by Borya for water covers Anya's pending water reminder.
    await h.message(BORYA, "/done вода")
    done_text = h.session.sent(GROUP.id)[-1].text
    assert "вне очереди" in done_text

    # Settings: Borya is not an admin, Anya created the room.
    await h.message(BORYA, "/settings")
    assert "только админы" in h.session.sent(GROUP.id)[-1].text
    await h.message(ANYA, "/settings")
    assert "Настройки" in h.session.sent(GROUP.id)[-1].text

    # /add_category with a guided dialog (ForceReply answers).
    await h.message(BORYA, "/add_category")
    assert h.session.sent(GROUP.id)[-1].reply_markup.force_reply
    await h.message(BORYA, "Соль")
    await h.message(BORYA, "🧂")
    assert "🧂 Соль" in h.session.sent(GROUP.id)[-1].text
    await h.message(BORYA, "/add_category 🧻 Туалетная бумага")
    async with db.session() as session:
        room = await RoomRepo(session).get_by_chat_id(GROUP.id)
        names = [c.title for c in await CategoryRepo(session).list(room.id)]  # type: ignore[union-attr]
    assert names == ["🍞 Хлеб", "💧 Вода", "🗑 Мусор", "🧂 Соль", "🧻 Туалетная бумага"]

    # Nothing crashed along the way.
    assert "Что-то пошло не так" not in " ".join(h.alerts())
    assert not [r for r in h.session.sent() if "Что-то пошло не так" in r.text]


async def test_reminder_for_member_without_dm_goes_to_group(harness: Harness, db, monkeypatch):
    h = harness
    await h.message(BORYA, "/start")
    await h.press(BORYA, JoinCb().pack())
    fake_now = await local_time_tomorrow(db, 20)
    monkeypatch.setattr(jobs, "utcnow", lambda: fake_now)
    await jobs.reminder_tick(db, h.notifier)

    fallbacks = [r.text for r in h.session.sent(GROUP.id) if "tg://user?id=2" in r.text]
    assert len(fallbacks) == 3  # bread, water and trash are all due at 20:00
    assert any("вынести мусор" in text and "Start" in text for text in fallbacks)


async def test_commands_menu_is_registered(harness: Harness):
    from bot.commands import set_bot_commands

    await set_bot_commands(harness.bot, harness.i18n)
    menus = harness.session.of(SetMyCommands)
    assert {m.language_code for m in menus} == {None, "ru", "ro"}
    assert all(c.description for m in menus for c in m.commands)


async def test_stage_two_flow(harness: Harness, db: Database):
    h = harness
    await h.message(ANYA, "/start")
    await h.press(ANYA, JoinCb().pack())
    await h.press(BORYA, JoinCb().pack())

    # /done in the group: the announcement carries 👍 / 🤨.
    await h.message(ANYA, "/done хлеб")
    announcement = h.session.sent(GROUP.id)[-1]
    buttons = announcement.reply_markup.inline_keyboard[0]
    assert [b.text for b in buttons] == ["👍", "🤨 А вот и нет"]
    down = buttons[1].callback_data

    # The performer can't vote; Borya is the only other roommate, so his 🤨 decides.
    await h.press(ANYA, down)
    assert h.alerts()[-1] == "За себя голосовать нельзя 🙂"
    await h.press(BORYA, down)
    assert "Большинство против" in h.session.of(EditMessageText)[-1].text
    async with db.session() as session:
        room = await RoomRepo(session).get_by_chat_id(GROUP.id)
        category = (await CategoryRepo(session).list(room.id))[0]  # type: ignore[union-attr]
        state = await QueueRepo(session).get(category.id, 1)  # Anya's member id is 1
        assert state is not None and state.skip_debt == 1

    # /away with a preset button, then /queue shows it, then /back.
    await h.message(BORYA, "/away")
    away_buttons = h.session.sent(GROUP.id)[-1].reply_markup.inline_keyboard
    week = next(b for row in away_buttons for b in row if b.text == "Неделю")
    await h.press(ANYA, week.callback_data)
    assert h.alerts()[-1] == "Эта кнопка не для тебя 🙂"
    await h.press(BORYA, week.callback_data)
    assert "в отъезде до" in h.session.of(EditMessageText)[-1].text
    await h.message(ANYA, "/queue")
    assert "🏖 В отъезде: Боря" in h.session.sent(GROUP.id)[-1].text
    await h.message(BORYA, "/back")
    assert "снова дома" in h.session.sent(GROUP.id)[-1].text

    # Settings: repeat interval and queue mode.
    await h.message(ANYA, "/settings")
    await h.press(ANYA, SettingsCb(action="repeat").pack())
    await h.press(ANYA, SettingsCb(action="setrepeat", value="2").pack())
    assert "🔁 Повтор: через 2 ч" in h.session.of(EditMessageText)[-1].text
    await h.press(ANYA, SettingsCb(action="mode", category_id=category.id).pack())
    assert "справедливая" in h.session.of(EditMessageText)[-1].text
    await h.message(ANYA, "/queue")
    assert "⚖️ За 30 дней" in h.session.sent(GROUP.id)[-1].text

    assert not [r for r in h.session.sent() if "Что-то пошло не так" in r.text]

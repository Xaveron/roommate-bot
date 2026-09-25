"""Reminder delivery: DM first, group chat as a fallback."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import SendMessage

from bot.i18n import I18n
from bot.notifications import Notifier
from tests.conftest import at, make_room
from tests.test_services import plan


class FakeBot:
    def __init__(self, blocked: set[int]) -> None:
        self.blocked = blocked
        self.sent: list[dict[str, Any]] = []

    async def me(self):
        return SimpleNamespace(username="roommate_test_bot")

    async def send_message(self, chat_id: int, text: str, reply_markup: Any = None):
        if chat_id in self.blocked:
            raise TelegramForbiddenError(
                method=SendMessage(chat_id=chat_id, text=text),
                message="Forbidden: bot can't initiate conversation with a user",
            )
        self.sent.append({"chat_id": chat_id, "text": text, "markup": reply_markup})
        return SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=len(self.sent))

    async def edit_message_reply_markup(self, **kwargs: Any) -> None:
        return None


async def test_reminder_goes_to_private_chat(session):
    room, (anya, _, _) = await make_room(session)
    bot = FakeBot(blocked=set())
    notifier = Notifier(bot, I18n())  # type: ignore[arg-type]
    assignment, *_ = await plan(session, room, "2026-09-25 18:00")
    await notifier.deliver_reminder(assignment, at("2026-09-25 18:00"))

    (message,) = bot.sent
    assert message["chat_id"] == anya.telegram_user_id
    assert "Сегодня твоя очередь" in message["text"]
    buttons = [b.text for row in message["markup"].inline_keyboard for b in row]
    assert buttons == ["✅ Куплю", "🔄 Ещё есть", "⏭ Не могу сегодня"]
    assert anya.user.dm_available
    assert assignment.message_chat_id == anya.telegram_user_id


async def test_reminder_falls_back_to_group_when_dm_is_impossible(session):
    room, (anya, _, _) = await make_room(session)
    bot = FakeBot(blocked={anya.telegram_user_id})
    notifier = Notifier(bot, I18n())  # type: ignore[arg-type]
    assignment, *_ = await plan(session, room, "2026-09-25 18:00")
    await notifier.deliver_reminder(assignment, at("2026-09-25 18:00"))

    (message,) = bot.sent
    assert message["chat_id"] == room.chat_id
    assert f"tg://user?id={anya.telegram_user_id}" in message["text"]
    assert "Start" in message["text"]
    urls = [b.url for row in message["markup"].inline_keyboard for b in row if b.url]
    assert urls == ["https://t.me/roommate_test_bot?start=dm"]
    assert not anya.user.dm_available
    assert assignment.message_chat_id == room.chat_id


async def test_repeated_reminder_and_group_nudge(session):
    room, (anya, _, _) = await make_room(session)
    bot = FakeBot(blocked=set())
    notifier = Notifier(bot, I18n())  # type: ignore[arg-type]
    assignment, *_ = await plan(session, room, "2026-09-25 18:00")

    await notifier.deliver_reminder(assignment, at("2026-09-25 21:00"))
    assert bot.sent[-1]["text"].startswith("🔔 Напоминаю ещё раз!")
    assert assignment.reminders_sent == 2

    await notifier.nudge(assignment, at("2026-09-26 00:00"))
    nudge = bot.sent[-1]
    assert nudge["chat_id"] == room.chat_id
    assert f"tg://user?id={anya.telegram_user_id}" in nudge["text"]
    assert assignment.category.name in nudge["text"]
    assert assignment.reminders_sent == 3

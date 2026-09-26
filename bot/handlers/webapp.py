"""Opening the Mini App: /app, the /start app_<room> deep link and the menu button."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import InlineKeyboardMarkup, Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from bot.db.models import Room, User
from bot.db.repositories import MemberRepo, RoomRepo
from bot.i18n import Translator
from bot.permissions import is_in_chat
from bot.utils.text import esc

router = Router(name="webapp")

DEEP_LINK = F.args.regexp(r"^app(_\d+)?$")


def webapp_keyboard(t: Translator, webapp_url: str, room_id: int) -> InlineKeyboardMarkup:
    """web_app buttons are only allowed in private chats."""
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn-webapp"), web_app=WebAppInfo(url=f"{webapp_url}/?room={room_id}"))
    return builder.as_markup()


def open_in_private_keyboard(
    t: Translator, bot_username: str, room_id: int
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("btn-webapp-private"), url=f"https://t.me/{bot_username}?start=app_{room_id}"
    )
    return builder.as_markup()


@router.message(Command("app"), flags={"require": "room"})
async def cmd_app(
    message: Message, bot: Bot, room: Room, settings: Settings, t: Translator
) -> None:
    if not settings.webapp_url:
        await message.reply(t("webapp-not-configured"))
        return
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(
            t("webapp-open", room=esc(room.name)),
            reply_markup=webapp_keyboard(t, settings.webapp_url, room.id),
        )
        return
    username = (await bot.me()).username or ""
    await message.reply(
        t("webapp-open-private"), reply_markup=open_in_private_keyboard(t, username, room.id)
    )


@router.message(CommandStart(deep_link=True, magic=DEEP_LINK), F.chat.type == ChatType.PRIVATE)
async def start_app_deep_link(
    message: Message,
    command: CommandObject,
    bot: Bot,
    session: AsyncSession,
    user: User,
    room: Room | None,
    settings: Settings,
    t: Translator,
) -> None:
    """t.me/<bot>?start=app_<room id>: make that room active and offer the Mini App.

    Somebody from the room's group chat who hasn't joined yet can join in the Mini App.
    """
    rooms = await MemberRepo(session).rooms_of_user(user.id)
    wanted = int(command.args.split("_")[1]) if command.args and "_" in command.args else None
    target = next((r for r in rooms if r.id == wanted), None)
    if target is None and wanted is not None and settings.webapp_url:
        other = await RoomRepo(session).get(wanted)
        if other is not None and other.is_active and await is_in_chat(bot, other, user.id):
            await message.answer(
                t("webapp-open-join", room=esc(other.name)),
                reply_markup=webapp_keyboard(t, settings.webapp_url, other.id),
            )
            return
    target = target or room
    if target is None:
        await message.answer(t("err-no-room-private"))
        return
    user.active_room_id = target.id
    if not settings.webapp_url:
        await message.answer(t("webapp-not-configured"))
        return
    await message.answer(
        t("webapp-open", room=esc(target.name)),
        reply_markup=webapp_keyboard(t, settings.webapp_url, target.id),
    )

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Chat, Message, TelegramObject
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.locks import lock_room, refreshed
from bot.db.models import Room, User
from bot.db.repositories import MemberRepo, RoomRepo, UserRepo
from bot.i18n import Translator
from bot.keyboards.common import join_keyboard

GROUP_TYPES = (ChatType.GROUP, ChatType.SUPERGROUP)


class RoomContextMiddleware(BaseMiddleware):
    """Registers the Telegram user and resolves the current room and membership.

    * in a group chat the room is bound to the chat;
    * in private chat it's the user's active room (or their only room).

    Puts ``user``, ``room`` and ``member`` (possibly None) into handler data.

    In a group chat the room's lock (see ``bot.db.locks``) is taken before anything is read
    or written, so the update never interleaves with the Mini App working on the same room.
    In private chat the services take the lock of the room they change.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session: AsyncSession = data["session"]
        tg_user: TgUser | None = data.get("event_from_user")
        chat: Chat | None = data.get("event_chat")
        user = room = member = None
        in_group = chat is not None and chat.type in GROUP_TYPES

        if in_group:
            room = await RoomRepo(session).get_by_chat_id(chat.id)  # type: ignore[union-attr]
            if room is not None:
                await lock_room(session, room.id)
                await refreshed(session, room)

        if tg_user is not None and not tg_user.is_bot:
            user = await UserRepo(session).upsert(
                user_id=tg_user.id,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                username=tg_user.username,
                language_code=tg_user.language_code,
            )
            if chat is not None and chat.type == ChatType.PRIVATE:
                user.dm_available = True

        if not in_group and user is not None:
            room = await resolve_private_room(session, user)

        if room is not None and user is not None:
            member = await MemberRepo(session).get_by_user(room.id, user.id)
            if member is not None and not member.is_active:
                member = None

        data.update(user=user, room=room, member=member)
        return await handler(event, data)


async def resolve_private_room(session: AsyncSession, user: User) -> Room | None:
    rooms = await MemberRepo(session).rooms_of_user(user.id)
    if not rooms:
        return None
    for room in rooms:
        if room.id == user.active_room_id:
            return room
    return rooms[0]


class RequirementsMiddleware(BaseMiddleware):
    """Checks the ``require`` flag of a handler: "room" or "member".

    Answers with a friendly explanation instead of silently ignoring the update.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        requirement = get_flag(data, "require")
        if requirement is None:
            return await handler(event, data)

        t: Translator = data["t"]
        room: Room | None = data.get("room")
        chat: Chat | None = data.get("event_chat")
        in_group = chat is not None and chat.type in GROUP_TYPES

        if room is None:
            key = "err-no-room-group" if in_group else "err-no-room-private"
            await _reply(event, t(key))
            return None
        if requirement == "member" and data.get("member") is None:
            if in_group:
                bot_username = (await data["bot"].me()).username
                await _reply(event, t("err-not-member"), join_keyboard(t, bot_username or ""))
            else:
                await _reply(event, t("err-no-room-private"))
            return None
        return await handler(event, data)


async def _reply(event: TelegramObject, text: str, markup: Any = None) -> None:
    if isinstance(event, Message):
        await event.reply(text, reply_markup=markup)
    elif isinstance(event, CallbackQuery):
        await event.answer(text, show_alert=True)

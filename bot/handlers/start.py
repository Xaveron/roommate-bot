"""Room lifecycle: /start, joining and leaving, members, help."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters import (
    IS_MEMBER,
    IS_NOT_MEMBER,
    ChatMemberUpdatedFilter,
    Command,
    CommandStart,
)
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.announcements import announce_join, leave_text
from bot.config import Settings
from bot.db.models import Member, Room, User
from bot.db.repositories import MemberRepo
from bot.handlers.common import is_group
from bot.i18n import I18n, Translator, default_category_names
from bot.keyboards.callbacks import JoinCb, LeaveCb, RoomPickCb
from bot.keyboards.common import join_keyboard, leave_confirm_keyboard, room_picker
from bot.notifications import Notifier
from bot.services.clock import utcnow
from bot.services.rooms import RoomService
from bot.utils.text import bold, esc

logger = logging.getLogger(__name__)
router = Router(name="start")

GROUP_CHATS = F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP})
PRIVATE_CHAT = F.chat.type == ChatType.PRIVATE


async def _ensure_room(
    session: AsyncSession,
    *,
    chat_id: int,
    title: str,
    user: User | None,
    i18n: I18n,
    settings: Settings,
) -> tuple[Room, bool]:
    language = i18n.resolve(user.language_code if user else None, settings.default_language)
    if language == "en":  # rooms default to the project's main languages
        language = settings.default_language
    return await RoomService(session).get_or_create(
        chat_id=chat_id,
        title=title,
        created_by=user.id if user else None,
        language=language,
        timezone=settings.default_timezone,
        default_names=default_category_names(i18n, language),
        now=utcnow(),
    )


async def _welcome(bot: Bot, room: Room, i18n: I18n, *, created: bool) -> tuple[str, object]:
    t = i18n.get(room.language)
    username = (await bot.me()).username or ""
    key = "start-group-created" if created else "start-group-existing"
    return t(key, room=esc(room.name)), join_keyboard(t, username)


@router.message(CommandStart(), GROUP_CHATS)
async def start_in_group(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    user: User | None,
    i18n: I18n,
    settings: Settings,
) -> None:
    room, created = await _ensure_room(
        session,
        chat_id=message.chat.id,
        title=message.chat.title or str(message.chat.id),
        user=user,
        i18n=i18n,
        settings=settings,
    )
    text, markup = await _welcome(bot, room, i18n, created=created)
    await message.answer(text, reply_markup=markup)  # type: ignore[arg-type]


@router.my_chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER), GROUP_CHATS)
async def bot_added_to_group(
    event: ChatMemberUpdated,
    bot: Bot,
    session: AsyncSession,
    user: User | None,
    i18n: I18n,
    settings: Settings,
) -> None:
    room, created = await _ensure_room(
        session,
        chat_id=event.chat.id,
        title=event.chat.title or str(event.chat.id),
        user=user,
        i18n=i18n,
        settings=settings,
    )
    text, markup = await _welcome(bot, room, i18n, created=created)
    await bot.send_message(event.chat.id, text, reply_markup=markup)  # type: ignore[arg-type]


@router.my_chat_member(ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER), GROUP_CHATS)
async def bot_removed_from_group(event: ChatMemberUpdated, session: AsyncSession) -> None:
    await RoomService(session).deactivate(event.chat.id)


@router.message(F.migrate_to_chat_id)
async def group_migrated(message: Message, session: AsyncSession) -> None:
    room = await RoomService(session).migrate_chat(message.chat.id, message.migrate_to_chat_id)
    if room is not None:
        logger.info("Room %s moved to chat %s", room.id, room.chat_id)


@router.message(CommandStart(), PRIVATE_CHAT)
async def start_in_private(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    user: User,
    settings: Settings,
    t: Translator,
) -> None:
    rooms = await MemberRepo(session).rooms_of_user(user.id)
    username = (await bot.me()).username or ""
    builder = InlineKeyboardBuilder()
    if rooms and settings.webapp_url:
        builder.button(text=t("btn-webapp"), web_app=WebAppInfo(url=f"{settings.webapp_url}/"))
    builder.button(text=t("btn-add-to-group"), url=f"https://t.me/{username}?startgroup=room")
    builder.adjust(1)
    if rooms:
        names = "\n".join(f"• {esc(room.name)}" for room in rooms)
        text = t("start-private-with-rooms", name=bold(user.first_name), rooms=names)
    else:
        text = t("start-private-new", name=bold(user.first_name))
    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(JoinCb.filter())
async def join_room(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User | None,
    room: Room | None,
    t: Translator,
    notifier: Notifier,
) -> None:
    if room is None or user is None or callback.message is None:
        await callback.answer(t("err-no-room-group"), show_alert=True)
        return
    member, joined = await RoomService(session).join(room, user, utcnow())
    if not joined:
        await callback.answer(t("join-already"))
        return
    await callback.answer(t("join-toast"))
    await announce_join(notifier, room, member)


@router.message(Command("leave"), GROUP_CHATS, flags={"require": "member"})
async def leave_room(message: Message, member: Member, t: Translator) -> None:
    await message.reply(
        t("leave-confirm"), reply_markup=leave_confirm_keyboard(t, member.telegram_user_id)
    )


@router.callback_query(LeaveCb.filter(), flags={"require": "member"})
async def leave_room_confirm(
    callback: CallbackQuery,
    callback_data: LeaveCb,
    session: AsyncSession,
    member: Member,
    t: Translator,
) -> None:
    if callback.from_user.id != callback_data.user_id:
        await callback.answer(t("err-not-your-button"), show_alert=True)
        return
    if not callback_data.confirm:
        await callback.answer()
        if callback.message is not None:
            await callback.message.delete()  # type: ignore[union-attr]
        return
    await RoomService(session).leave(member)
    await callback.answer()
    if callback.message is not None:
        await callback.message.edit_text(leave_text(t, member))  # type: ignore[union-attr]


@router.message(Command("members"), flags={"require": "room"})
async def list_members(message: Message, session: AsyncSession, room: Room, t: Translator) -> None:
    members = await RoomService(session).active_members(room)
    if not members:
        await message.answer(t("members-empty"))
        return
    lines = [t("members-title", room=esc(room.name), count=len(members))]
    for member in members:
        key = "members-line" if member.user.dm_available else "members-line-no-dm"
        lines.append(t(key, name=esc(member.display_name)))
    if any(not m.user.dm_available for m in members):
        lines.append("")
        lines.append(t("members-no-dm-hint"))
    await message.answer("\n".join(lines))


@router.message(Command("room"), PRIVATE_CHAT)
async def pick_room(
    message: Message, session: AsyncSession, user: User, room: Room | None, t: Translator
) -> None:
    rooms = await MemberRepo(session).rooms_of_user(user.id)
    if not rooms:
        await message.answer(t("err-no-room-private"))
        return
    await message.answer(t("room-pick"), reply_markup=room_picker(rooms, room.id if room else None))


@router.callback_query(RoomPickCb.filter())
async def room_picked(
    callback: CallbackQuery,
    callback_data: RoomPickCb,
    session: AsyncSession,
    user: User,
    t: Translator,
) -> None:
    rooms = await MemberRepo(session).rooms_of_user(user.id)
    chosen = next((r for r in rooms if r.id == callback_data.room_id), None)
    if chosen is None:
        await callback.answer(t("err-generic"), show_alert=True)
        return
    user.active_room_id = chosen.id
    await callback.answer()
    if callback.message is not None:
        await callback.message.edit_text(t("room-picked", room=esc(chosen.name)))  # type: ignore[union-attr]


@router.message(Command("help"))
async def show_help(message: Message, t: Translator) -> None:
    key = "help-group" if is_group(message.chat) else "help-private"
    await message.answer(t(key))

"""/settings menu and /add_category.

Free-text answers are requested with ForceReply: in groups with privacy mode enabled the bot
only sees replies to its own messages, so this works without extra BotFather configuration.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ForceReply, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import SUPPORTED_LANGUAGES
from bot.db.models import Category, Room
from bot.db.repositories import CategoryRepo, MemberRepo
from bot.handlers.common import ANSWER, can_manage, default_category_names
from bot.i18n import I18n, Translator
from bot.keyboards import settings as kb
from bot.keyboards.callbacks import SettingsCb
from bot.services.categories import CategoryService
from bot.services.clock import utcnow
from bot.services.errors import ServiceError
from bot.services.rooms import RoomService
from bot.utils.parsing import (
    format_time,
    parse_compact_time,
    parse_time,
    parse_time_range,
    split_emoji,
)
from bot.utils.text import bold, esc, mention

router = Router(name="settings")


class AddCategory(StatesGroup):
    name = State()
    emoji = State()


class SettingsInput(StatesGroup):
    reminder_time = State()
    quiet_hours = State()
    timezone = State()


# --- texts -------------------------------------------------------------------------------


def _days_text(t: Translator, days: str) -> str:
    if len(days) == 7:
        return t("days-every")
    return ", ".join(t("weekday-short", day=int(d)) for d in days)


def main_text(t: Translator, room: Room) -> str:
    quiet = (
        f"{format_time(room.quiet_hours_start)}–{format_time(room.quiet_hours_end)}"
        if room.quiet_hours_start is not None
        else t("quiet-off")
    )
    return t(
        "settings-main",
        room=esc(room.name),
        language=t("language-name", code=room.language),
        timezone=room.timezone,
        quiet=quiet,
        repeat=t("repeat-value", hours=room.repeat_after_hours),
    )


def category_text(t: Translator, category: Category) -> str:
    return t(
        "settings-category",
        title=esc(category.title),
        time=format_time(category.reminder_time),
        days=_days_text(t, category.reminder_days),
        state=t("category-state", active=str(category.is_active).lower()),
        mode=t("category-mode", mode=category.queue_mode),
    )


# --- entry points ------------------------------------------------------------------------


@router.message(Command("settings"), flags={"require": "room"})
async def cmd_settings(message: Message, bot: Bot, room: Room, t: Translator) -> None:
    if message.from_user is None or not await can_manage(bot, room, message.from_user.id):
        await message.reply(t("err-not-admin"))
        return
    await message.answer(main_text(t, room), reply_markup=kb.main_menu(t))


@router.message(Command("cancel"), StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext, t: Translator) -> None:
    if await state.get_state() is None:
        await message.reply(t("cancel-nothing"))
        return
    await state.clear()
    await message.reply(t("cancel-done"))


@router.message(Command("add_category"), flags={"require": "member"})
async def cmd_add_category(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    room: Room,
    state: FSMContext,
    t: Translator,
) -> None:
    if command.args:
        emoji, name = split_emoji(command.args)
        await _create_category(message, session, room, t, name=name, emoji=emoji)
        return
    await state.set_state(AddCategory.name)
    await message.reply(
        t("add-category-ask-name"),
        reply_markup=ForceReply(selective=True, input_field_placeholder=t("add-category-hint")),
    )


async def _create_category(
    message: Message,
    session: AsyncSession,
    room: Room,
    t: Translator,
    *,
    name: str,
    emoji: str | None,
) -> bool:
    try:
        category = await CategoryService(session).create(room, name=name, emoji=emoji, now=utcnow())
    except ServiceError as error:
        await message.reply(t(error.key, **error.args_))
        return False
    await message.reply(
        t(
            "add-category-done",
            title=esc(category.title),
            time=format_time(category.reminder_time),
        )
    )
    return True


@router.message(AddCategory.name, ANSWER)
async def add_category_name(
    message: Message,
    session: AsyncSession,
    room: Room | None,
    state: FSMContext,
    t: Translator,
) -> None:
    if room is None:
        await state.clear()
        return
    emoji, name = split_emoji(message.text or "")
    if emoji is not None:
        if await _create_category(message, session, room, t, name=name, emoji=emoji):
            await state.clear()
        return
    await state.update_data(name=name)
    await state.set_state(AddCategory.emoji)
    await message.reply(
        t("add-category-ask-emoji", name=esc(name)),
        reply_markup=ForceReply(selective=True, input_field_placeholder="🧻"),
    )


@router.message(AddCategory.emoji, ANSWER)
async def add_category_emoji(
    message: Message,
    session: AsyncSession,
    room: Room | None,
    state: FSMContext,
    t: Translator,
) -> None:
    data = await state.get_data()
    if room is None or "name" not in data:
        await state.clear()
        return
    raw = (message.text or "").strip()
    emoji = None if raw in {"-", "—", "0"} else raw
    if await _create_category(message, session, room, t, name=data["name"], emoji=emoji):
        await state.clear()


# --- menu navigation ---------------------------------------------------------------------


async def _show(callback: CallbackQuery, text: str, markup: Any) -> None:
    if callback.message is None:
        return
    with suppress(TelegramAPIError):  # "message is not modified"
        await callback.message.edit_text(text, reply_markup=markup)  # type: ignore[union-attr]


async def _ask(callback: CallbackQuery, state: FSMContext, new_state: State, text: str) -> None:
    """Ask for free text in the chat where the menu lives."""
    await state.set_state(new_state)
    user = callback.from_user
    if callback.message is not None:
        await callback.message.answer(  # type: ignore[union-attr]
            f"{mention(user.id, user.full_name)} 👇\n{text}",
            reply_markup=ForceReply(selective=True),
        )


@router.callback_query(SettingsCb.filter(), flags={"require": "room"})
async def on_settings(
    callback: CallbackQuery,
    callback_data: SettingsCb,
    bot: Bot,
    session: AsyncSession,
    room: Room,
    state: FSMContext,
    t: Translator,
    i18n: I18n,
) -> None:
    if not await can_manage(bot, room, callback.from_user.id):
        await callback.answer(t("err-not-admin"), show_alert=True)
        return
    categories = CategoryService(session)
    rooms = RoomService(session)
    action, value = callback_data.action, callback_data.value
    category: Category | None = None
    try:
        if callback_data.category_id:
            category = await categories.get(room, callback_data.category_id)

        match action:
            case "menu":
                await _show(callback, main_text(t, room), kb.main_menu(t))
            case "close":
                if callback.message is not None:
                    await callback.message.delete()  # type: ignore[union-attr]
            case "cats":
                await _show(
                    callback,
                    t("settings-categories"),
                    kb.categories_menu(t, await categories.list(room)),
                )
            case "cat" if category:
                await _show(callback, category_text(t, category), kb.category_menu(t, category))
            case "time" if category:
                await _show(callback, category_text(t, category), kb.time_menu(t, category))
            case "settime" if category:
                parsed = parse_compact_time(value)
                if parsed is None:
                    raise ServiceError("err-bad-time")
                await categories.set_reminder_time(category, parsed)
                await _show(callback, category_text(t, category), kb.category_menu(t, category))
            case "customtime" if category:
                await state.update_data(category_id=category.id)
                await _ask(callback, state, SettingsInput.reminder_time, t("ask-time"))
            case "days" if category:
                await _show(callback, category_text(t, category), kb.days_menu(t, category))
            case "day" if category:
                await categories.toggle_day(category, int(value))
                await _show(callback, category_text(t, category), kb.days_menu(t, category))
            case "alldays" if category:
                await categories.set_every_day(category)
                await _show(callback, category_text(t, category), kb.days_menu(t, category))
            case "mode" if category:
                await categories.toggle_queue_mode(category)
                await _show(callback, category_text(t, category), kb.category_menu(t, category))
            case "toggle" if category:
                await categories.set_active(category, not category.is_active, utcnow())
                await _show(callback, category_text(t, category), kb.category_menu(t, category))
            case "del" if category:
                await _show(
                    callback,
                    t("settings-delete-confirm", title=esc(category.title)),
                    kb.delete_confirm_menu(t, category),
                )
            case "delok" if category:
                title = category.title
                await categories.delete(category)
                await callback.answer(t("toast-category-deleted", title=title))
                await _show(
                    callback,
                    t("settings-categories"),
                    kb.categories_menu(t, await categories.list(room)),
                )
                return
            case "addcat":
                await _ask(callback, state, AddCategory.name, t("add-category-ask-name"))
            case "repeat":
                await _show(
                    callback, t("settings-repeat"), kb.repeat_menu(t, room.repeat_after_hours)
                )
            case "setrepeat":
                await rooms.set_repeat_hours(room, int(value))
                await _show(callback, main_text(t, room), kb.main_menu(t))
            case "quiet":
                await _show(callback, t("settings-quiet"), kb.quiet_menu(t))
            case "setquiet":
                if value == "off":
                    await rooms.set_quiet_hours(room, None, None)
                else:
                    start, end = parse_compact_time(value[:4]), parse_compact_time(value[4:])
                    await rooms.set_quiet_hours(room, start, end)
                await _show(callback, main_text(t, room), kb.main_menu(t))
            case "customquiet":
                await _ask(callback, state, SettingsInput.quiet_hours, t("ask-quiet"))
            case "tz":
                await _show(callback, t("settings-timezone"), kb.timezone_menu(t, room.timezone))
            case "settz":
                index = int(value)
                if not 0 <= index < len(kb.TIMEZONE_PRESETS):
                    raise ServiceError("err-bad-timezone")
                await rooms.set_timezone(room, kb.TIMEZONE_PRESETS[index])
                await _show(callback, main_text(t, room), kb.main_menu(t))
            case "customtz":
                await _ask(callback, state, SettingsInput.timezone, t("ask-timezone"))
            case "lang":
                await _show(callback, t("settings-language"), kb.language_menu(t, room.language))
            case "setlang" if value in SUPPORTED_LANGUAGES:
                await rooms.set_language(
                    room,
                    value,
                    old_names=default_category_names(i18n, room.language),
                    new_names=default_category_names(i18n, value),
                )
                t = i18n.get(value)
                await _show(callback, main_text(t, room), kb.main_menu(t))
            case "members":
                members = await MemberRepo(session).list(room.id)
                await _show(callback, t("settings-members"), kb.members_menu(t, members))
            case "rmm":
                member = await MemberRepo(session).get(int(value))
                if member is None or member.room_id != room.id or not member.is_active:
                    raise ServiceError("err-generic")
                await _show(
                    callback,
                    t("settings-remove-member-confirm", name=bold(member.display_name)),
                    kb.remove_member_confirm(t, member),
                )
            case "rmmok":
                member = await MemberRepo(session).get(int(value))
                if member is None or member.room_id != room.id:
                    raise ServiceError("err-generic")
                await rooms.leave(member)
                members = await MemberRepo(session).list(room.id)
                await _show(callback, t("settings-members"), kb.members_menu(t, members))
            case _:
                raise ServiceError("err-generic")
    except ServiceError as error:
        await callback.answer(t(error.key, **error.args_), show_alert=True)
        return
    except ValueError:
        await callback.answer(t("err-generic"), show_alert=True)
        return
    await callback.answer()


# --- free-text input ---------------------------------------------------------------------


@router.message(SettingsInput.reminder_time, ANSWER)
async def input_reminder_time(
    message: Message,
    session: AsyncSession,
    room: Room | None,
    state: FSMContext,
    t: Translator,
) -> None:
    data = await state.get_data()
    category = await CategoryRepo(session).get(data.get("category_id", 0))
    if room is None or category is None or category.room_id != room.id:
        await state.clear()
        return
    parsed = parse_time(message.text or "")
    if parsed is None:
        await message.reply(t("err-bad-time"), reply_markup=ForceReply(selective=True))
        return
    await CategoryService(session).set_reminder_time(category, parsed)
    await state.clear()
    await message.reply(category_text(t, category), reply_markup=kb.category_menu(t, category))


@router.message(SettingsInput.quiet_hours, ANSWER)
async def input_quiet_hours(
    message: Message,
    session: AsyncSession,
    room: Room | None,
    state: FSMContext,
    t: Translator,
) -> None:
    if room is None:
        await state.clear()
        return
    text = (message.text or "").strip()
    if text in {"-", "off", "0"}:
        await RoomService(session).set_quiet_hours(room, None, None)
    else:
        parsed = parse_time_range(text)
        if parsed is None:
            await message.reply(t("err-bad-time-range"), reply_markup=ForceReply(selective=True))
            return
        await RoomService(session).set_quiet_hours(room, *parsed)
    await state.clear()
    await message.reply(main_text(t, room), reply_markup=kb.main_menu(t))


@router.message(SettingsInput.timezone, ANSWER)
async def input_timezone(
    message: Message,
    session: AsyncSession,
    room: Room | None,
    state: FSMContext,
    t: Translator,
) -> None:
    if room is None:
        await state.clear()
        return
    try:
        await RoomService(session).set_timezone(room, (message.text or "").strip())
    except ServiceError as error:
        await message.reply(t(error.key, **error.args_), reply_markup=ForceReply(selective=True))
        return
    await state.clear()
    await message.reply(main_text(t, room), reply_markup=kb.main_menu(t))

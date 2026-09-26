"""/away and /back: "I'm away" mode."""

from __future__ import annotations

from contextlib import suppress
from datetime import date

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ForceReply, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.announcements import away_text, back_text
from bot.db.models import Member, Room
from bot.handlers.common import ANSWER
from bot.i18n import Translator
from bot.keyboards.callbacks import AwayCb
from bot.keyboards.common import away_keyboard, back_home_keyboard
from bot.notifications import Notifier
from bot.services.away import AwayService, is_away, until_for_days
from bot.services.clock import local_date, utcnow
from bot.services.errors import ServiceError
from bot.utils.parsing import format_date, parse_date
from bot.utils.text import mention

router = Router(name="away")


class AwayInput(StatesGroup):
    until = State()


def _today(room: Room) -> date:
    return local_date(room.timezone, utcnow())


async def _go_away(
    session: AsyncSession,
    room: Room,
    member: Member,
    until: date,
    t: Translator,
    notifier: Notifier,
    chat_id: int,
) -> str:
    """Switch the mode on; returns the text for the chat where it was requested."""
    await AwayService(session).go_away(room, member, until, utcnow())
    announcement = away_text(t, member, until)
    if chat_id == room.chat_id:
        return announcement
    await notifier.send_group(room, announcement)
    return t("away-set-private", date=format_date(until))


async def _come_back(
    session: AsyncSession,
    room: Room,
    member: Member,
    t: Translator,
    notifier: Notifier,
    chat_id: int,
) -> str:
    if not await AwayService(session).come_back(room, member, utcnow()):
        return t("back-not-away")
    announcement = back_text(t, member)
    if chat_id == room.chat_id:
        return announcement
    await notifier.send_group(room, announcement)
    return t("back-done-private")


@router.message(Command("away"), flags={"require": "member"})
async def cmd_away(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    room: Room,
    member: Member,
    t: Translator,
    notifier: Notifier,
) -> None:
    today = _today(room)
    if command.args:
        until = parse_date(command.args, today)
        if until is None:
            await message.reply(t("err-bad-date"))
            return
        try:
            text = await _go_away(session, room, member, until, t, notifier, message.chat.id)
        except ServiceError as error:
            await message.reply(t(error.key, **error.args_))
            return
        await message.reply(text)
        return
    if is_away(member, today):
        await message.reply(
            t("away-status", date=format_date(member.away_until)),  # type: ignore[arg-type]
            reply_markup=back_home_keyboard(t, member.telegram_user_id),
        )
        return
    await message.reply(t("away-ask"), reply_markup=away_keyboard(t, member.telegram_user_id))


@router.message(Command("back"), flags={"require": "member"})
async def cmd_back(
    message: Message,
    session: AsyncSession,
    room: Room,
    member: Member,
    t: Translator,
    notifier: Notifier,
) -> None:
    await message.reply(await _come_back(session, room, member, t, notifier, message.chat.id))


@router.callback_query(AwayCb.filter(), flags={"require": "member"})
async def on_away_button(
    callback: CallbackQuery,
    callback_data: AwayCb,
    session: AsyncSession,
    room: Room,
    member: Member,
    state: FSMContext,
    t: Translator,
    notifier: Notifier,
) -> None:
    if callback.from_user.id != callback_data.user_id:
        await callback.answer(t("err-not-your-button"), show_alert=True)
        return
    message = callback.message if isinstance(callback.message, Message) else None
    chat_id = message.chat.id if message else room.chat_id

    if callback_data.action == "custom":
        await state.set_state(AwayInput.until)
        await callback.answer()
        if message is not None:
            user = callback.from_user
            await message.answer(
                f"{mention(user.id, user.full_name)} 👇\n{t('ask-away-date')}",
                reply_markup=ForceReply(selective=True, input_field_placeholder="15.10"),
            )
        return

    try:
        if callback_data.action == "days" and 1 <= callback_data.value <= 366:
            until = until_for_days(_today(room), callback_data.value)
            text = await _go_away(session, room, member, until, t, notifier, chat_id)
        elif callback_data.action == "back":
            text = await _come_back(session, room, member, t, notifier, chat_id)
        else:
            raise ServiceError("err-generic")
    except ServiceError as error:
        await callback.answer(t(error.key, **error.args_), show_alert=True)
        return
    await callback.answer()
    if message is not None:
        with suppress(TelegramAPIError):
            await message.edit_text(text)


@router.message(AwayInput.until, ANSWER)
async def input_away_date(
    message: Message,
    session: AsyncSession,
    room: Room | None,
    member: Member | None,
    state: FSMContext,
    t: Translator,
    notifier: Notifier,
) -> None:
    if room is None or member is None:
        await state.clear()
        return
    until = parse_date(message.text or "", _today(room))
    if until is None:
        await message.reply(t("err-bad-date"), reply_markup=ForceReply(selective=True))
        return
    try:
        text = await _go_away(session, room, member, until, t, notifier, message.chat.id)
    except ServiceError as error:
        await message.reply(t(error.key, **error.args_), reply_markup=ForceReply(selective=True))
        return
    await state.clear()
    await message.reply(text)

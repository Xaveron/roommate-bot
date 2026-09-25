"""Reminder buttons (I'll buy / Done / Still have / Can't today) and /done."""

from __future__ import annotations

from contextlib import suppress

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Category, Member, Room
from bot.db.repositories import AssignmentRepo
from bot.handlers.common import completion_markup, completion_text, name_of
from bot.i18n import I18n, Translator
from bot.keyboards.callbacks import DoneCb, TurnCb
from bot.keyboards.common import done_picker, turn_keyboard
from bot.notifications import Notifier, reminder_text
from bot.services.categories import CategoryService
from bot.services.clock import utcnow
from bot.services.errors import ServiceError
from bot.services.reminders import room_is_quiet
from bot.services.tasks import Completion, TaskService
from bot.utils.text import bold, esc

router = Router(name="tasks")


async def _edit(callback: CallbackQuery, text: str, markup: object = None) -> None:
    if callback.message is None:
        return
    with suppress(TelegramAPIError):  # message too old or unchanged
        await callback.message.edit_text(text, reply_markup=markup)  # type: ignore[union-attr, arg-type]


@router.callback_query(TurnCb.filter())
async def on_turn_button(
    callback: CallbackQuery,
    callback_data: TurnCb,
    session: AsyncSession,
    i18n: I18n,
    notifier: Notifier,
) -> None:
    assignment = await AssignmentRepo(session).get(callback_data.assignment_id)
    room = assignment.category.room if assignment else None
    t = i18n.get(room.language if room else None)
    if assignment is None or room is None:
        await callback.answer(t("err-assignment-closed"), show_alert=True)
        return

    service = TaskService(session)
    now = utcnow()
    user_id = callback.from_user.id
    in_group = callback.message is not None and callback.message.chat.id == room.chat_id
    try:
        match callback_data.action:
            case "accept":
                await service.accept(assignment.id, user_id)
                await callback.answer(t("toast-accepted"))
                await _edit(
                    callback,
                    reminder_text(t, assignment, with_room=not in_group),
                    turn_keyboard(t, assignment),
                )
            case "done":
                completion = await service.complete(assignment.id, user_id, now)
                await callback.answer(t("toast-done"))
                await _announce_completion(callback, completion, notifier, t, in_group=in_group)
            case "still":
                await service.still_have(assignment.id, user_id, now)
                await callback.answer(t("toast-snoozed"))
                text = reminder_text(t, assignment, with_room=not in_group)
                await _edit(callback, f"{text}\n\n{t('turn-snoozed')}")
            case "decline":
                handover = await service.decline(assignment.id, user_id, now)
                await callback.answer(t("toast-declined"))
                next_assignment = handover.next_assignment
                next_member = next_assignment.member if next_assignment else None
                text = reminder_text(t, assignment, with_room=not in_group)
                await _edit(
                    callback, f"{text}\n\n{t('turn-declined', next=name_of(next_member, t))}"
                )
                key = "group-declined" if next_member else "group-declined-nobody"
                await notifier.send_group(
                    room,
                    t(
                        key,
                        name=bold(assignment.member.display_name),
                        emoji=assignment.category.emoji,
                        category=esc(assignment.category.name),
                        next=name_of(next_member, t),
                    ),
                )
                if next_assignment is not None and not room_is_quiet(room, now):
                    await notifier.deliver_reminder(next_assignment, now)
            case _:
                await callback.answer()
    except ServiceError as error:
        await callback.answer(t(error.key, **error.args_), show_alert=True)


async def _announce_completion(
    callback: CallbackQuery,
    completion: Completion,
    notifier: Notifier,
    t: Translator,
    *,
    in_group: bool,
) -> None:
    room = completion.category.room
    announcement = completion_text(t, completion)
    markup = completion_markup(t, completion)
    if in_group:
        await _edit(callback, announcement, markup)
    else:
        if completion.assignment is not None:
            text = reminder_text(t, completion.assignment)
            await _edit(callback, f"{text}\n\n{t('turn-done')}")
        await notifier.send_group(room, announcement, markup)


@router.message(Command("done"), flags={"require": "member"})
async def cmd_done(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    room: Room,
    member: Member,
    t: Translator,
    notifier: Notifier,
) -> None:
    categories = CategoryService(session)
    active = await categories.list(room, active_only=True)
    if not active:
        await message.reply(t("err-no-categories"))
        return
    if command.args:
        category = await categories.find(room, command.args)
        if category is not None:
            text, markup = await _mark_done(
                session, room, category, member, t, notifier, message.chat.id
            )
            await message.reply(text, reply_markup=markup)
            return
        await message.reply(
            t("done-not-found"), reply_markup=done_picker(t, active, member.telegram_user_id)
        )
        return
    await message.reply(
        t("done-pick"), reply_markup=done_picker(t, active, member.telegram_user_id)
    )


@router.callback_query(DoneCb.filter(), flags={"require": "member"})
async def on_done_picked(
    callback: CallbackQuery,
    callback_data: DoneCb,
    session: AsyncSession,
    room: Room,
    member: Member,
    t: Translator,
    notifier: Notifier,
) -> None:
    if callback.from_user.id != callback_data.user_id:
        await callback.answer(t("err-not-your-button"), show_alert=True)
        return
    try:
        category = await CategoryService(session).get(room, callback_data.category_id)
    except ServiceError as error:
        await callback.answer(t(error.key, **error.args_), show_alert=True)
        return
    chat_id = callback.message.chat.id if callback.message else room.chat_id
    text, markup = await _mark_done(session, room, category, member, t, notifier, chat_id)
    await callback.answer(t("toast-done"))
    await _edit(callback, text, markup)


async def _mark_done(
    session: AsyncSession,
    room: Room,
    category: Category,
    member: Member,
    t: Translator,
    notifier: Notifier,
    chat_id: int,
) -> tuple[str, InlineKeyboardMarkup | None]:
    """Record the chore; returns the text (and buttons) for the chat where it was requested."""
    completion = await TaskService(session).mark_done(category, member, utcnow())
    if completion.covered is not None:
        await notifier.close_reminder(
            completion.covered, t("turn-covered", name=bold(member.display_name))
        )
    announcement = completion_text(t, completion)
    markup = completion_markup(t, completion)
    if chat_id == room.chat_id:
        return announcement, markup
    await notifier.send_group(room, announcement, markup)
    return t("done-private-confirm", emoji=category.emoji, category=esc(category.name)), None

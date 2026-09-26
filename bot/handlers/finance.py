"""Money: the amount after "Done", /expense, /balance and "I paid my debt back"."""

from __future__ import annotations

from contextlib import suppress

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ForceReply, Message
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from bot.announcements import (
    amount_saved_text,
    amount_text,
    announce_achievements,
    expense_text,
    settle_text,
)
from bot.db.models import CategoryKind, Duty, Member, Room
from bot.db.repositories import CategoryRepo, DutyRepo, MemberRepo, RoomRepo
from bot.handlers.common import ANSWER
from bot.i18n import Translator
from bot.keyboards.callbacks import AmountCb, ExpenseCb, SettleCb
from bot.keyboards.money import amount_keyboard, balance_keyboard, expense_split_keyboard
from bot.notifications import Notifier
from bot.render import balance_text
from bot.services.clock import local_date, utcnow
from bot.services.errors import ServiceError
from bot.services.finance import FinanceService
from bot.utils.money import format_money, parse_amount
from bot.utils.text import esc, mention

router = Router(name="finance")

NO_DESCRIPTION = {"-", "—", "0"}


class AmountInput(StatesGroup):
    value = State()


class ExpenseInput(StatesGroup):
    amount = State()
    description = State()
    split = State()


def _prompt(user: TgUser, text: str) -> str:
    return f"{mention(user.id, user.full_name)} 👇\n{text}"


# --- the amount right after "Done" ---------------------------------------------------------


async def offer_amount(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    t: Translator,
    duty: Duty,
    kind: str,
    user_id: int,
    *,
    in_group: bool,
) -> None:
    """Ask how much the purchase cost (not for chores like the trash)."""
    if kind == CategoryKind.TRASH:
        return
    if not in_group:
        # In private chat the answer is simply the next message.
        await state.set_state(AmountInput.value)
        await state.update_data(duty_id=duty.id)
    await bot.send_message(
        chat_id,
        t("amount-ask"),
        reply_markup=amount_keyboard(t, duty.id, user_id, with_enter=in_group),
    )


@router.callback_query(AmountCb.filter())
async def on_amount_button(
    callback: CallbackQuery, callback_data: AmountCb, state: FSMContext, t: Translator
) -> None:
    if callback.from_user.id != callback_data.user_id:
        await callback.answer(t("err-not-your-button"), show_alert=True)
        return
    message = callback.message if isinstance(callback.message, Message) else None
    if callback_data.action == "skip":
        if await state.get_state() == AmountInput.value.state:
            await state.clear()
        await callback.answer()
        if message is not None:
            with suppress(TelegramAPIError):
                await message.edit_text(t("amount-skipped"))
        return
    await state.set_state(AmountInput.value)
    await state.update_data(duty_id=callback_data.duty_id)
    await callback.answer()
    if message is not None:
        await message.answer(
            _prompt(callback.from_user, t("amount-enter")),
            reply_markup=ForceReply(selective=True, input_field_placeholder="23.50"),
        )


@router.message(AmountInput.value, ANSWER)
async def input_amount(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    t: Translator,
    notifier: Notifier,
) -> None:
    cents = parse_amount(message.text or "")
    if cents is None:
        await message.reply(t("err-bad-amount"))
        return
    data = await state.get_data()
    duty = await DutyRepo(session).get(data.get("duty_id", 0))
    category = await CategoryRepo(session).get(duty.category_id) if duty else None
    payer = await MemberRepo(session).get(duty.member_id) if duty else None
    if (
        duty is None
        or category is None
        or payer is None
        or message.from_user is None
        or payer.telegram_user_id != message.from_user.id
    ):
        await state.clear()
        await message.reply(t("err-assignment-closed"))
        return
    room = category.room
    try:
        expense = await FinanceService(session).record_duty_amount(
            room, duty, payer, cents, utcnow()
        )
    except ServiceError as error:
        await state.clear()
        await message.reply(t(error.key, **error.args_))
        return
    await state.clear()
    t = notifier.translator(room)
    await message.reply(amount_saved_text(t, room, category, expense))
    if message.chat.id != room.chat_id:
        await notifier.send_group(room, amount_text(t, room, category, payer, cents))
    await announce_achievements(session, notifier, room, payer)


# --- /expense --------------------------------------------------------------------------------


@router.message(Command("expense"), flags={"require": "member"})
async def cmd_expense(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    room: Room,
    member: Member,
    state: FSMContext,
    t: Translator,
) -> None:
    await state.clear()
    await state.update_data(room_id=room.id)
    if not command.args:
        await state.set_state(ExpenseInput.amount)
        await message.reply(
            t("expense-ask-amount"),
            reply_markup=ForceReply(selective=True, input_field_placeholder="120"),
        )
        return
    raw_amount, _, description = command.args.strip().partition(" ")
    cents = parse_amount(raw_amount)
    if cents is None:
        await state.clear()
        await message.reply(t("err-bad-amount"))
        return
    await state.update_data(amount=cents)
    if not description.strip():
        await state.set_state(ExpenseInput.description)
        await message.reply(t("expense-ask-description"), reply_markup=ForceReply(selective=True))
        return
    await _show_split(message, session, room, member, state, t, description.strip())


@router.message(ExpenseInput.amount, ANSWER)
async def input_expense_amount(message: Message, state: FSMContext, t: Translator) -> None:
    cents = parse_amount(message.text or "")
    if cents is None:
        await message.reply(t("err-bad-amount"), reply_markup=ForceReply(selective=True))
        return
    await state.update_data(amount=cents)
    await state.set_state(ExpenseInput.description)
    await message.reply(t("expense-ask-description"), reply_markup=ForceReply(selective=True))


@router.message(ExpenseInput.description, ANSWER)
async def input_expense_description(
    message: Message,
    session: AsyncSession,
    member: Member | None,
    state: FSMContext,
    t: Translator,
) -> None:
    room = await RoomRepo(session).get((await state.get_data()).get("room_id", 0))
    if room is None or member is None or member.room_id != room.id:
        await state.clear()
        return
    text = (message.text or "").strip()
    await _show_split(
        message, session, room, member, state, t, "" if text in NO_DESCRIPTION else text
    )


async def _show_split(
    message: Message,
    session: AsyncSession,
    room: Room,
    member: Member,
    state: FSMContext,
    t: Translator,
    description: str,
) -> None:
    today = local_date(room.timezone, utcnow())
    roommates = list(await MemberRepo(session).list(room.id))
    selected = [m.id for m in roommates if m.is_available(today)] or [member.id]
    data = await state.update_data(description=description, selected=selected)
    await state.set_state(ExpenseInput.split)
    await message.reply(
        _split_text(t, room, data),
        reply_markup=expense_split_keyboard(t, roommates, selected, member.telegram_user_id),
    )


def _split_text(t: Translator, room: Room, data: dict) -> str:
    return t(
        "expense-pick",
        amount=format_money(data["amount"], room.currency),
        description=esc(data.get("description") or "—"),
    )


@router.callback_query(ExpenseCb.filter(), flags={"require": "member"})
async def on_expense_button(
    callback: CallbackQuery,
    callback_data: ExpenseCb,
    session: AsyncSession,
    member: Member,
    state: FSMContext,
    t: Translator,
    notifier: Notifier,
) -> None:
    if callback.from_user.id != callback_data.user_id:
        await callback.answer(t("err-not-your-button"), show_alert=True)
        return
    message = callback.message if isinstance(callback.message, Message) else None
    data = await state.get_data()
    room = await RoomRepo(session).get(data.get("room_id", 0))
    if await state.get_state() != ExpenseInput.split.state or room is None or message is None:
        await callback.answer(t("err-assignment-closed"), show_alert=True)
        return
    roommates = list(await MemberRepo(session).list(room.id))
    selected: list[int] = list(data.get("selected", []))

    if callback_data.action == "cancel":
        await state.clear()
        await callback.answer()
        with suppress(TelegramAPIError):
            await message.edit_text(t("cancel-done"))
        return
    if callback_data.action == "save":
        try:
            expense = await FinanceService(session).add_expense(
                room, member, data["amount"], data.get("description", ""), selected, utcnow()
            )
        except ServiceError as error:
            await callback.answer(t(error.key, **error.args_), show_alert=True)
            return
        await state.clear()
        await callback.answer(t("toast-saved"))
        names = {m.id: m.display_name for m in roommates}
        text = expense_text(t, room, member, expense, names)
        with suppress(TelegramAPIError):
            await message.edit_text(text)
        if message.chat.id != room.chat_id:
            await notifier.send_group(room, text)
        await announce_achievements(session, notifier, room, member)
        return

    if callback_data.action == "all":
        selected = [m.id for m in roommates]
    elif callback_data.action == "toggle" and callback_data.value in {m.id for m in roommates}:
        if callback_data.value in selected:
            selected.remove(callback_data.value)
        else:
            selected.append(callback_data.value)
    data = await state.update_data(selected=selected)
    await callback.answer()
    with suppress(TelegramAPIError):
        await message.edit_reply_markup(
            reply_markup=expense_split_keyboard(t, roommates, selected, member.telegram_user_id)
        )


# --- /balance ----------------------------------------------------------------------------


async def _balance_view(session: AsyncSession, room: Room, t: Translator) -> tuple[str, object]:
    finance = FinanceService(session)
    balances = await finance.balances(room)
    transfers = await finance.transfers(room)
    names = {
        m.id: m.display_name for m in await MemberRepo(session).list(room.id, active_only=False)
    }
    return (
        balance_text(t, room, balances, transfers, names),
        balance_keyboard(transfers, names, room.currency),
    )


@router.message(Command("balance"), flags={"require": "room"})
async def cmd_balance(message: Message, session: AsyncSession, room: Room, t: Translator) -> None:
    text, markup = await _balance_view(session, room, t)
    await message.answer(text, reply_markup=markup)  # type: ignore[arg-type]


@router.callback_query(SettleCb.filter(), flags={"require": "member"})
async def on_settle(
    callback: CallbackQuery,
    callback_data: SettleCb,
    session: AsyncSession,
    room: Room,
    member: Member,
    t: Translator,
    notifier: Notifier,
) -> None:
    try:
        expense = await FinanceService(session).settle_debt(
            room,
            callback_data.debtor_id,
            callback_data.creditor_id,
            callback_data.cents,
            utcnow(),
            actor=member,
        )
    except ServiceError as error:
        await callback.answer(t(error.key, **error.args_), show_alert=True)
        return
    await callback.answer(t("toast-saved"))
    members = MemberRepo(session)
    debtor = await members.get(callback_data.debtor_id)
    creditor = await members.get(callback_data.creditor_id)
    await notifier.send_group(room, settle_text(t, room, debtor, creditor, expense.amount_cents))
    if isinstance(callback.message, Message):
        text, markup = await _balance_view(session, room, t)
        with suppress(TelegramAPIError):
            await callback.message.edit_text(text, reply_markup=markup)  # type: ignore[arg-type]

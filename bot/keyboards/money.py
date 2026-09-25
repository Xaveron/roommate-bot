"""Keyboards of stage 3: amounts, expenses, balance, shopping list, statistics."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db.models import Member, ShoppingItem
from bot.i18n import Translator
from bot.keyboards.callbacks import (
    AmountCb,
    ExpenseCb,
    SettleCb,
    ShopCb,
    StatsCb,
    TopCb,
)
from bot.services.finance import Transfer
from bot.services.stats import shift_month
from bot.utils.money import format_money
from bot.utils.text import truncate


def amount_keyboard(
    t: Translator, duty_id: int, user_id: int, *, with_enter: bool
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if with_enter:
        builder.button(
            text=t("btn-amount-enter"),
            callback_data=AmountCb(action="enter", duty_id=duty_id, user_id=user_id),
        )
    builder.button(
        text=t("btn-amount-skip"),
        callback_data=AmountCb(action="skip", duty_id=duty_id, user_id=user_id),
    )
    return builder.as_markup()


def expense_split_keyboard(
    t: Translator, members: Sequence[Member], selected: Collection[int], user_id: int
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for member in members:
        mark = "✅" if member.id in selected else "▫️"
        builder.button(
            text=f"{mark} {truncate(member.display_name, 20)}",
            callback_data=ExpenseCb(action="toggle", user_id=user_id, value=member.id),
        )
    builder.adjust(2)
    builder.row()
    builder.button(
        text=t("btn-expense-all"), callback_data=ExpenseCb(action="all", user_id=user_id)
    )
    builder.button(
        text=t("btn-expense-save"), callback_data=ExpenseCb(action="save", user_id=user_id)
    )
    builder.button(text=t("btn-cancel"), callback_data=ExpenseCb(action="cancel", user_id=user_id))
    sizes = [2] * (len(members) // 2) + ([1] if len(members) % 2 else []) + [1, 2]
    builder.adjust(*sizes)
    return builder.as_markup()


def balance_keyboard(
    transfers: Sequence[Transfer], names: Mapping[int, str], currency: str
) -> InlineKeyboardMarkup | None:
    if not transfers:
        return None
    builder = InlineKeyboardBuilder()
    for transfer in transfers:
        debtor = truncate(names.get(transfer.debtor_id, "?"), 14)
        creditor = truncate(names.get(transfer.creditor_id, "?"), 14)
        builder.button(
            text=f"✅ {debtor} → {creditor} · {format_money(transfer.amount_cents, currency)}",
            callback_data=SettleCb(
                debtor_id=transfer.debtor_id,
                creditor_id=transfer.creditor_id,
                cents=transfer.amount_cents,
            ),
        )
    builder.adjust(1)
    return builder.as_markup()


def shopping_keyboard(t: Translator, items: Sequence[ShoppingItem]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(
            text=t("btn-item-bought", item=truncate(item.text, 30)),
            callback_data=ShopCb(action="bought", item_id=item.id),
        )
    builder.button(text=t("btn-going-shopping"), callback_data=ShopCb(action="going"))
    builder.button(text=t("btn-refresh"), callback_data=ShopCb(action="refresh"))
    sizes = [2] * (len(items) // 2) + ([1] if len(items) % 2 else []) + [2]
    builder.adjust(*sizes)
    return builder.as_markup()


def stats_keyboard(t: Translator, year: int, month: int, *, has_next: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    prev_year, prev_month = shift_month(year, month, -1)
    builder.button(
        text=t("btn-stats-prev"), callback_data=StatsCb(year=prev_year, month=prev_month)
    )
    if has_next:
        next_year, next_month = shift_month(year, month, 1)
        builder.button(
            text=t("btn-stats-next"), callback_data=StatsCb(year=next_year, month=next_month)
        )
    return builder.as_markup()


def top_keyboard(t: Translator) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn-achievements"), callback_data=TopCb(action="achievements"))
    return builder.as_markup()

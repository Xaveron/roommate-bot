from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db.models import Assignment, AssignmentStatus, Category, Room, Vote
from bot.i18n import Translator
from bot.keyboards.callbacks import (
    AwayCb,
    DoneCb,
    HistoryCb,
    JoinCb,
    LeaveCb,
    RoomPickCb,
    TurnCb,
    VoteCb,
)

AWAY_PRESETS = (1, 3, 7, 14)


def bot_link(bot_username: str, payload: str = "dm") -> str:
    return f"https://t.me/{bot_username}?start={payload}"


def open_bot_button(t: Translator, bot_username: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=t("btn-open-bot"), url=bot_link(bot_username))


def join_keyboard(t: Translator, bot_username: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn-join"), callback_data=JoinCb())
    builder.row(open_bot_button(t, bot_username))
    return builder.as_markup()


def open_bot_keyboard(t: Translator, bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[open_bot_button(t, bot_username)]])


def leave_confirm_keyboard(t: Translator, user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("btn-leave-confirm"), callback_data=LeaveCb(user_id=user_id, confirm=True)
    )
    builder.button(text=t("btn-cancel"), callback_data=LeaveCb(user_id=user_id, confirm=False))
    return builder.as_markup()


def turn_keyboard(
    t: Translator, assignment: Assignment, *, bot_username: str | None = None
) -> InlineKeyboardMarkup | None:
    """Buttons under a reminder, depending on the assignment state."""
    kind = assignment.category.kind
    builder = InlineKeyboardBuilder()

    def add(action: str, text: str) -> None:
        builder.button(text=text, callback_data=TurnCb(action=action, assignment_id=assignment.id))

    if assignment.status == AssignmentStatus.PENDING:
        add("accept", t("btn-accept", kind=kind))
        add("still", t("btn-still-have", kind=kind))
        add("decline", t("btn-decline"))
        builder.adjust(2, 1)
    elif assignment.status == AssignmentStatus.ACCEPTED:
        add("done", t("btn-done"))
        add("decline", t("btn-decline"))
        builder.adjust(1, 1)
    else:
        return None
    if bot_username:
        builder.row(open_bot_button(t, bot_username))
    return builder.as_markup()


def done_picker(
    t: Translator, categories: Sequence[Category], user_id: int
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(
            text=category.title, callback_data=DoneCb(category_id=category.id, user_id=user_id)
        )
    builder.adjust(2)
    return builder.as_markup()


def history_picker(t: Translator, categories: Sequence[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(text=category.title, callback_data=HistoryCb(category_id=category.id))
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(
            text=t("btn-history-all"), callback_data=HistoryCb(category_id=0).pack()
        )
    )
    return builder.as_markup()


def vote_keyboard(t: Translator, duty_id: int, up: int = 0, down: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("btn-vote-up", count=up), callback_data=VoteCb(duty_id=duty_id, vote=Vote.UP)
    )
    builder.button(
        text=t("btn-vote-down", count=down),
        callback_data=VoteCb(duty_id=duty_id, vote=Vote.DOWN),
    )
    return builder.as_markup()


def away_keyboard(t: Translator, user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for days in AWAY_PRESETS:
        builder.button(
            text=t("btn-away-days", days=days),
            callback_data=AwayCb(action="days", user_id=user_id, value=days),
        )
    builder.button(
        text=t("btn-away-custom"), callback_data=AwayCb(action="custom", user_id=user_id)
    )
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def back_home_keyboard(t: Translator, user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn-back-home"), callback_data=AwayCb(action="back", user_id=user_id))
    return builder.as_markup()


def room_picker(rooms: Sequence[Room], active_room_id: int | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for room in rooms:
        mark = "✅ " if room.id == active_room_id else ""
        builder.button(text=f"{mark}{room.name}", callback_data=RoomPickCb(room_id=room.id))
    builder.adjust(1)
    return builder.as_markup()

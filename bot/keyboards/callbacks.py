"""Callback data factories (payload must fit into 64 bytes; ':' is the separator)."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class JoinCb(CallbackData, prefix="join"):
    pass


class LeaveCb(CallbackData, prefix="leave"):
    user_id: int  # only the member who asked may confirm
    confirm: bool = False


class TurnCb(CallbackData, prefix="turn"):
    """Buttons under a reminder. action: accept | done | still | decline."""

    action: str
    assignment_id: int


class DoneCb(CallbackData, prefix="done"):
    category_id: int
    user_id: int  # only the member who asked may pick


class HistoryCb(CallbackData, prefix="hist"):
    category_id: int  # 0 = all categories


class VoteCb(CallbackData, prefix="vote"):
    """👍 / 🤨 under a completion announcement. vote: up | down."""

    duty_id: int
    vote: str


class AwayCb(CallbackData, prefix="away"):
    """action: days (value = number of days) | custom | back."""

    action: str
    user_id: int
    value: int = 0


class AmountCb(CallbackData, prefix="amt"):
    """After "Done": action enter | skip."""

    action: str
    duty_id: int
    user_id: int


class ExpenseCb(CallbackData, prefix="exp"):
    """/expense split picker. action: toggle (value = member id) | all | save | cancel."""

    action: str
    user_id: int
    value: int = 0


class SettleCb(CallbackData, prefix="settle"):
    debtor_id: int
    creditor_id: int
    cents: int


class ShopCb(CallbackData, prefix="shop"):
    """action: bought (item_id) | going | refresh."""

    action: str
    item_id: int = 0


class StatsCb(CallbackData, prefix="stats"):
    year: int
    month: int


class TopCb(CallbackData, prefix="top"):
    action: str  # achievements


class RoomPickCb(CallbackData, prefix="room"):
    room_id: int


class SettingsCb(CallbackData, prefix="st"):
    """Settings menu navigation. ``value`` never contains ':'."""

    action: str
    category_id: int = 0
    value: str = ""

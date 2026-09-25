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


class RoomPickCb(CallbackData, prefix="room"):
    room_id: int


class SettingsCb(CallbackData, prefix="st"):
    """Settings menu navigation. ``value`` never contains ':'."""

    action: str
    category_id: int = 0
    value: str = ""

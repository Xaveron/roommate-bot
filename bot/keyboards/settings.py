from __future__ import annotations

from collections.abc import Sequence
from datetime import time

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import SUPPORTED_LANGUAGES
from bot.db.models import Category, Member
from bot.i18n import Translator
from bot.keyboards.callbacks import SettingsCb
from bot.utils.parsing import compact_time, format_time

TIME_PRESETS = tuple(time(h) for h in (7, 8, 9, 12, 15, 17, 18, 19, 20, 21, 22, 23))
QUIET_PRESETS = (
    (time(22), time(8)),
    (time(23), time(8)),
    (time(23), time(9)),
    (time(0), time(8)),
)
REPEAT_PRESETS = (1, 2, 3, 4, 6, 8)
TIMEZONE_PRESETS = (
    "Europe/Chisinau",
    "Europe/Bucharest",
    "Europe/Kyiv",
    "Europe/Moscow",
    "Europe/Istanbul",
    "Europe/Berlin",
    "Europe/London",
    "UTC",
)


def _cb(action: str, category_id: int = 0, value: str = "") -> str:
    return SettingsCb(action=action, category_id=category_id, value=value).pack()


def _back(builder: InlineKeyboardBuilder, t: Translator, action: str, category_id: int = 0):
    builder.button(text=t("btn-back"), callback_data=_cb(action, category_id))


def main_menu(t: Translator) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn-settings-categories"), callback_data=_cb("cats"))
    builder.button(text=t("btn-settings-repeat"), callback_data=_cb("repeat"))
    builder.button(text=t("btn-settings-quiet"), callback_data=_cb("quiet"))
    builder.button(text=t("btn-settings-timezone"), callback_data=_cb("tz"))
    builder.button(text=t("btn-settings-language"), callback_data=_cb("lang"))
    builder.button(text=t("btn-settings-members"), callback_data=_cb("members"))
    builder.button(text=t("btn-close"), callback_data=_cb("close"))
    builder.adjust(1, 2, 2, 1, 1)
    return builder.as_markup()


def categories_menu(t: Translator, categories: Sequence[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        state = "✅" if category.is_active else "⏸"
        builder.button(
            text=f"{state} {category.title} · {format_time(category.reminder_time)}",
            callback_data=_cb("cat", category.id),
        )
    builder.button(text=t("btn-add-category"), callback_data=_cb("addcat"))
    _back(builder, t, "menu")
    builder.adjust(1)
    return builder.as_markup()


def category_menu(t: Translator, category: Category) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn-category-time"), callback_data=_cb("time", category.id))
    builder.button(text=t("btn-category-days"), callback_data=_cb("days", category.id))
    builder.button(
        text=t("btn-category-mode", mode=category.queue_mode),
        callback_data=_cb("mode", category.id),
    )
    toggle_key = "btn-category-disable" if category.is_active else "btn-category-enable"
    builder.button(text=t(toggle_key), callback_data=_cb("toggle", category.id))
    builder.button(text=t("btn-category-delete"), callback_data=_cb("del", category.id))
    _back(builder, t, "cats")
    builder.adjust(2, 1, 2, 1)
    return builder.as_markup()


def time_menu(t: Translator, category: Category) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for preset in TIME_PRESETS:
        mark = "• " if preset == category.reminder_time else ""
        builder.button(
            text=f"{mark}{format_time(preset)}",
            callback_data=_cb("settime", category.id, compact_time(preset)),
        )
    builder.button(text=t("btn-custom-time"), callback_data=_cb("customtime", category.id))
    _back(builder, t, "cat", category.id)
    builder.adjust(4, 4, 4, 1, 1)
    return builder.as_markup()


def days_menu(t: Translator, category: Category) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for day in range(7):
        mark = "✅" if str(day) in category.reminder_days else "▫️"
        builder.button(
            text=f"{mark} {t('weekday-short', day=day)}",
            callback_data=_cb("day", category.id, str(day)),
        )
    builder.button(text=t("btn-every-day"), callback_data=_cb("alldays", category.id))
    _back(builder, t, "cat", category.id)
    builder.adjust(4, 3, 1, 1)
    return builder.as_markup()


def delete_confirm_menu(t: Translator, category: Category) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn-delete-confirm"), callback_data=_cb("delok", category.id))
    _back(builder, t, "cat", category.id)
    builder.adjust(1)
    return builder.as_markup()


def repeat_menu(t: Translator, current: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for hours in REPEAT_PRESETS:
        mark = "• " if hours == current else ""
        builder.button(
            text=f"{mark}{t('btn-repeat-hours', hours=hours)}",
            callback_data=_cb("setrepeat", value=str(hours)),
        )
    mark = "• " if current == 0 else ""
    builder.button(text=f"{mark}{t('btn-repeat-off')}", callback_data=_cb("setrepeat", value="0"))
    _back(builder, t, "menu")
    builder.adjust(3, 3, 1, 1)
    return builder.as_markup()


def quiet_menu(t: Translator) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for start, end in QUIET_PRESETS:
        builder.button(
            text=f"{format_time(start)}–{format_time(end)}",
            callback_data=_cb("setquiet", value=f"{compact_time(start)}{compact_time(end)}"),
        )
    builder.button(text=t("btn-quiet-off"), callback_data=_cb("setquiet", value="off"))
    builder.button(text=t("btn-custom-range"), callback_data=_cb("customquiet"))
    _back(builder, t, "menu")
    builder.adjust(2, 2, 1, 1, 1)
    return builder.as_markup()


def timezone_menu(t: Translator, current: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, name in enumerate(TIMEZONE_PRESETS):
        mark = "• " if name == current else ""
        builder.button(text=f"{mark}{name}", callback_data=_cb("settz", value=str(index)))
    builder.button(text=t("btn-custom-timezone"), callback_data=_cb("customtz"))
    _back(builder, t, "menu")
    builder.adjust(2, 2, 2, 2, 1, 1)
    return builder.as_markup()


def language_menu(t: Translator, current: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code in SUPPORTED_LANGUAGES:
        mark = "• " if code == current else ""
        builder.button(
            text=f"{mark}{t('language-name', code=code)}", callback_data=_cb("setlang", value=code)
        )
    _back(builder, t, "menu")
    builder.adjust(3, 1)
    return builder.as_markup()


def members_menu(t: Translator, members: Sequence[Member]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for member in members:
        builder.button(
            text=t("btn-remove-member", name=member.display_name),
            callback_data=_cb("rmm", value=str(member.id)),
        )
    _back(builder, t, "menu")
    builder.adjust(1)
    return builder.as_markup()


def remove_member_confirm(t: Translator, member: Member) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("btn-remove-member-confirm"), callback_data=_cb("rmmok", value=str(member.id))
    )
    _back(builder, t, "members")
    builder.adjust(1)
    return builder.as_markup()

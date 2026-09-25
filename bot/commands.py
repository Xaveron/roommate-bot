"""Localized command menus shown by Telegram clients."""

from __future__ import annotations

from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
)

from bot.i18n import I18n

GROUP_COMMANDS = (
    "start",
    "queue",
    "done",
    "history",
    "add_category",
    "settings",
    "away",
    "back",
    "members",
    "leave",
    "help",
)
PRIVATE_COMMANDS = ("start", "queue", "done", "history", "away", "back", "room", "help")


async def set_bot_commands(bot: Bot, i18n: I18n) -> None:
    for locale in i18n.locales:
        t = i18n.get(locale)
        # English doubles as the default menu for every other language.
        language_code = None if locale == "en" else locale
        for scope, names in (
            (BotCommandScopeAllGroupChats(), GROUP_COMMANDS),
            (BotCommandScopeAllPrivateChats(), PRIVATE_COMMANDS),
        ):
            commands = [
                BotCommand(command=name, description=t("cmd-description", command=name))
                for name in names
            ]
            await bot.set_my_commands(commands, scope=scope, language_code=language_code)

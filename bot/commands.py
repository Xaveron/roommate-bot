"""Localized command menus shown by Telegram clients."""

from __future__ import annotations

from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    MenuButtonCommands,
    MenuButtonWebApp,
    WebAppInfo,
)

from bot.config import Settings
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
    "buy",
    "list",
    "shop",
    "expense",
    "balance",
    "stats",
    "top",
    "export",
    "app",
    "members",
    "leave",
    "help",
)
PRIVATE_COMMANDS = (
    "start",
    "queue",
    "done",
    "history",
    "buy",
    "list",
    "expense",
    "balance",
    "stats",
    "top",
    "app",
    "away",
    "back",
    "room",
    "help",
)


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


async def set_menu_button(bot: Bot, i18n: I18n, settings: Settings) -> None:
    """The button next to the message field in private chats opens the Mini App."""
    if settings.webapp_url:
        t = i18n.get(settings.default_language)
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text=t("btn-webapp"), web_app=WebAppInfo(url=f"{settings.webapp_url}/")
            )
        )
    else:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

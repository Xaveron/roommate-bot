"""Entry point: wires config, database, i18n, dispatcher and scheduler together."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Dispatcher
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage

from bot import migrate
from bot.commands import set_bot_commands, set_menu_button
from bot.config import Settings, get_settings
from bot.db import Database
from bot.handlers import build_router
from bot.i18n import I18n
from bot.middlewares import (
    DbSessionMiddleware,
    I18nMiddleware,
    RequirementsMiddleware,
    RoomContextMiddleware,
)
from bot.notifications import Notifier, create_bot
from bot.scheduler import setup_scheduler

logger = logging.getLogger(__name__)


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)


def build_dispatcher(
    settings: Settings, db: Database, i18n: I18n, notifier: Notifier
) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage(), settings=settings, i18n=i18n, notifier=notifier)
    # Order matters: session -> user/room context -> translator.
    dp.update.outer_middleware(DbSessionMiddleware(db))
    dp.update.outer_middleware(RoomContextMiddleware())
    dp.update.outer_middleware(I18nMiddleware(i18n))
    dp.message.middleware(RequirementsMiddleware())
    dp.callback_query.middleware(RequirementsMiddleware())
    dp.include_router(build_router())
    return dp


async def run() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    if settings.auto_migrate:
        logger.info("Applying database migrations")
        await asyncio.to_thread(migrate.upgrade, settings.database_url)

    db = Database(settings.database_url)
    i18n = I18n(default_locale=settings.default_language)
    bot = create_bot(settings.bot_token.get_secret_value())
    notifier = Notifier(bot, i18n)
    dp = build_dispatcher(settings, db, i18n, notifier)
    scheduler = setup_scheduler(settings, db, notifier)

    try:
        me = await bot.me()
    except TelegramUnauthorizedError:
        logger.error("Telegram rejected BOT_TOKEN: check the token from @BotFather in .env")
        await bot.session.close()
        await db.dispose()
        raise SystemExit(1) from None
    logger.info("Starting @%s", me.username)
    await set_bot_commands(bot, i18n)
    await set_menu_button(bot, i18n, settings)
    scheduler.start()
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await db.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

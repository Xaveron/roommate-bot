"""Last line of defence: log the error and tell the user something went wrong."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ErrorEvent

from bot.i18n import I18n

logger = logging.getLogger(__name__)
router = Router(name="errors")


@router.errors()
async def on_error(event: ErrorEvent, i18n: I18n) -> bool:
    update = event.update
    logger.exception("Error while handling update %s", update.update_id, exc_info=event.exception)
    source = update.message or update.callback_query
    user = source.from_user if source is not None else None
    t = i18n.get(user.language_code if user else None)
    try:
        if update.callback_query is not None:
            await update.callback_query.answer(t("err-generic"), show_alert=True)
        elif update.message is not None:
            await update.message.reply(t("err-generic"))
    except TelegramAPIError:
        pass
    return True

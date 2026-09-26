"""👍 / 🤨 votes under completion announcements."""

from __future__ import annotations

from contextlib import suppress

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.announcements import review_note
from bot.db.models import Member, Vote
from bot.i18n import Translator
from bot.keyboards.callbacks import VoteCb
from bot.keyboards.common import vote_keyboard
from bot.services.clock import utcnow
from bot.services.errors import ServiceError
from bot.services.reviews import ReviewService

router = Router(name="reviews")


@router.callback_query(VoteCb.filter(), flags={"require": "member"})
async def on_vote(
    callback: CallbackQuery,
    callback_data: VoteCb,
    session: AsyncSession,
    member: Member,
    t: Translator,
) -> None:
    try:
        outcome = await ReviewService(session).vote(
            callback_data.duty_id, member, Vote(callback_data.vote), utcnow()
        )
    except ServiceError as error:
        await callback.answer(t(error.key, **error.args_), show_alert=True)
        return
    except ValueError:
        await callback.answer(t("err-generic"), show_alert=True)
        return

    message = callback.message if isinstance(callback.message, Message) else None
    if outcome.decided is None:
        await callback.answer(t("toast-vote-saved"))
        if message is not None:
            with suppress(TelegramAPIError):
                await message.edit_reply_markup(
                    reply_markup=vote_keyboard(t, outcome.duty.id, outcome.up, outcome.down)
                )
        return

    note = review_note(t, outcome)
    await callback.answer(t("toast-vote-saved"))
    if message is not None:
        with suppress(TelegramAPIError):
            await message.edit_text(f"{message.html_text}\n\n{note}", reply_markup=None)

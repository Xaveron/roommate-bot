"""/history: recent records, one table per category."""

from __future__ import annotations

from aiogram import Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import ReviewStatus, Room
from bot.handlers.common import answer_long, split_long
from bot.i18n import Translator
from bot.keyboards.callbacks import HistoryCb
from bot.keyboards.common import history_picker
from bot.services.categories import CategoryService
from bot.services.clock import local_now
from bot.services.errors import ServiceError
from bot.services.history import CategoryHistory, HistoryService
from bot.utils.text import bold, esc, render_table

router = Router(name="history")


def render_history(t: Translator, room: Room, history: CategoryHistory) -> str:
    title = bold(history.category.title)
    if not history.duties:
        return f"{title}\n{t('history-empty')}"
    rows = [
        [
            local_now(room.timezone, duty.created_at).strftime("%d.%m %H:%M"),
            duty.member.display_name,
            t("duty-status", status=duty.status)
            if duty.review != ReviewStatus.DISPUTED
            else t("duty-disputed", status=t("duty-status", status=duty.status)),
        ]
        for duty in history.duties
    ]
    headers = [t("history-col-date"), t("history-col-who"), t("history-col-status")]
    table = render_table(headers, rows, max_widths=[11, 12, 24])
    return f"{title}\n<pre>{esc(table)}</pre>"


@router.message(Command("history"), flags={"require": "room"})
async def cmd_history(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    room: Room,
    t: Translator,
) -> None:
    categories = CategoryService(session)
    if command.args:
        category = await categories.find(room, command.args, active_only=False)
        if category is not None:
            history = await HistoryService(session).for_category(category)
            await message.answer(render_history(t, room, history))
            return
    all_categories = await categories.list(room)
    if not all_categories:
        await message.answer(t("err-no-categories"))
        return
    await message.answer(t("history-pick"), reply_markup=history_picker(t, all_categories))


@router.callback_query(HistoryCb.filter(), flags={"require": "room"})
async def on_history_picked(
    callback: CallbackQuery,
    callback_data: HistoryCb,
    session: AsyncSession,
    room: Room,
    t: Translator,
) -> None:
    service = HistoryService(session)
    if callback_data.category_id == 0:
        tables = [render_history(t, room, h) for h in await service.for_room(room)]
        text = "\n\n".join([t("history-title", room=esc(room.name)), *tables])
    else:
        try:
            category = await CategoryService(session).get(room, callback_data.category_id)
        except ServiceError as error:
            await callback.answer(t(error.key, **error.args_), show_alert=True)
            return
        text = render_history(t, room, await service.for_category(category))
    await callback.answer()
    if callback.message is None:
        return
    parts = split_long(text)
    try:
        await callback.message.edit_text(parts[0])  # type: ignore[union-attr]
    except TelegramAPIError:
        await answer_long(callback.message, parts[0])  # type: ignore[arg-type]
    for part in parts[1:]:
        await callback.message.answer(part)  # type: ignore[union-attr]

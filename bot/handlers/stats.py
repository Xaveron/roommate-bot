"""/stats, /top and /export."""

from __future__ import annotations

import asyncio

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.announcements import send_export
from bot.db.models import Room
from bot.db.repositories import MemberRepo
from bot.i18n import Translator
from bot.keyboards.callbacks import StatsCb, TopCb
from bot.keyboards.money import stats_keyboard, top_keyboard
from bot.render import achievements_text, month_title, stats_chart, stats_text, top_text
from bot.services.achievements import AchievementService
from bot.services.clock import local_now, utcnow
from bot.services.stats import StatsService

router = Router(name="stats")


async def _send_stats(
    message: Message, session: AsyncSession, room: Room, t: Translator, year: int, month: int
) -> None:
    stats = await StatsService(session).month(room, year, month)
    title = month_title(t, year, month)
    chart = await asyncio.to_thread(stats_chart, t, stats, title)
    if chart is not None:
        await message.answer_photo(BufferedInputFile(chart, "stats.png"))
    today = local_now(room.timezone, utcnow()).date()
    has_next = (year, month) < (today.year, today.month)
    await message.answer(
        stats_text(t, room, stats, title),
        reply_markup=stats_keyboard(t, year, month, has_next=has_next),
    )


@router.message(Command("stats"), flags={"require": "room"})
async def cmd_stats(message: Message, session: AsyncSession, room: Room, t: Translator) -> None:
    today = local_now(room.timezone, utcnow()).date()
    await _send_stats(message, session, room, t, today.year, today.month)


@router.callback_query(StatsCb.filter(), flags={"require": "room"})
async def on_stats_month(
    callback: CallbackQuery,
    callback_data: StatsCb,
    session: AsyncSession,
    room: Room,
    t: Translator,
) -> None:
    await callback.answer()
    if isinstance(callback.message, Message) and 1 <= callback_data.month <= 12:
        await _send_stats(
            callback.message, session, room, t, callback_data.year, callback_data.month
        )


@router.message(Command("top"), flags={"require": "room"})
async def cmd_top(message: Message, session: AsyncSession, room: Room, t: Translator) -> None:
    today = local_now(room.timezone, utcnow()).date()
    stats = await StatsService(session).month(room, today.year, today.month)
    badges = await AchievementService(session).for_members([m.member for m in stats.members])
    await message.answer(
        top_text(t, stats, badges, month_title(t, today.year, today.month)),
        reply_markup=top_keyboard(t),
    )


@router.callback_query(TopCb.filter(), flags={"require": "room"})
async def on_top_button(
    callback: CallbackQuery, session: AsyncSession, room: Room, t: Translator
) -> None:
    await callback.answer()
    members = list(await MemberRepo(session).list(room.id))
    badges = await AchievementService(session).for_members(members)
    if isinstance(callback.message, Message):
        await callback.message.answer(achievements_text(t, members, badges))


@router.message(Command("export"), flags={"require": "member"})
async def cmd_export(
    message: Message, bot: Bot, session: AsyncSession, room: Room, t: Translator
) -> None:
    thread_id = message.message_thread_id if message.is_topic_message else None
    await send_export(bot, session, room, t, message.chat.id, thread_id=thread_id)

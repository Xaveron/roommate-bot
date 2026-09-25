"""Shared shopping list: /buy, /list and "I'm going to the shop"."""

from __future__ import annotations

from contextlib import suppress

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Member, Room
from bot.db.repositories import MemberRepo
from bot.handlers.common import announce_achievements
from bot.i18n import Translator
from bot.keyboards.callbacks import ShopCb
from bot.keyboards.money import shopping_keyboard
from bot.notifications import Notifier
from bot.render import shopping_text
from bot.services.clock import utcnow
from bot.services.errors import ServiceError
from bot.services.reminders import room_is_quiet
from bot.services.shopping import ShoppingService
from bot.utils.text import bold, esc

router = Router(name="shopping")


async def _list_view(session: AsyncSession, room: Room, t: Translator) -> tuple[str, object]:
    items = await ShoppingService(session).open_items(room)
    names = {
        m.id: m.display_name for m in await MemberRepo(session).list(room.id, active_only=False)
    }
    return shopping_text(t, items, names), shopping_keyboard(t, items)


@router.message(Command("buy"), flags={"require": "member"})
async def cmd_buy(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    room: Room,
    member: Member,
    t: Translator,
) -> None:
    if not command.args:
        await message.reply(t("buy-usage"))
        return
    try:
        added = await ShoppingService(session).add(room, member, command.args, utcnow())
    except ServiceError as error:
        await message.reply(t(error.key, **error.args_))
        return
    if not added:
        await message.reply(t("buy-nothing-new"))
        return
    await message.reply(t("buy-added", items=esc(", ".join(item.text for item in added))))


@router.message(Command("list"), flags={"require": "room"})
async def cmd_list(message: Message, session: AsyncSession, room: Room, t: Translator) -> None:
    text, markup = await _list_view(session, room, t)
    await message.answer(text, reply_markup=markup)  # type: ignore[arg-type]


async def going_shopping(
    bot: Bot, session: AsyncSession, room: Room, member: Member, notifier: Notifier
) -> None:
    """Tell the group chat and every other roommate (in private, outside quiet hours)."""
    t = notifier.translator(room)
    items = await ShoppingService(session).open_items(room)
    listed = "\n".join(f"• {esc(item.text)}" for item in items) or t("list-empty")
    name = bold(member.display_name)
    await notifier.send_group(room, t("shopping-going", name=name, list=listed))
    if room_is_quiet(room, utcnow()):
        return
    for roommate in await MemberRepo(session).list(room.id):
        if roommate.id == member.id or not roommate.user.dm_available:
            continue
        with suppress(TelegramAPIError):
            await bot.send_message(
                roommate.telegram_user_id,
                t("shopping-going-dm", name=name, room=esc(room.name), list=listed),
            )


@router.message(Command("shop"), flags={"require": "member"})
async def cmd_shop(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    room: Room,
    member: Member,
    t: Translator,
    notifier: Notifier,
) -> None:
    await going_shopping(bot, session, room, member, notifier)
    if message.chat.id != room.chat_id:
        await message.reply(t("shopping-going-sent"))


@router.callback_query(ShopCb.filter(), flags={"require": "member"})
async def on_shop_button(
    callback: CallbackQuery,
    callback_data: ShopCb,
    bot: Bot,
    session: AsyncSession,
    room: Room,
    member: Member,
    t: Translator,
    notifier: Notifier,
) -> None:
    if callback_data.action == "going":
        await going_shopping(bot, session, room, member, notifier)
        await callback.answer(t("shopping-going-sent"))
        return
    if callback_data.action == "bought":
        try:
            await ShoppingService(session).mark_bought(
                room, callback_data.item_id, member, utcnow()
            )
        except ServiceError as error:
            await callback.answer(t(error.key, **error.args_), show_alert=True)
        else:
            await callback.answer(t("toast-bought"))
            await announce_achievements(session, notifier, room, member)
    else:
        await callback.answer()
    if isinstance(callback.message, Message):
        text, markup = await _list_view(session, room, t)
        with suppress(TelegramAPIError):
            await callback.message.edit_text(text, reply_markup=markup)  # type: ignore[arg-type]

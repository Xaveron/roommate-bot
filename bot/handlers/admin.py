"""Commands for the bot owners (ADMIN_IDS in .env)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from bot.db.repositories import DutyRepo, MemberRepo, RoomRepo, UserRepo
from bot.i18n import Translator

router = Router(name="admin")


@router.message(Command("admin"), F.chat.type == ChatType.PRIVATE)
async def cmd_admin(
    message: Message, session: AsyncSession, settings: Settings, t: Translator
) -> None:
    if message.from_user is None or message.from_user.id not in settings.admin_ids:
        return  # stay invisible for everybody else
    await message.answer(
        t(
            "admin-stats",
            rooms=await RoomRepo(session).count(),
            members=await MemberRepo(session).count(),
            users=await UserRepo(session).count(),
            duties=await DutyRepo(session).count(),
        )
    )

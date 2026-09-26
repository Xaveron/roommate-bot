"""Rooms and their members."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, time

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.locks import lock_room
from bot.db.models import CategoryKind, Member, Room, User
from bot.db.repositories import CategoryRepo, MemberRepo, RoomRepo
from bot.services.categories import CategoryService
from bot.services.clock import is_valid_timezone
from bot.services.errors import ServiceError
from bot.services.queue import QueueService

MAX_REPEAT_HOURS = 24

# kind, emoji, reminder time
DEFAULT_CATEGORIES: tuple[tuple[CategoryKind, str, time], ...] = (
    (CategoryKind.BREAD, "🍞", time(18, 0)),
    (CategoryKind.WATER, "💧", time(18, 0)),
    (CategoryKind.TRASH, "🗑", time(20, 0)),
)


class RoomService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.rooms = RoomRepo(session)
        self.members = MemberRepo(session)
        self.categories = CategoryRepo(session)
        self.queue = QueueService(session)

    async def get_or_create(
        self,
        *,
        chat_id: int,
        title: str,
        created_by: int | None,
        language: str,
        timezone: str,
        default_names: Mapping[str, str],
        now: datetime,
    ) -> tuple[Room, bool]:
        """Return the room of a group chat, creating it with default categories if needed."""
        room = await self.rooms.get_by_chat_id(chat_id)
        if room is not None:
            room.is_active = True
            if title and room.name != title:
                room.name = title
            return room, False

        try:
            async with self.session.begin_nested():
                room = await self.rooms.add(
                    Room(
                        chat_id=chat_id,
                        name=title,
                        language=language,
                        timezone=timezone,
                        created_by=created_by,
                        is_active=True,
                        created_at=now,
                    )
                )
                category_service = CategoryService(self.session)
                for kind, emoji, reminder_time in DEFAULT_CATEGORIES:
                    await category_service.create(
                        room,
                        name=default_names[kind],
                        emoji=emoji,
                        now=now,
                        kind=kind,
                        reminder_time=reminder_time,
                    )
        except IntegrityError:
            # Telegram delivered two updates at once ("bot added" + /start) and the other
            # one created the room first.
            existing = await self.rooms.get_by_chat_id(chat_id)
            if existing is None:
                raise
            return existing, False
        return room, True

    async def join(self, room: Room, user: User, now: datetime) -> tuple[Member, bool]:
        """Add the user to the room. Returns (member, joined_now)."""
        await lock_room(self.session, room.id)
        member = await self.members.get_by_user(room.id, user.id)
        if member is not None and member.is_active:
            return member, False
        if member is None:
            try:
                async with self.session.begin_nested():
                    member = await self.members.add(
                        Member(
                            room_id=room.id,
                            telegram_user_id=user.id,
                            user=user,
                            is_active=True,
                            joined_at=now,
                        )
                    )
                    await self.queue.enqueue_member(room.id, member.id)
            except IntegrityError:
                # A double tap on "I live here": the other request added the member.
                existing = await self.members.get_by_user(room.id, user.id)
                if existing is None:
                    raise
                return existing, False
            await self.session.flush()
            return member, True
        member.is_active = True
        member.away_until = None
        await self.queue.enqueue_member(room.id, member.id)
        await self.session.flush()
        return member, True

    async def leave(self, member: Member) -> None:
        """Deactivate the member. Their open turns are handed over by the scheduler."""
        await lock_room(self.session, member.room_id)
        member.is_active = False
        await self.session.flush()

    async def active_members(self, room: Room) -> Sequence[Member]:
        return await self.members.list(room.id)

    async def set_language(
        self,
        room: Room,
        language: str,
        old_names: Mapping[str, str],
        new_names: Mapping[str, str],
    ) -> None:
        """Switch language; default categories that kept their default name get translated."""
        await lock_room(self.session, room.id)
        room.language = language
        for category in await self.categories.list(room.id):
            if category.kind == CategoryKind.CUSTOM:
                continue
            if category.name == old_names.get(category.kind) and category.kind in new_names:
                category.name = new_names[category.kind]
        await self.session.flush()

    async def set_timezone(self, room: Room, timezone: str) -> None:
        if not is_valid_timezone(timezone):
            raise ServiceError("err-bad-timezone")
        await lock_room(self.session, room.id)
        room.timezone = timezone
        await self.session.flush()

    async def set_quiet_hours(self, room: Room, start: time | None, end: time | None) -> None:
        if (start is None) != (end is None) or (start is not None and start == end):
            raise ServiceError("err-bad-time-range")
        await lock_room(self.session, room.id)
        room.quiet_hours_start, room.quiet_hours_end = start, end
        await self.session.flush()

    async def set_repeat_hours(self, room: Room, hours: int) -> None:
        if not 0 <= hours <= MAX_REPEAT_HOURS:
            raise ServiceError("err-generic")
        await lock_room(self.session, room.id)
        room.repeat_after_hours = hours
        await self.session.flush()

    async def set_currency(self, room: Room, currency: str) -> None:
        currency = currency.strip().upper()
        if not (currency.isalpha() and 2 <= len(currency) <= 5):
            raise ServiceError("err-generic")
        await lock_room(self.session, room.id)
        room.currency = currency
        await self.session.flush()

    async def toggle_weekly_summary(self, room: Room) -> None:
        await self.set_weekly_summary(room, not room.weekly_summary)

    async def set_weekly_summary(self, room: Room, enabled: bool) -> None:
        await lock_room(self.session, room.id)
        room.weekly_summary = enabled
        await self.session.flush()

    async def migrate_chat(self, old_chat_id: int, new_chat_id: int) -> Room | None:
        """A group became a supergroup and got a new chat id."""
        room = await self.rooms.get_by_chat_id(old_chat_id)
        if room is None or await self.rooms.get_by_chat_id(new_chat_id) is not None:
            return None
        room.chat_id = new_chat_id
        await self.session.flush()
        return room

    async def deactivate(self, chat_id: int) -> None:
        room = await self.rooms.get_by_chat_id(chat_id)
        if room is not None:
            room.is_active = False
            await self.session.flush()

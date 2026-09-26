"""Mini App API, acting side for the room itself: settings, categories, roommates, export.

The rights are the bot's: room settings, changing or deleting categories and removing a
roommate are for chat admins and the room's creator (``ManageDep``, like /settings), while
anybody who lives in the room may add a category (/add_category), export (/export) or leave
(/leave). Joining is for whoever is in the room's group chat, like "I live here" there.

The same rules apply as in ``bot.webapi.actions``: one transaction holding the room's lock,
the services do the checks, ``Idempotency-Key`` protects from doing an action twice.
"""

from __future__ import annotations

from typing import Annotated

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from fastapi import APIRouter, HTTPException, Path, Request, status

from bot.announcements import announce_join, leave_text, plain, send_export
from bot.db.repositories import MemberRepo, UserRepo
from bot.i18n import Translator, default_category_names
from bot.notifications import Notifier
from bot.services.categories import CategoryService
from bot.services.errors import ServiceError
from bot.services.rooms import RoomService
from bot.utils.parsing import format_time
from bot.utils.text import esc
from bot.webapi.deps import ActionDep, InitDataDep, ManageDep, SessionDep, VisitDep
from bot.webapi.schemas import (
    ActionOut,
    ActiveRoomIn,
    CategoryIn,
    CategoryPatchIn,
    RoomSettingsIn,
)

router = APIRouter()

IdPath = Annotated[int, Path(ge=1)]


def reply(t: Translator, key: str, **kwargs: object) -> ActionOut:
    return ActionOut(message=plain(t(key, **kwargs)))


# --- the caller's rooms --------------------------------------------------------------------


@router.post("/me/room", response_model=ActionOut)
async def choose_room(
    request: Request, session: SessionDep, init: InitDataDep, body: ActiveRoomIn
) -> ActionOut:
    """The room switched to in the app is the one the bot's private chat works with (/room)."""
    rooms = await MemberRepo(session).rooms_of_user(init.user.id)
    chosen = next((room for room in rooms if room.id == body.room_id), None)
    user = await UserRepo(session).get(init.user.id)
    if chosen is None or user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Room not found")
    user.active_room_id = chosen.id
    await session.commit()
    notifier: Notifier = request.app.state.notifier
    return reply(notifier.translator(chosen), "room-picked", room=esc(chosen.name))


@router.post("/rooms/{room_id}/join", response_model=ActionOut)
async def join(visit: VisitDep) -> ActionOut:
    """ "I live here"."""
    tg = visit.user
    user = await UserRepo(visit.session).upsert(
        user_id=tg.id,
        first_name=tg.first_name,
        last_name=tg.last_name,
        username=tg.username,
        language_code=tg.language_code,
    )
    member, joined = await RoomService(visit.session).join(visit.room, user, visit.now)
    if not joined:
        return await visit.finish(reply(visit.t, "join-already"))
    await announce_join(visit.notifier, visit.room, member)
    return await visit.finish(reply(visit.t, "join-toast"))


@router.post("/rooms/{room_id}/leave", response_model=ActionOut)
async def leave(action: ActionDep) -> ActionOut:
    """The caller moves out: gone from every queue, the history stays."""
    await RoomService(action.session).leave(action.member)
    await action.notifier.send_group(action.room, leave_text(action.t, action.member))
    return await action.finish(reply(action.t, "app-left", room=esc(action.room.name)))


@router.post("/rooms/{room_id}/members/{member_id}/remove", response_model=ActionOut)
async def remove_member(action: ManageDep, member_id: IdPath) -> ActionOut:
    member = await MemberRepo(action.session).get(member_id)
    if member is None or member.room_id != action.room.id or not member.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Roommate not found")
    await RoomService(action.session).leave(member)
    await action.notifier.send_group(action.room, leave_text(action.t, member))
    return await action.finish(reply(action.t, "app-member-removed", name=esc(member.display_name)))


@router.post("/rooms/{room_id}/export", response_model=ActionOut)
async def export(action: ActionDep) -> ActionOut:
    """The CSV files go to the caller's private chat with the bot, as /export there."""
    try:
        await send_export(
            action.notifier.bot,
            action.session,
            action.room,
            action.t,
            action.member.telegram_user_id,
        )
    except (TelegramForbiddenError, TelegramBadRequest) as error:
        raise ServiceError("err-dm-needed") from error
    action.member.user.dm_available = True
    return await action.finish(reply(action.t, "app-export-sent"))


# --- settings ------------------------------------------------------------------------------


@router.patch("/rooms/{room_id}/settings", response_model=ActionOut)
async def update_settings(action: ManageDep, body: RoomSettingsIn) -> ActionOut:
    rooms, room, t = RoomService(action.session), action.room, action.t
    if body.language is not None and body.language != room.language:
        i18n = action.notifier.i18n
        await rooms.set_language(
            room,
            body.language,
            old_names=default_category_names(i18n, room.language),
            new_names=default_category_names(i18n, body.language),
        )
        t = i18n.get(body.language)
    if body.timezone is not None:
        await rooms.set_timezone(room, body.timezone.strip())
    if "quiet_hours" in body.model_fields_set:
        quiet = body.quiet_hours
        await rooms.set_quiet_hours(
            room, quiet.start if quiet else None, quiet.end if quiet else None
        )
    if body.repeat_after_hours is not None:
        await rooms.set_repeat_hours(room, body.repeat_after_hours)
    if body.currency is not None:
        await rooms.set_currency(room, body.currency)
    if body.weekly_summary is not None:
        await rooms.set_weekly_summary(room, body.weekly_summary)
    return await action.finish(reply(t, "toast-saved"))


# --- categories ----------------------------------------------------------------------------


@router.post("/rooms/{room_id}/categories", response_model=ActionOut)
async def add_category(action: ActionDep, body: CategoryIn) -> ActionOut:
    category = await CategoryService(action.session).create(
        action.room, name=body.name, emoji=body.emoji, now=action.now
    )
    return await action.finish(
        reply(
            action.t,
            "app-category-added",
            title=esc(category.title),
            time=format_time(category.reminder_time),
        )
    )


@router.patch("/rooms/{room_id}/categories/{category_id}", response_model=ActionOut)
async def update_category(
    action: ManageDep, category_id: IdPath, body: CategoryPatchIn
) -> ActionOut:
    service = CategoryService(action.session)
    category = await service.get(action.room, category_id)
    if body.name is not None:
        await service.rename(category, body.name)
    if body.emoji is not None:
        await service.set_emoji(category, body.emoji)
    if body.reminder_time is not None:
        await service.set_reminder_time(category, body.reminder_time)
    if body.reminder_days is not None:
        await service.set_days(category, body.reminder_days)
    if body.mode is not None and body.mode != category.queue_mode:
        await service.toggle_queue_mode(category)  # debts and credits start from scratch
    if body.is_active is not None and body.is_active != category.is_active:
        await service.set_active(category, body.is_active, action.now)
    return await action.finish(reply(action.t, "toast-saved"))


@router.delete("/rooms/{room_id}/categories/{category_id}", response_model=ActionOut)
async def delete_category(action: ManageDep, category_id: IdPath) -> ActionOut:
    """With its history and queue, as in the bot (disabling keeps them)."""
    service = CategoryService(action.session)
    category = await service.get(action.room, category_id)
    title = category.title
    await service.delete(category)
    return await action.finish(reply(action.t, "toast-category-deleted", title=esc(title)))

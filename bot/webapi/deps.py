"""FastAPI dependencies: database session, Telegram auth, room membership, actions, rights."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated

from aiogram import Bot
from fastapi import Depends, Header, HTTPException, Path, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from bot.db import Database
from bot.db.locks import lock_room
from bot.db.models import ApiRequest, Member, Room
from bot.db.repositories import ApiRequestRepo, MemberRepo, RoomRepo
from bot.i18n import Translator
from bot.notifications import Notifier
from bot.permissions import can_manage, is_in_chat
from bot.services.clock import utcnow
from bot.services.errors import ServiceError
from bot.webapi.auth import InitData, InitDataError, WebAppUser, parse_init_data

AUTH_SCHEME = "tma "
# Repeated requests with the same Idempotency-Key get the first response for this long.
IDEMPOTENCY_TTL = timedelta(days=1)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    db: Database = request.app.state.db
    async with db.session() as session:
        yield session


def get_init_data(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> InitData:
    """``Authorization: tma <Telegram.WebApp.initData>``, verified with the bot token."""
    settings: Settings = request.app.state.settings
    if not authorization or not authorization.startswith(AUTH_SCHEME):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Telegram initData required")
    try:
        return parse_init_data(
            authorization[len(AUTH_SCHEME) :],
            settings.bot_token.get_secret_value(),
            max_age=settings.webapp_initdata_max_age,
            now=utcnow(),
        )
    except InitDataError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


SessionDep = Annotated[AsyncSession, Depends(get_session)]
InitDataDep = Annotated[InitData, Depends(get_init_data)]
RoomIdDep = Annotated[int, Path(ge=1)]


async def load_membership(session: AsyncSession, user_id: int, room_id: int) -> tuple[Room, Member]:
    """The room and the caller's membership. 404 for strangers: rooms can't be probed."""
    room = await RoomRepo(session).get(room_id)
    member = await MemberRepo(session).get_by_user(room_id, user_id) if room else None
    if room is None or not room.is_active or member is None or not member.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Room not found")
    return room, member


async def get_membership(
    session: SessionDep, init: InitDataDep, room_id: RoomIdDep
) -> tuple[Room, Member]:
    return await load_membership(session, init.user.id, room_id)


MembershipDep = Annotated[tuple[Room, Member], Depends(get_membership)]


class ReplayedResponse(Exception):
    """The request was already carried out; answer with what was answered then."""

    def __init__(self, stored: ApiRequest) -> None:
        super().__init__(stored.key)
        self.status_code = stored.status_code
        self.body = stored.response


async def remember[M: BaseModel](
    session: AsyncSession, user_id: int, key: str | None, now: datetime, result: M
) -> M:
    """Commit, remembering the response for a repeated request with the same key."""
    if key:
        requests = ApiRequestRepo(session)
        await requests.prune(user_id, now - IDEMPOTENCY_TTL)
        await requests.add(
            ApiRequest(
                user_id=user_id,
                key=key,
                status_code=status.HTTP_200_OK,
                response=result.model_dump_json(),
                created_at=now,
            )
        )
    await session.commit()
    return result


async def replay_if_done(session: AsyncSession, user_id: int, key: str | None) -> None:
    """A request with this key was already carried out: answer as then (``ReplayedResponse``)."""
    if key:
        stored = await ApiRequestRepo(session).get(user_id, key)
        if stored is not None:
            raise ReplayedResponse(stored)


IdempotencyKey = Annotated[str | None, Header(min_length=8, max_length=64)]


@dataclass(slots=True)
class Action:
    """A change of a room requested by the Mini App.

    It runs in one transaction that holds the room's lock (see ``bot.db.locks``) from the very
    start, so it never interleaves with the bot or another request working on the same room.
    """

    session: AsyncSession
    room: Room
    member: Member
    notifier: Notifier
    t: Translator
    now: datetime
    key: str | None

    async def finish[M: BaseModel](self, result: M) -> M:
        user_id = self.member.telegram_user_id
        return await remember(self.session, user_id, self.key, self.now, result)


async def get_action(
    request: Request,
    session: SessionDep,
    init: InitDataDep,
    room_id: RoomIdDep,
    idempotency_key: IdempotencyKey = None,
) -> Action:
    await lock_room(session, room_id)
    room, member = await load_membership(session, init.user.id, room_id)
    notifier: Notifier = request.app.state.notifier
    t = notifier.translator(room)
    request.state.translator = t  # for the texts of service errors
    await replay_if_done(session, init.user.id, idempotency_key)
    return Action(
        session=session,
        room=room,
        member=member,
        notifier=notifier,
        t=t,
        now=utcnow(),
        key=idempotency_key,
    )


ActionDep = Annotated[Action, Depends(get_action)]


async def get_manage_action(action: ActionDep) -> Action:
    """An action only chat admins and the room's creator may take (as /settings in the bot).

    Telegram is asked every time, so taking admin rights away works at once.
    """
    if not await can_manage(action.notifier.bot, action.room, action.member.telegram_user_id):
        raise ServiceError("err-not-admin")
    return action


ManageDep = Annotated[Action, Depends(get_manage_action)]


@dataclass(slots=True)
class Visit:
    """A request to join a room from somebody who doesn't live there (yet).

    Like ``Action`` it holds the room's lock; the caller must be in the room's group chat,
    exactly like whoever presses "I live here" there.
    """

    session: AsyncSession
    room: Room
    user: WebAppUser
    notifier: Notifier
    t: Translator
    now: datetime
    key: str | None

    async def finish[M: BaseModel](self, result: M) -> M:
        return await remember(self.session, self.user.id, self.key, self.now, result)


async def get_visit(
    request: Request,
    session: SessionDep,
    init: InitDataDep,
    room_id: RoomIdDep,
    idempotency_key: IdempotencyKey = None,
) -> Visit:
    await lock_room(session, room_id)
    room = await RoomRepo(session).get(room_id)
    notifier: Notifier = request.app.state.notifier
    if room is None or not room.is_active or not await is_in_chat(notifier.bot, room, init.user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Room not found")
    t = notifier.translator(room)
    request.state.translator = t
    await replay_if_done(session, init.user.id, idempotency_key)
    return Visit(
        session=session,
        room=room,
        user=init.user,
        notifier=notifier,
        t=t,
        now=utcnow(),
        key=idempotency_key,
    )


VisitDep = Annotated[Visit, Depends(get_visit)]


class RightsCache:
    """``can_manage`` answers for the screens that show them, kept for a minute.

    The screens are refreshed every few seconds; actions always ask Telegram afresh.
    """

    TTL = timedelta(minutes=1)

    def __init__(self) -> None:
        self._answers: dict[tuple[int, int], tuple[bool, datetime]] = {}

    async def can_manage(self, bot: Bot, room: Room, user_id: int, now: datetime) -> bool:
        if room.created_by == user_id:
            return True
        cached = self._answers.get((room.id, user_id))
        if cached is not None and cached[1] > now:
            return cached[0]
        answer = await can_manage(bot, room, user_id)
        if len(self._answers) > 10_000:  # a lot of rooms: start over rather than grow
            self._answers.clear()
        self._answers[(room.id, user_id)] = (answer, now + self.TTL)
        return answer

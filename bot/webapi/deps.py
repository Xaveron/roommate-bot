"""FastAPI dependencies: database session, Telegram auth, room membership."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Path, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from bot.db import Database
from bot.db.models import Member, Room
from bot.db.repositories import MemberRepo, RoomRepo
from bot.services.clock import utcnow
from bot.webapi.auth import InitData, InitDataError, parse_init_data

AUTH_SCHEME = "tma "


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


async def get_membership(
    session: SessionDep,
    init: InitDataDep,
    room_id: Annotated[int, Path(ge=1)],
) -> tuple[Room, Member]:
    """The room and the caller's membership. 404 for strangers: rooms can't be probed."""
    room = await RoomRepo(session).get(room_id)
    member = await MemberRepo(session).get_by_user(room_id, init.user.id) if room else None
    if room is None or not room.is_active or member is None or not member.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Room not found")
    return room, member


MembershipDep = Annotated[tuple[Room, Member], Depends(get_membership)]

"""FastAPI application for the Telegram Mini App: JSON API under /api + the built frontend.

The Mini App acts on behalf of the bot, so it has its own Bot API client, but only to *send*
messages: it never asks Telegram for updates (only the bot process polls, or Telegram would
answer with "Conflict: terminated by other getUpdates request").
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from bot.announcements import plain
from bot.config import Settings, get_settings
from bot.db import Database
from bot.i18n import I18n, Translator
from bot.notifications import Notifier, create_bot
from bot.services.errors import ServiceError
from bot.webapi.actions import router as actions_router
from bot.webapi.deps import ReplayedResponse, RightsCache
from bot.webapi.manage import router as manage_router
from bot.webapi.routes import router

UNPROCESSABLE = 422

# HTTP status of business rule violations; everything else is 409 Conflict.
ERROR_STATUS = {
    "err-not-your-turn": status.HTTP_403_FORBIDDEN,
    "err-not-your-button": status.HTTP_403_FORBIDDEN,
    "err-settle-not-yours": status.HTTP_403_FORBIDDEN,
    "err-not-admin": status.HTTP_403_FORBIDDEN,
    "err-category-not-found": status.HTTP_404_NOT_FOUND,
    "err-bad-amount": UNPROCESSABLE,
    "err-bad-date": UNPROCESSABLE,
    "err-date-past": UNPROCESSABLE,
    "err-date-too-far": UNPROCESSABLE,
    "err-expense-nobody": UNPROCESSABLE,
    "err-buy-empty": UNPROCESSABLE,
    "err-category-name": UNPROCESSABLE,
    "err-category-emoji": UNPROCESSABLE,
    "err-no-days": UNPROCESSABLE,
    "err-bad-time": UNPROCESSABLE,
    "err-bad-time-range": UNPROCESSABLE,
    "err-bad-timezone": UNPROCESSABLE,
    "err-generic": UNPROCESSABLE,  # services raise it for values the bot's buttons never send
}


def create_app(
    settings: Settings | None = None,
    db: Database | None = None,
    notifier: Notifier | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    owns_db, owns_notifier = db is None, notifier is None
    database = db or Database(settings.database_url)
    notifier = notifier or Notifier(
        create_bot(settings.bot_token.get_secret_value()),
        I18n(default_locale=settings.default_language),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if owns_db:
            await database.dispose()
        if owns_notifier:
            await notifier.bot.session.close()

    app = FastAPI(
        title="RoomMate Mini App API",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.db = database
    app.state.notifier = notifier
    app.state.rights = RightsCache()

    @app.middleware("http")
    async def no_cache_for_api(request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, error: ServiceError) -> JSONResponse:
        t: Translator = getattr(request.state, "translator", None) or notifier.i18n.get(None)
        return JSONResponse(
            status_code=ERROR_STATUS.get(error.key, status.HTTP_409_CONFLICT),
            content={"detail": {"code": error.key, "message": plain(t(error.key, **error.args_))}},
        )

    @app.exception_handler(ReplayedResponse)
    async def replayed(_: Request, stored: ReplayedResponse) -> Response:
        return Response(
            content=stored.body,
            status_code=stored.status_code,
            media_type="application/json",
            headers={"Idempotent-Replayed": "true"},
        )

    app.include_router(router, prefix="/api")
    app.include_router(actions_router, prefix="/api")
    app.include_router(manage_router, prefix="/api")
    dist = Path(settings.webapp_dist)
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app

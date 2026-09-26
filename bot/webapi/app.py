"""FastAPI application for the Telegram Mini App: JSON API under /api + the built frontend."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from bot.config import Settings, get_settings
from bot.db import Database
from bot.webapi.routes import router


def create_app(settings: Settings | None = None, db: Database | None = None) -> FastAPI:
    settings = settings or get_settings()
    owns_db = db is None
    database = db or Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if owns_db:
            await database.dispose()

    app = FastAPI(
        title="RoomMate Mini App API",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.db = database

    @app.middleware("http")
    async def no_cache_for_api(request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(router, prefix="/api")
    dist = Path(settings.webapp_dist)
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app

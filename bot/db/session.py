"""Database engine and session management."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def is_sqlite(url: str) -> bool:
    return make_url(url).get_backend_name() == "sqlite"


def ensure_sqlite_dir(url: str) -> None:
    """Create the directory of a file-based SQLite database if needed."""
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite" and parsed.database not in (None, "", ":memory:"):
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_engine(url: str, **kwargs: Any) -> AsyncEngine:
    ensure_sqlite_dir(url)
    engine = create_async_engine(url, **kwargs)
    if is_sqlite(url):
        event.listen(engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    return engine


class Database:
    """Owns the engine and hands out sessions.

    SQLite allows a single writer, and interleaved async transactions easily end up with
    "database is locked" errors, so with SQLite every unit of work is serialized through one
    lock. PostgreSQL runs units of work concurrently and relies on row locks instead.
    """

    def __init__(self, url: str, *, engine: AsyncEngine | None = None, **engine_kwargs: Any):
        self.url = url
        self.engine = engine or create_engine(url, **engine_kwargs)
        self.sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)
        self._lock = asyncio.Lock() if is_sqlite(url) else None

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Session for one unit of work. The caller commits; errors roll back."""
        if self._lock is not None:
            await self._lock.acquire()
        try:
            async with self.sessionmaker() as session:
                try:
                    yield session
                except BaseException:
                    await session.rollback()
                    raise
        finally:
            if self._lock is not None:
                self._lock.release()

    async def dispose(self) -> None:
        await self.engine.dispose()

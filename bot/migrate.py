"""Apply Alembic migrations programmatically (used on startup and in tests)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from bot.db.session import ensure_sqlite_dir

ROOT = Path(__file__).resolve().parent.parent


def alembic_config(database_url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.attributes["database_url"] = database_url
    config.attributes["configure_logger"] = False
    return config


def upgrade(database_url: str, revision: str = "head") -> None:
    ensure_sqlite_dir(database_url)
    command.upgrade(alembic_config(database_url), revision)

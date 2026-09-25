"""Application settings loaded from environment variables / .env file."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

SUPPORTED_LANGUAGES = ("ru", "ro", "en")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: SecretStr
    database_url: str = "sqlite+aiosqlite:///./data/roommate.db"
    default_timezone: str = "Europe/Chisinau"
    default_language: str = "ru"
    # Telegram user ids of bot owners (comma-separated); they get access to /admin.
    admin_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    log_level: str = "INFO"
    # How often the scheduler checks whether reminders are due.
    scheduler_tick_seconds: int = Field(default=60, ge=10, le=600)
    # Apply Alembic migrations automatically on startup.
    auto_migrate: bool = True

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _split_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return [int(part) for part in value.replace(" ", "").split(",") if part]
        if isinstance(value, int):
            return [value]
        return value

    @field_validator("default_timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown timezone: {value}") from exc
        return value

    @field_validator("default_language")
    @classmethod
    def _check_language(cls, value: str) -> str:
        if value not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Language must be one of {SUPPORTED_LANGUAGES}")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

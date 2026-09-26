"""Alembic migrations create exactly the schema described by the models."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from bot.db.models import Base
from bot.migrate import alembic_config, upgrade
from tests.conftest import TEST_DATABASE_URL


def test_upgrade_matches_models_and_downgrade_works(tmp_path: Path):
    path = tmp_path / "roommate.db"
    upgrade(f"sqlite+aiosqlite:///{path}")

    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        diff = compare_metadata(context, Base.metadata)
    assert diff == [], f"models and migrations differ: {diff}"

    command.downgrade(alembic_config(f"sqlite+aiosqlite:///{path}"), "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()


def test_stage_one_database_with_data_upgrades(tmp_path: Path):
    """A database created by the stage 1 release keeps its data after the upgrade."""
    path = tmp_path / "old.db"
    url = f"sqlite+aiosqlite:///{path}"
    upgrade(url, "0001")

    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        for statement in (
            "INSERT INTO rooms (id, chat_id, name, language, timezone, is_active, created_at) "
            "VALUES (1, -100, '906B', 'ru', 'Europe/Chisinau', 1, '2026-09-01 10:00:00')",
            "INSERT INTO users (id, first_name, dm_available, created_at) "
            "VALUES (7, 'Аня', 1, '2026-09-01 10:00:00')",
            "INSERT INTO members (id, room_id, telegram_user_id, is_active, joined_at) "
            "VALUES (1, 1, 7, 1, '2026-09-01 10:00:00')",
            "INSERT INTO categories (id, room_id, kind, name, emoji, reminder_time, "
            "reminder_days, queue_mode, is_active, sort_order, created_at) VALUES "
            "(1, 1, 'bread', 'Хлеб', '🍞', '18:00:00', '0123456', 'round_robin', 1, 0, "
            "'2026-09-01 10:00:00')",
            "INSERT INTO duties (id, category_id, member_id, status, created_at) "
            "VALUES (1, 1, 1, 'done', '2026-09-02 18:30:00')",
        ):
            connection.execute(text(statement))

    upgrade(url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT repeat_after_hours FROM rooms")).scalar() == 3
        assert connection.execute(text("SELECT review FROM duties")).scalar() == "open"
        assert connection.execute(text("SELECT name FROM categories")).scalar() == "Хлеб"
        assert connection.execute(text("SELECT count(*) FROM duty_votes")).scalar() == 0
    engine.dispose()


def test_stage_two_database_with_data_upgrades(tmp_path: Path):
    """Stage 2 -> 3: decimal duty amounts become cents, rooms get currency defaults."""
    path = tmp_path / "stage2.db"
    url = f"sqlite+aiosqlite:///{path}"
    upgrade(url, "0002")

    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as connection:
        for statement in (
            "INSERT INTO rooms (id, chat_id, name, language, timezone, is_active, created_at, "
            "repeat_after_hours) VALUES (1, -100, '906B', 'ro', 'Europe/Chisinau', 1, "
            "'2026-09-01 10:00:00', 2)",
            "INSERT INTO users (id, first_name, dm_available, created_at) "
            "VALUES (7, 'Ana', 1, '2026-09-01 10:00:00')",
            "INSERT INTO members (id, room_id, telegram_user_id, is_active, joined_at) "
            "VALUES (1, 1, 7, 1, '2026-09-01 10:00:00')",
            "INSERT INTO categories (id, room_id, kind, name, emoji, reminder_time, "
            "reminder_days, queue_mode, is_active, sort_order, created_at) VALUES "
            "(1, 1, 'bread', 'Pâine', '🍞', '18:00:00', '0123456', 'fair', 1, 0, "
            "'2026-09-01 10:00:00')",
            "INSERT INTO duties (id, category_id, member_id, status, amount, created_at, review) "
            "VALUES (1, 1, 1, 'done', 23.5, '2026-09-02 18:30:00', 'confirmed')",
        ):
            connection.execute(text(statement))

    upgrade(url)
    with engine.connect() as connection:
        room = connection.execute(
            text("SELECT currency, weekly_summary, repeat_after_hours FROM rooms")
        ).one()
        assert tuple(room) == ("MDL", 1, 2)
        duty = connection.execute(text("SELECT amount_cents, review FROM duties")).one()
        assert tuple(duty) == (2350, "confirmed")
        assert connection.execute(text("SELECT count(*) FROM expenses")).scalar() == 0
    engine.dispose()


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="needs TEST_DATABASE_URL (PostgreSQL)")
def test_migrations_on_postgresql():
    """Upgrade to head on a real PostgreSQL, compare with the models, downgrade to base."""
    url = TEST_DATABASE_URL
    assert url is not None

    async def run(work):
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                return await connection.run_sync(work)
        finally:
            await engine.dispose()

    def reset(connection):
        Base.metadata.drop_all(connection)
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))

    def compare(connection):
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        return compare_metadata(context, Base.metadata)

    def tables(connection):
        return set(inspect(connection).get_table_names())

    asyncio.run(run(reset))
    try:
        upgrade(url)
        diff = asyncio.run(run(compare))
        assert diff == [], f"models and migrations differ on PostgreSQL: {diff}"
        command.downgrade(alembic_config(url), "base")
        assert asyncio.run(run(tables)) == {"alembic_version"}
    finally:
        asyncio.run(run(reset))

"""Alembic migrations create exactly the schema described by the models."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from bot.db.models import Base
from bot.migrate import alembic_config, upgrade


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

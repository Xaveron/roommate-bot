"""Alembic migrations create exactly the schema described by the models."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

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

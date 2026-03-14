"""Helpers for running Alembic migrations against the runtime database."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from codeman.infrastructure.persistence.sqlite.engine import build_sqlite_url


def project_root() -> Path:
    """Return the repository root for migration resources."""

    return Path(__file__).resolve().parents[5]


def build_alembic_config(database_path: Path) -> Config:
    """Build an Alembic config pointing at the runtime database."""

    root = project_root()
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", build_sqlite_url(database_path))
    return config


def upgrade_database(database_path: Path) -> None:
    """Apply all runtime metadata migrations."""

    command.upgrade(build_alembic_config(database_path), "head")

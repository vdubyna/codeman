"""SQLite engine helpers."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def build_sqlite_url(database_path: Path) -> str:
    """Build a SQLAlchemy URL for the runtime metadata database."""

    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


def create_sqlite_engine(database_path: Path) -> Engine:
    """Create a SQLAlchemy engine for the runtime metadata database."""

    return create_engine(build_sqlite_url(database_path), future=True)

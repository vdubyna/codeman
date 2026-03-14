"""SQLAlchemy Core table metadata for runtime persistence."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, MetaData, String, Table

metadata = MetaData()

repositories_table = Table(
    "repositories",
    metadata,
    Column("id", String(length=32), primary_key=True),
    Column("repository_name", String(length=255), nullable=False),
    Column("canonical_path", String(length=2048), nullable=False, unique=True),
    Column("requested_path", String(length=2048), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

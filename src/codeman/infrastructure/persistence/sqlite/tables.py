"""SQLAlchemy Core table metadata for runtime persistence."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

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

snapshots_table = Table(
    "snapshots",
    metadata,
    Column("id", String(length=32), primary_key=True),
    Column("repository_id", String(length=32), ForeignKey("repositories.id"), nullable=False),
    Column("revision_identity", String(length=255), nullable=False),
    Column("revision_source", String(length=64), nullable=False),
    Column("manifest_path", String(length=2048), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("source_inventory_extracted_at", DateTime(timezone=True), nullable=True),
    Column("chunk_generation_completed_at", DateTime(timezone=True), nullable=True),
    Column("indexing_config_fingerprint", String(length=64), nullable=True),
)

source_files_table = Table(
    "source_files",
    metadata,
    Column("id", String(length=64), primary_key=True),
    Column("snapshot_id", String(length=32), ForeignKey("snapshots.id"), nullable=False),
    Column("repository_id", String(length=32), ForeignKey("repositories.id"), nullable=False),
    Column("relative_path", String(length=2048), nullable=False),
    Column("language", String(length=32), nullable=False),
    Column("content_hash", String(length=64), nullable=False),
    Column("byte_size", Integer(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "snapshot_id",
        "relative_path",
        name="uq_source_files_snapshot_relative_path",
    ),
)

chunks_table = Table(
    "chunks",
    metadata,
    Column("id", String(length=64), primary_key=True),
    Column("snapshot_id", String(length=32), ForeignKey("snapshots.id"), nullable=False),
    Column("repository_id", String(length=32), ForeignKey("repositories.id"), nullable=False),
    Column("source_file_id", String(length=64), ForeignKey("source_files.id"), nullable=False),
    Column("relative_path", String(length=2048), nullable=False),
    Column("language", String(length=32), nullable=False),
    Column("strategy", String(length=64), nullable=False),
    Column("serialization_version", String(length=16), nullable=False),
    Column("source_content_hash", String(length=64), nullable=False),
    Column("start_line", Integer(), nullable=False),
    Column("end_line", Integer(), nullable=False),
    Column("start_byte", Integer(), nullable=False),
    Column("end_byte", Integer(), nullable=False),
    Column("payload_path", String(length=2048), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

reindex_runs_table = Table(
    "reindex_runs",
    metadata,
    Column("id", String(length=32), primary_key=True),
    Column("repository_id", String(length=32), ForeignKey("repositories.id"), nullable=False),
    Column(
        "previous_snapshot_id",
        String(length=32),
        ForeignKey("snapshots.id"),
        nullable=False,
    ),
    Column(
        "result_snapshot_id",
        String(length=32),
        ForeignKey("snapshots.id"),
        nullable=False,
    ),
    Column("previous_revision_identity", String(length=255), nullable=False),
    Column("result_revision_identity", String(length=255), nullable=False),
    Column("previous_config_fingerprint", String(length=64), nullable=False),
    Column("current_config_fingerprint", String(length=64), nullable=False),
    Column("change_reason", String(length=64), nullable=False),
    Column("source_files_reused", Integer(), nullable=False),
    Column("source_files_rebuilt", Integer(), nullable=False),
    Column("source_files_removed", Integer(), nullable=False),
    Column("chunks_reused", Integer(), nullable=False),
    Column("chunks_rebuilt", Integer(), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

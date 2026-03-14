"""SQLite adapter for generated chunk metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from codeman.application.ports.chunk_store_port import ChunkStorePort
from codeman.contracts.chunking import ChunkRecord
from codeman.infrastructure.persistence.sqlite.migrations import upgrade_database
from codeman.infrastructure.persistence.sqlite.tables import chunks_table


@dataclass(slots=True)
class SqliteChunkStore(ChunkStorePort):
    """Persist retrieval chunk metadata in the runtime SQLite database."""

    engine: Engine
    database_path: Path

    def initialize(self) -> None:
        """Ensure the runtime metadata schema is up to date."""

        upgrade_database(self.database_path)

    def upsert_chunks(self, chunks: Sequence[ChunkRecord]) -> list[ChunkRecord]:
        """Persist chunk rows and return the stored records ordered by path and span."""

        if not chunks:
            return []

        insert_statement = sqlite_insert(chunks_table).values(
            [
                {
                    "id": record.chunk_id,
                    "snapshot_id": record.snapshot_id,
                    "repository_id": record.repository_id,
                    "source_file_id": record.source_file_id,
                    "relative_path": record.relative_path,
                    "language": record.language,
                    "strategy": record.strategy,
                    "serialization_version": record.serialization_version,
                    "source_content_hash": record.source_content_hash,
                    "start_line": record.start_line,
                    "end_line": record.end_line,
                    "start_byte": record.start_byte,
                    "end_byte": record.end_byte,
                    "payload_path": str(record.payload_path),
                    "created_at": record.created_at,
                }
                for record in chunks
            ]
        )
        statement = insert_statement.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "strategy": insert_statement.excluded.strategy,
                "serialization_version": insert_statement.excluded.serialization_version,
                "source_content_hash": insert_statement.excluded.source_content_hash,
                "start_line": insert_statement.excluded.start_line,
                "end_line": insert_statement.excluded.end_line,
                "start_byte": insert_statement.excluded.start_byte,
                "end_byte": insert_statement.excluded.end_byte,
                "payload_path": insert_statement.excluded.payload_path,
                "created_at": insert_statement.excluded.created_at,
            },
        )

        snapshot_id = chunks[0].snapshot_id
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        query = (
            select(chunks_table)
            .where(
                chunks_table.c.snapshot_id == snapshot_id,
                chunks_table.c.id.in_(chunk_ids),
            )
            .order_by(
                chunks_table.c.relative_path.asc(),
                chunks_table.c.start_line.asc(),
                chunks_table.c.start_byte.asc(),
            )
        )

        with self.engine.begin() as connection:
            connection.execute(statement)
            rows = connection.execute(query).mappings().all()

        return [self._row_to_record(row) for row in rows]

    def list_by_snapshot(self, snapshot_id: str) -> list[ChunkRecord]:
        """Return chunk rows for a snapshot ordered by path and span."""

        if not self.database_path.exists():
            return []

        query = (
            select(chunks_table)
            .where(chunks_table.c.snapshot_id == snapshot_id)
            .order_by(
                chunks_table.c.relative_path.asc(),
                chunks_table.c.start_line.asc(),
                chunks_table.c.start_byte.asc(),
            )
        )
        with self.engine.begin() as connection:
            rows = connection.execute(query).mappings().all()

        return [self._row_to_record(row) for row in rows]

    @staticmethod
    def _row_to_record(row: Any) -> ChunkRecord:
        """Convert a row mapping into a chunk metadata DTO."""

        return ChunkRecord(
            chunk_id=row["id"],
            snapshot_id=row["snapshot_id"],
            repository_id=row["repository_id"],
            source_file_id=row["source_file_id"],
            relative_path=row["relative_path"],
            language=row["language"],
            strategy=row["strategy"],
            serialization_version=row["serialization_version"],
            source_content_hash=row["source_content_hash"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            start_byte=row["start_byte"],
            end_byte=row["end_byte"],
            payload_path=Path(row["payload_path"]),
            created_at=row["created_at"],
        )

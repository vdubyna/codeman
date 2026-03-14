"""SQLite adapter for source-file inventory metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from codeman.application.ports.source_inventory_port import SourceInventoryStorePort
from codeman.contracts.repository import SourceFileRecord
from codeman.infrastructure.persistence.sqlite.migrations import upgrade_database
from codeman.infrastructure.persistence.sqlite.tables import source_files_table


@dataclass(slots=True)
class SqliteSourceInventoryStore(SourceInventoryStorePort):
    """Persist extracted source-file metadata in the runtime SQLite database."""

    engine: Engine
    database_path: Path

    def initialize(self) -> None:
        """Ensure the runtime metadata schema is up to date."""

        upgrade_database(self.database_path)

    def upsert_source_files(
        self,
        source_files: Sequence[SourceFileRecord],
    ) -> list[SourceFileRecord]:
        """Insert source-file rows and return the stored records for the snapshot."""

        if not source_files:
            return []

        statement = sqlite_insert(source_files_table).values(
            [
                {
                    "id": record.source_file_id,
                    "snapshot_id": record.snapshot_id,
                    "repository_id": record.repository_id,
                    "relative_path": record.relative_path,
                    "language": record.language,
                    "content_hash": record.content_hash,
                    "byte_size": record.byte_size,
                    "created_at": record.discovered_at,
                }
                for record in source_files
            ]
        ).on_conflict_do_nothing(
            index_elements=["snapshot_id", "relative_path"],
        )

        snapshot_id = source_files[0].snapshot_id
        relative_paths = [record.relative_path for record in source_files]
        query = (
            select(source_files_table)
            .where(
                source_files_table.c.snapshot_id == snapshot_id,
                source_files_table.c.relative_path.in_(relative_paths),
            )
            .order_by(source_files_table.c.relative_path.asc())
        )

        with self.engine.begin() as connection:
            connection.execute(statement)
            rows = connection.execute(query).mappings().all()

        return [self._row_to_record(row) for row in rows]

    @staticmethod
    def _row_to_record(row: Any) -> SourceFileRecord:
        """Convert a row mapping into a source-file contract DTO."""

        return SourceFileRecord(
            source_file_id=row["id"],
            snapshot_id=row["snapshot_id"],
            repository_id=row["repository_id"],
            relative_path=row["relative_path"],
            language=row["language"],
            content_hash=row["content_hash"],
            byte_size=row["byte_size"],
            discovered_at=row["created_at"],
        )

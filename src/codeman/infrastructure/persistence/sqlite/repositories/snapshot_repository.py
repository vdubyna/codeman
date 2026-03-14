"""SQLite adapter for immutable snapshot metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine

from codeman.application.ports.snapshot_port import SnapshotMetadataStorePort
from codeman.contracts.repository import SnapshotRecord
from codeman.infrastructure.persistence.sqlite.migrations import upgrade_database
from codeman.infrastructure.persistence.sqlite.tables import snapshots_table


@dataclass(slots=True)
class SqliteSnapshotMetadataStore(SnapshotMetadataStorePort):
    """Persist snapshot metadata in the runtime SQLite database."""

    engine: Engine
    database_path: Path

    def initialize(self) -> None:
        """Ensure the runtime metadata schema is up to date."""

        upgrade_database(self.database_path)

    def get_by_snapshot_id(self, snapshot_id: str) -> SnapshotRecord | None:
        """Look up a snapshot by its persisted identifier."""

        if not self.database_path.exists():
            return None

        query = select(snapshots_table).where(snapshots_table.c.id == snapshot_id)
        with self.engine.begin() as connection:
            row = connection.execute(query).mappings().first()

        if row is None:
            return None

        return self._row_to_record(row)

    def create_snapshot(
        self,
        *,
        snapshot_id: str,
        repository_id: str,
        revision_identity: str,
        revision_source: str,
        manifest_path: Path,
        created_at: datetime,
    ) -> SnapshotRecord:
        """Persist a snapshot metadata row."""

        statement = insert(snapshots_table).values(
            id=snapshot_id,
            repository_id=repository_id,
            revision_identity=revision_identity,
            revision_source=revision_source,
            manifest_path=str(manifest_path),
            created_at=created_at,
            source_inventory_extracted_at=None,
        )
        with self.engine.begin() as connection:
            connection.execute(statement)

        return SnapshotRecord(
            snapshot_id=snapshot_id,
            repository_id=repository_id,
            revision_identity=revision_identity,
            revision_source=revision_source,
            manifest_path=manifest_path,
            created_at=created_at,
            source_inventory_extracted_at=None,
        )

    def mark_source_inventory_extracted(
        self,
        *,
        snapshot_id: str,
        extracted_at: datetime,
    ) -> None:
        """Record that source inventory extraction completed for a snapshot."""

        statement = (
            update(snapshots_table)
            .where(snapshots_table.c.id == snapshot_id)
            .values(source_inventory_extracted_at=extracted_at)
        )
        with self.engine.begin() as connection:
            connection.execute(statement)

    @staticmethod
    def _row_to_record(row: Any) -> SnapshotRecord:
        """Convert a row mapping into a snapshot contract DTO."""

        return SnapshotRecord(
            snapshot_id=row["id"],
            repository_id=row["repository_id"],
            revision_identity=row["revision_identity"],
            revision_source=row["revision_source"],
            manifest_path=Path(row["manifest_path"]),
            created_at=row["created_at"],
            source_inventory_extracted_at=row["source_inventory_extracted_at"],
        )

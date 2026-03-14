"""SQLite adapter for immutable snapshot metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import insert
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
        )

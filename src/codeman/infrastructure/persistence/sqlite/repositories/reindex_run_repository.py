"""SQLite adapter for attributable re-index run metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import insert
from sqlalchemy.engine import Engine

from codeman.application.ports.reindex_run_store_port import ReindexRunStorePort
from codeman.contracts.reindexing import ChangeReason, ReindexRunRecord
from codeman.infrastructure.persistence.sqlite.migrations import upgrade_database
from codeman.infrastructure.persistence.sqlite.tables import reindex_runs_table


@dataclass(slots=True)
class SqliteReindexRunStore(ReindexRunStorePort):
    """Persist attributable re-index run records in SQLite."""

    engine: Engine
    database_path: Path

    def initialize(self) -> None:
        """Ensure the runtime metadata schema is up to date."""

        upgrade_database(self.database_path)

    def create_run(
        self,
        *,
        repository_id: str,
        previous_snapshot_id: str,
        result_snapshot_id: str,
        previous_revision_identity: str,
        result_revision_identity: str,
        previous_config_fingerprint: str,
        current_config_fingerprint: str,
        change_reason: ChangeReason,
        source_files_reused: int,
        source_files_rebuilt: int,
        source_files_removed: int,
        chunks_reused: int,
        chunks_rebuilt: int,
        created_at: datetime,
    ) -> ReindexRunRecord:
        """Persist a re-index run and return the stored DTO."""

        run_id = uuid4().hex
        statement = insert(reindex_runs_table).values(
            id=run_id,
            repository_id=repository_id,
            previous_snapshot_id=previous_snapshot_id,
            result_snapshot_id=result_snapshot_id,
            previous_revision_identity=previous_revision_identity,
            result_revision_identity=result_revision_identity,
            previous_config_fingerprint=previous_config_fingerprint,
            current_config_fingerprint=current_config_fingerprint,
            change_reason=change_reason,
            source_files_reused=source_files_reused,
            source_files_rebuilt=source_files_rebuilt,
            source_files_removed=source_files_removed,
            chunks_reused=chunks_reused,
            chunks_rebuilt=chunks_rebuilt,
            created_at=created_at,
        )
        with self.engine.begin() as connection:
            connection.execute(statement)

        return ReindexRunRecord(
            run_id=run_id,
            repository_id=repository_id,
            previous_snapshot_id=previous_snapshot_id,
            result_snapshot_id=result_snapshot_id,
            previous_revision_identity=previous_revision_identity,
            result_revision_identity=result_revision_identity,
            previous_config_fingerprint=previous_config_fingerprint,
            current_config_fingerprint=current_config_fingerprint,
            change_reason=change_reason,
            source_files_reused=source_files_reused,
            source_files_rebuilt=source_files_rebuilt,
            source_files_removed=source_files_removed,
            chunks_reused=chunks_reused,
            chunks_rebuilt=chunks_rebuilt,
            created_at=created_at,
        )

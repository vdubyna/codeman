"""SQLite adapter for lexical index-build attribution records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import desc, exists, insert, select
from sqlalchemy.engine import Engine

from codeman.application.ports.index_build_store_port import IndexBuildStorePort
from codeman.contracts.retrieval import LexicalIndexBuildRecord
from codeman.infrastructure.persistence.sqlite.migrations import upgrade_database
from codeman.infrastructure.persistence.sqlite.tables import (
    chunks_table,
    lexical_index_builds_table,
    snapshots_table,
)


@dataclass(slots=True)
class SqliteIndexBuildStore(IndexBuildStorePort):
    """Persist lexical index-build metadata in the runtime SQLite database."""

    engine: Engine
    database_path: Path

    def initialize(self) -> None:
        """Ensure the runtime metadata schema is up to date."""

        upgrade_database(self.database_path)

    def create_build(self, build: LexicalIndexBuildRecord) -> LexicalIndexBuildRecord:
        """Persist one lexical index-build record."""

        statement = insert(lexical_index_builds_table).values(
            id=build.build_id,
            repository_id=build.repository_id,
            snapshot_id=build.snapshot_id,
            revision_identity=build.revision_identity,
            revision_source=build.revision_source,
            indexing_config_fingerprint=build.indexing_config_fingerprint,
            lexical_engine=build.lexical_engine,
            tokenizer_spec=build.tokenizer_spec,
            indexed_fields_json=json.dumps(build.indexed_fields),
            chunks_indexed=build.chunks_indexed,
            index_path=str(build.index_path),
            created_at=build.created_at,
        )
        with self.engine.begin() as connection:
            connection.execute(statement)

        return build

    def get_latest_build_for_snapshot(
        self,
        snapshot_id: str,
    ) -> LexicalIndexBuildRecord | None:
        """Return the latest lexical-index build for a snapshot."""

        if not self.database_path.exists():
            return None

        query = (
            select(lexical_index_builds_table)
            .where(lexical_index_builds_table.c.snapshot_id == snapshot_id)
            .order_by(
                desc(lexical_index_builds_table.c.created_at),
                desc(lexical_index_builds_table.c.id),
            )
            .limit(1)
        )
        with self.engine.begin() as connection:
            row = connection.execute(query).mappings().first()

        if row is None:
            return None

        return self._row_to_record(row)

    def get_latest_build_for_repository(
        self,
        repository_id: str,
        indexing_config_fingerprint: str,
    ) -> LexicalIndexBuildRecord | None:
        """Return the current lexical-index build for the latest indexed snapshot/config pair."""

        if not self.database_path.exists():
            return None

        chunk_rows_exist = exists(
            select(chunks_table.c.id).where(chunks_table.c.snapshot_id == snapshots_table.c.id),
        )
        snapshot_query = (
            select(snapshots_table.c.id)
            .where(
                snapshots_table.c.repository_id == repository_id,
                snapshots_table.c.source_inventory_extracted_at.is_not(None),
                (
                    snapshots_table.c.chunk_generation_completed_at.is_not(None)
                    | chunk_rows_exist
                ),
            )
            .order_by(
                desc(snapshots_table.c.created_at),
                desc(snapshots_table.c.id),
            )
            .limit(1)
        )
        with self.engine.begin() as connection:
            snapshot_row = connection.execute(snapshot_query).mappings().first()

            if snapshot_row is None:
                return None

            row = connection.execute(
                select(lexical_index_builds_table)
                .where(
                    lexical_index_builds_table.c.repository_id == repository_id,
                    lexical_index_builds_table.c.snapshot_id == snapshot_row["id"],
                    lexical_index_builds_table.c.indexing_config_fingerprint
                    == indexing_config_fingerprint,
                )
                .order_by(
                    desc(lexical_index_builds_table.c.created_at),
                    desc(lexical_index_builds_table.c.id),
                )
                .limit(1)
            ).mappings().first()

        if row is None:
            return None

        return self._row_to_record(row)

    @staticmethod
    def _row_to_record(row: Any) -> LexicalIndexBuildRecord:
        """Convert a row mapping into an index-build DTO."""

        return LexicalIndexBuildRecord(
            build_id=row["id"],
            repository_id=row["repository_id"],
            snapshot_id=row["snapshot_id"],
            revision_identity=row["revision_identity"],
            revision_source=row["revision_source"],
            indexing_config_fingerprint=row["indexing_config_fingerprint"],
            lexical_engine=row["lexical_engine"],
            tokenizer_spec=row["tokenizer_spec"],
            indexed_fields=list(json.loads(row["indexed_fields_json"])),
            chunks_indexed=row["chunks_indexed"],
            index_path=Path(row["index_path"]),
            created_at=row["created_at"],
        )

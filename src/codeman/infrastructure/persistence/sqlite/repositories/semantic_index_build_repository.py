"""SQLite adapter for semantic index-build attribution records."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import desc, exists, insert, select
from sqlalchemy.engine import Engine

from codeman.application.ports.semantic_index_build_store_port import (
    SemanticIndexBuildStorePort,
)
from codeman.contracts.retrieval import SemanticIndexBuildRecord
from codeman.infrastructure.persistence.sqlite.migrations import upgrade_database
from codeman.infrastructure.persistence.sqlite.tables import (
    chunks_table,
    semantic_index_builds_table,
    snapshots_table,
)


@dataclass(slots=True)
class SqliteSemanticIndexBuildStore(SemanticIndexBuildStorePort):
    """Persist semantic index-build metadata in the runtime SQLite database."""

    engine: Engine
    database_path: Path

    def initialize(self) -> None:
        """Ensure the runtime metadata schema is up to date."""

        upgrade_database(self.database_path)

    def create_build(self, build: SemanticIndexBuildRecord) -> SemanticIndexBuildRecord:
        """Persist one semantic index-build record."""

        statement = insert(semantic_index_builds_table).values(
            id=build.build_id,
            repository_id=build.repository_id,
            snapshot_id=build.snapshot_id,
            revision_identity=build.revision_identity,
            revision_source=build.revision_source,
            semantic_config_fingerprint=build.semantic_config_fingerprint,
            provider_id=build.provider_id,
            model_id=build.model_id,
            model_version=build.model_version,
            is_external_provider=1 if build.is_external_provider else 0,
            vector_engine=build.vector_engine,
            document_count=build.document_count,
            embedding_dimension=build.embedding_dimension,
            build_duration_ms=build.build_duration_ms,
            artifact_path=str(build.artifact_path),
            created_at=build.created_at,
        )
        with self.engine.begin() as connection:
            connection.execute(statement)

        return build

    def get_latest_build_for_snapshot(
        self,
        snapshot_id: str,
        semantic_config_fingerprint: str,
    ) -> SemanticIndexBuildRecord | None:
        """Return the latest semantic-index build for a snapshot/config pair."""

        if not self.database_path.exists():
            return None

        query = (
            select(semantic_index_builds_table)
            .where(
                semantic_index_builds_table.c.snapshot_id == snapshot_id,
                semantic_index_builds_table.c.semantic_config_fingerprint
                == semantic_config_fingerprint,
            )
            .order_by(
                desc(semantic_index_builds_table.c.created_at),
                desc(semantic_index_builds_table.c.id),
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
        semantic_config_fingerprint: str,
    ) -> SemanticIndexBuildRecord | None:
        """Return the current semantic build for the latest indexed snapshot/config pair."""

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
                (snapshots_table.c.chunk_generation_completed_at.is_not(None) | chunk_rows_exist),
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

            row = (
                connection.execute(
                    select(semantic_index_builds_table)
                    .where(
                        semantic_index_builds_table.c.repository_id == repository_id,
                        semantic_index_builds_table.c.snapshot_id == snapshot_row["id"],
                        semantic_index_builds_table.c.semantic_config_fingerprint
                        == semantic_config_fingerprint,
                    )
                    .order_by(
                        desc(semantic_index_builds_table.c.created_at),
                        desc(semantic_index_builds_table.c.id),
                    )
                    .limit(1)
                )
                .mappings()
                .first()
            )

        if row is None:
            return None

        return self._row_to_record(row)

    def get_by_build_id(self, build_id: str) -> SemanticIndexBuildRecord | None:
        """Return one semantic-index build by its stable identifier."""

        if not self.database_path.exists():
            return None

        query = select(semantic_index_builds_table).where(
            semantic_index_builds_table.c.id == build_id
        )
        with self.engine.begin() as connection:
            row = connection.execute(query).mappings().first()

        if row is None:
            return None

        return self._row_to_record(row)

    @staticmethod
    def _row_to_record(row: Any) -> SemanticIndexBuildRecord:
        """Convert a row mapping into a semantic index-build DTO."""

        return SemanticIndexBuildRecord(
            build_id=row["id"],
            repository_id=row["repository_id"],
            snapshot_id=row["snapshot_id"],
            revision_identity=row["revision_identity"],
            revision_source=row["revision_source"],
            semantic_config_fingerprint=row["semantic_config_fingerprint"],
            provider_id=row["provider_id"],
            model_id=row["model_id"],
            model_version=row["model_version"],
            is_external_provider=bool(row["is_external_provider"]),
            vector_engine=row["vector_engine"],
            document_count=row["document_count"],
            embedding_dimension=row["embedding_dimension"],
            build_duration_ms=row["build_duration_ms"],
            artifact_path=Path(row["artifact_path"]),
            created_at=row["created_at"],
        )

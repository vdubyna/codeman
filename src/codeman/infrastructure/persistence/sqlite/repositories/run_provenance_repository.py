"""SQLite adapter for run configuration provenance records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import desc, insert, inspect, select
from sqlalchemy.engine import Engine

from codeman.application.ports.run_provenance_store_port import RunProvenanceStorePort
from codeman.config.loader import ConfigurationResolutionError
from codeman.config.provenance import build_effective_config_provenance_canonical_json
from codeman.config.retrieval_profiles import RetrievalStrategyProfilePayload
from codeman.contracts.configuration import (
    RunConfigurationProvenanceRecord,
    RunProvenanceWorkflowContext,
)
from codeman.infrastructure.persistence.sqlite.migrations import upgrade_database
from codeman.infrastructure.persistence.sqlite.tables import run_provenance_records_table


def _canonical_context_json(context: RunProvenanceWorkflowContext) -> str:
    payload = context.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
    return json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    )


@dataclass(slots=True)
class SqliteRunProvenanceStore(RunProvenanceStorePort):
    """Persist run provenance in the runtime SQLite database."""

    engine: Engine
    database_path: Path

    def initialize(self) -> None:
        """Ensure the runtime metadata schema is up to date."""

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        upgrade_database(self.database_path)

    def create_record(
        self,
        record: RunConfigurationProvenanceRecord,
    ) -> RunConfigurationProvenanceRecord:
        """Persist one run provenance record."""

        statement = insert(run_provenance_records_table).values(
            id=record.run_id,
            workflow_type=record.workflow_type,
            repository_id=record.repository_id,
            snapshot_id=record.snapshot_id,
            configuration_id=record.configuration_id,
            indexing_config_fingerprint=record.indexing_config_fingerprint,
            semantic_config_fingerprint=record.semantic_config_fingerprint,
            provider_id=record.provider_id,
            model_id=record.model_id,
            model_version=record.model_version,
            effective_config_json=build_effective_config_provenance_canonical_json(
                record.effective_config
            ),
            workflow_context_json=_canonical_context_json(record.workflow_context),
            created_at=record.created_at,
        )
        with self.engine.begin() as connection:
            connection.execute(statement)
        return record

    def get_by_run_id(self, run_id: str) -> RunConfigurationProvenanceRecord | None:
        """Return a stored run provenance record by run id."""

        if not self._table_exists():
            return None

        query = (
            select(run_provenance_records_table)
            .where(run_provenance_records_table.c.id == run_id)
            .limit(1)
        )
        with self.engine.begin() as connection:
            row = connection.execute(query).mappings().first()

        if row is None:
            return None
        return self._row_to_record(row)

    def list_by_repository_id(self, repository_id: str) -> list[RunConfigurationProvenanceRecord]:
        """Return repository-scoped run provenance records in deterministic order."""

        if not self._table_exists():
            return []

        query = (
            select(run_provenance_records_table)
            .where(run_provenance_records_table.c.repository_id == repository_id)
            .order_by(
                desc(run_provenance_records_table.c.created_at),
                desc(run_provenance_records_table.c.id),
            )
        )
        with self.engine.begin() as connection:
            rows = connection.execute(query).mappings().all()

        return [self._row_to_record(row) for row in rows]

    def _table_exists(self) -> bool:
        """Return whether the run-provenance table exists already."""

        if not self.database_path.exists():
            return False
        return inspect(self.engine).has_table(run_provenance_records_table.name)

    @staticmethod
    def _row_to_record(row: Any) -> RunConfigurationProvenanceRecord:
        """Convert a row mapping into a run-provenance DTO."""

        try:
            effective_config = RetrievalStrategyProfilePayload.model_validate(
                json.loads(row["effective_config_json"])
            )
            workflow_context = RunProvenanceWorkflowContext.model_validate(
                json.loads(row["workflow_context_json"])
            )
        except (TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise ConfigurationResolutionError(
                f"Persisted run provenance record is invalid: {row['id']}",
                details={"run_id": row["id"]},
            ) from exc

        return RunConfigurationProvenanceRecord(
            run_id=row["id"],
            workflow_type=row["workflow_type"],
            repository_id=row["repository_id"],
            snapshot_id=row["snapshot_id"],
            configuration_id=row["configuration_id"],
            indexing_config_fingerprint=row["indexing_config_fingerprint"],
            semantic_config_fingerprint=row["semantic_config_fingerprint"],
            provider_id=row["provider_id"],
            model_id=row["model_id"],
            model_version=row["model_version"],
            effective_config=effective_config,
            workflow_context=workflow_context,
            created_at=row["created_at"],
        )

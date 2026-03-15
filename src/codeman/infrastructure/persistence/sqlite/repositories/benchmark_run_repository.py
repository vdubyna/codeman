"""SQLite adapter for benchmark execution lifecycle records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import desc, insert, inspect, select, update
from sqlalchemy.engine import Engine

from codeman.application.ports.benchmark_run_store_port import BenchmarkRunStorePort
from codeman.contracts.evaluation import BenchmarkRunRecord
from codeman.infrastructure.persistence.sqlite.migrations import upgrade_database
from codeman.infrastructure.persistence.sqlite.tables import benchmark_runs_table


def _normalize_utc_datetime(value: datetime | str | None) -> datetime | None:
    """Normalize SQLite datetime values to timezone-aware UTC datetimes."""

    if value is None:
        return None

    candidate = value
    if isinstance(candidate, str):
        candidate = datetime.fromisoformat(candidate.replace("Z", "+00:00"))

    if candidate.tzinfo is None:
        return candidate.replace(tzinfo=UTC)
    return candidate.astimezone(UTC)


@dataclass(slots=True)
class SqliteBenchmarkRunStore(BenchmarkRunStorePort):
    """Persist benchmark run lifecycle records in the runtime SQLite database."""

    engine: Engine
    database_path: Path

    def initialize(self) -> None:
        """Ensure the runtime metadata schema is up to date."""

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        upgrade_database(self.database_path)

    def create_run(self, record: BenchmarkRunRecord) -> BenchmarkRunRecord:
        """Persist one new benchmark run record."""

        statement = insert(benchmark_runs_table).values(
            id=record.run_id,
            repository_id=record.repository_id,
            snapshot_id=record.snapshot_id,
            retrieval_mode=record.retrieval_mode,
            dataset_id=record.dataset_id,
            dataset_version=record.dataset_version,
            dataset_fingerprint=record.dataset_fingerprint,
            case_count=record.case_count,
            completed_case_count=record.completed_case_count,
            status=record.status,
            artifact_path=str(record.artifact_path) if record.artifact_path is not None else None,
            evaluated_at_k=record.evaluated_at_k,
            recall_at_k=record.recall_at_k,
            mrr=record.mrr,
            ndcg_at_k=record.ndcg_at_k,
            query_latency_mean_ms=record.query_latency_mean_ms,
            query_latency_p95_ms=record.query_latency_p95_ms,
            lexical_index_duration_ms=record.lexical_index_duration_ms,
            semantic_index_duration_ms=record.semantic_index_duration_ms,
            derived_index_duration_ms=record.derived_index_duration_ms,
            metrics_artifact_path=(
                str(record.metrics_artifact_path)
                if record.metrics_artifact_path is not None
                else None
            ),
            metrics_computed_at=record.metrics_computed_at,
            error_code=record.error_code,
            error_message=record.error_message,
            started_at=record.started_at,
            completed_at=record.completed_at,
        )
        with self.engine.begin() as connection:
            connection.execute(statement)
        return record

    def update_run(self, record: BenchmarkRunRecord) -> BenchmarkRunRecord:
        """Persist the latest lifecycle fields for an existing benchmark run."""

        statement = (
            update(benchmark_runs_table)
            .where(benchmark_runs_table.c.id == record.run_id)
            .values(
                completed_case_count=record.completed_case_count,
                status=record.status,
                artifact_path=(
                    str(record.artifact_path) if record.artifact_path is not None else None
                ),
                evaluated_at_k=record.evaluated_at_k,
                recall_at_k=record.recall_at_k,
                mrr=record.mrr,
                ndcg_at_k=record.ndcg_at_k,
                query_latency_mean_ms=record.query_latency_mean_ms,
                query_latency_p95_ms=record.query_latency_p95_ms,
                lexical_index_duration_ms=record.lexical_index_duration_ms,
                semantic_index_duration_ms=record.semantic_index_duration_ms,
                derived_index_duration_ms=record.derived_index_duration_ms,
                metrics_artifact_path=(
                    str(record.metrics_artifact_path)
                    if record.metrics_artifact_path is not None
                    else None
                ),
                metrics_computed_at=record.metrics_computed_at,
                error_code=record.error_code,
                error_message=record.error_message,
                completed_at=record.completed_at,
            )
        )
        with self.engine.begin() as connection:
            connection.execute(statement)
        return record

    def get_by_run_id(self, run_id: str) -> BenchmarkRunRecord | None:
        """Return one persisted benchmark run record by run id."""

        if not self._table_exists():
            return None
        upgrade_database(self.database_path)

        query = select(benchmark_runs_table).where(benchmark_runs_table.c.id == run_id).limit(1)
        with self.engine.begin() as connection:
            row = connection.execute(query).mappings().first()

        if row is None:
            return None
        return self._row_to_record(row)

    def list_by_repository_id(self, repository_id: str) -> list[BenchmarkRunRecord]:
        """Return repository-scoped benchmark runs in deterministic order."""

        if not self._table_exists():
            return []
        upgrade_database(self.database_path)

        query = (
            select(benchmark_runs_table)
            .where(benchmark_runs_table.c.repository_id == repository_id)
            .order_by(
                desc(benchmark_runs_table.c.started_at),
                desc(benchmark_runs_table.c.id),
            )
        )
        with self.engine.begin() as connection:
            rows = connection.execute(query).mappings().all()
        return [self._row_to_record(row) for row in rows]

    def _table_exists(self) -> bool:
        """Return whether the benchmark-runs table exists already."""

        if not self.database_path.exists():
            return False
        return inspect(self.engine).has_table(benchmark_runs_table.name)

    @staticmethod
    def _row_to_record(row: Any) -> BenchmarkRunRecord:
        """Convert a row mapping into a benchmark-run DTO."""

        return BenchmarkRunRecord(
            run_id=row["id"],
            repository_id=row["repository_id"],
            snapshot_id=row["snapshot_id"],
            retrieval_mode=row["retrieval_mode"],
            dataset_id=row["dataset_id"],
            dataset_version=row["dataset_version"],
            dataset_fingerprint=row["dataset_fingerprint"],
            case_count=row["case_count"],
            completed_case_count=row["completed_case_count"],
            status=row["status"],
            artifact_path=Path(row["artifact_path"]) if row["artifact_path"] is not None else None,
            evaluated_at_k=row["evaluated_at_k"],
            recall_at_k=row["recall_at_k"],
            mrr=row["mrr"],
            ndcg_at_k=row["ndcg_at_k"],
            query_latency_mean_ms=row["query_latency_mean_ms"],
            query_latency_p95_ms=row["query_latency_p95_ms"],
            lexical_index_duration_ms=row["lexical_index_duration_ms"],
            semantic_index_duration_ms=row["semantic_index_duration_ms"],
            derived_index_duration_ms=row["derived_index_duration_ms"],
            metrics_artifact_path=(
                Path(row["metrics_artifact_path"])
                if row["metrics_artifact_path"] is not None
                else None
            ),
            metrics_computed_at=_normalize_utc_datetime(row["metrics_computed_at"]),
            error_code=row["error_code"],
            error_message=row["error_message"],
            started_at=_normalize_utc_datetime(row["started_at"]),
            completed_at=_normalize_utc_datetime(row["completed_at"]),
        )

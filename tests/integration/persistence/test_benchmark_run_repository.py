from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codeman.contracts.evaluation import BenchmarkRunRecord, BenchmarkRunStatus
from codeman.infrastructure.persistence.sqlite.engine import create_sqlite_engine
from codeman.infrastructure.persistence.sqlite.repositories.benchmark_run_repository import (
    SqliteBenchmarkRunStore,
)


def build_record(
    *,
    run_id: str,
    created_at: datetime,
    status: BenchmarkRunStatus,
    completed_case_count: int,
    completed_at: datetime | None,
    evaluated_at_k: int | None = None,
) -> BenchmarkRunRecord:
    return BenchmarkRunRecord(
        run_id=run_id,
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        retrieval_mode="lexical",
        dataset_id="fixture-benchmark",
        dataset_version="2026-03-15",
        dataset_fingerprint="f" * 64,
        case_count=2,
        completed_case_count=completed_case_count,
        status=status,
        artifact_path=Path("/tmp/run.json") if completed_at is not None else None,
        evaluated_at_k=evaluated_at_k,
        recall_at_k=0.5 if evaluated_at_k is not None else None,
        mrr=0.5 if evaluated_at_k is not None else None,
        ndcg_at_k=0.75 if evaluated_at_k is not None else None,
        query_latency_mean_ms=7.5 if evaluated_at_k is not None else None,
        query_latency_p95_ms=9 if evaluated_at_k is not None else None,
        lexical_index_duration_ms=42 if evaluated_at_k is not None else None,
        semantic_index_duration_ms=None,
        derived_index_duration_ms=None,
        metrics_artifact_path=(Path("/tmp/metrics.json") if evaluated_at_k is not None else None),
        metrics_computed_at=(
            datetime(2026, 3, 15, 10, 6, tzinfo=UTC) if evaluated_at_k is not None else None
        ),
        error_code=None,
        error_message=None,
        started_at=created_at,
        completed_at=completed_at,
    )


def test_sqlite_benchmark_run_store_round_trips_and_orders_records(tmp_path: Path) -> None:
    database_path = tmp_path / ".codeman" / "metadata.sqlite3"
    store = SqliteBenchmarkRunStore(
        engine=create_sqlite_engine(database_path),
        database_path=database_path,
    )
    running_record = build_record(
        run_id="run-001",
        created_at=datetime(2026, 3, 15, 9, 0, tzinfo=UTC),
        status=BenchmarkRunStatus.RUNNING,
        completed_case_count=0,
        completed_at=None,
    )
    succeeded_record = build_record(
        run_id="run-002",
        created_at=datetime(2026, 3, 15, 10, 0, tzinfo=UTC),
        status=BenchmarkRunStatus.SUCCEEDED,
        completed_case_count=2,
        completed_at=datetime(2026, 3, 15, 10, 5, tzinfo=UTC),
        evaluated_at_k=5,
    )

    store.initialize()
    store.create_run(running_record)
    store.create_run(succeeded_record)
    updated_running = running_record.model_copy(
        update={
            "completed_case_count": 1,
            "status": BenchmarkRunStatus.FAILED,
            "artifact_path": Path("/tmp/failed.json"),
            "error_code": "benchmark_execution_failed",
            "error_message": "Execution failed.",
            "completed_at": datetime(2026, 3, 15, 9, 30, tzinfo=UTC),
        }
    )
    store.update_run(updated_running)

    loaded = store.get_by_run_id("run-001")
    listed = store.list_by_repository_id("repo-123")

    assert loaded is not None
    assert loaded.status == BenchmarkRunStatus.FAILED
    assert loaded.completed_case_count == 1
    assert loaded.error_code == "benchmark_execution_failed"
    assert loaded.started_at == datetime(2026, 3, 15, 9, 0, tzinfo=UTC)
    assert loaded.completed_at == datetime(2026, 3, 15, 9, 30, tzinfo=UTC)
    assert [record.run_id for record in listed] == ["run-002", "run-001"]
    assert listed[0].evaluated_at_k == 5
    assert listed[0].metrics_artifact_path == Path("/tmp/metrics.json")
    assert listed[0].metrics_computed_at == datetime(2026, 3, 15, 10, 6, tzinfo=UTC)

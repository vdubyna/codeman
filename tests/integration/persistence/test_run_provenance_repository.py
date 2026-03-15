from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from codeman.config.retrieval_profiles import RetrievalStrategyProfilePayload
from codeman.contracts.configuration import (
    RunConfigurationProvenanceRecord,
    RunProvenanceWorkflowContext,
)
from codeman.infrastructure.persistence.sqlite.engine import create_sqlite_engine
from codeman.infrastructure.persistence.sqlite.repositories.run_provenance_repository import (
    SqliteRunProvenanceStore,
)


def _build_record(
    tmp_path: Path,
    *,
    run_id: str,
    repository_id: str,
    created_at: datetime,
) -> RunConfigurationProvenanceRecord:
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir(exist_ok=True)
    return RunConfigurationProvenanceRecord(
        run_id=run_id,
        workflow_type="query.semantic",
        repository_id=repository_id,
        snapshot_id="snapshot-123",
        configuration_id=f"config-{run_id}",
        semantic_config_fingerprint="semantic-fingerprint-123",
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="2026-03-15",
        effective_config=RetrievalStrategyProfilePayload.model_validate(
            {
                "indexing": {"fingerprint_salt": "indexing-salt"},
                "semantic_indexing": {
                    "provider_id": "local-hash",
                    "vector_engine": "sqlite-exact",
                    "vector_dimension": 16,
                    "fingerprint_salt": "semantic-salt",
                },
                "embedding_providers": {
                    "local_hash": {
                        "model_id": "fixture-local",
                        "model_version": "2026-03-15",
                        "local_model_path": str(local_model_path),
                    }
                },
            }
        ),
        workflow_context=RunProvenanceWorkflowContext(
            semantic_build_id="semantic-build-123",
            max_results=5,
        ),
        created_at=created_at,
    )


def test_sqlite_run_provenance_store_round_trips_and_orders_repository_records(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / ".codeman" / "metadata.sqlite3"
    store = SqliteRunProvenanceStore(
        engine=create_sqlite_engine(database_path),
        database_path=database_path,
    )
    first_record = _build_record(
        tmp_path,
        run_id="run-001",
        repository_id="repo-123",
        created_at=datetime(2026, 3, 15, 7, 0, tzinfo=UTC),
    )
    second_record = _build_record(
        tmp_path,
        run_id="run-002",
        repository_id="repo-123",
        created_at=datetime(2026, 3, 15, 8, 0, tzinfo=UTC),
    )

    store.initialize()
    store.create_record(first_record)
    store.create_record(second_record)

    loaded = store.get_by_run_id("run-001")
    listed = store.list_by_repository_id("repo-123")

    assert loaded is not None
    assert loaded.run_id == "run-001"
    assert [record.run_id for record in listed] == ["run-002", "run-001"]


def test_sqlite_run_provenance_store_persists_secret_safe_payloads_only(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / ".codeman" / "metadata.sqlite3"
    store = SqliteRunProvenanceStore(
        engine=create_sqlite_engine(database_path),
        database_path=database_path,
    )
    record = _build_record(
        tmp_path,
        run_id="run-001",
        repository_id="repo-123",
        created_at=datetime(2026, 3, 15, 7, 0, tzinfo=UTC),
    )

    store.initialize()
    store.create_record(record)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            (
                "select effective_config_json, workflow_context_json "
                "from run_provenance_records where id = ?"
            ),
            (record.run_id,),
        ).fetchone()

    assert row is not None
    assert "api_key" not in row[0]
    assert "super-secret" not in row[0]
    assert "semantic-build-123" in row[1]

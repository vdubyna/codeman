from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from codeman.contracts.chunking import ChunkPayloadDocument
from codeman.contracts.evaluation import (
    BenchmarkDatasetDocument,
    BenchmarkDatasetSummary,
    BenchmarkQueryCase,
    BenchmarkQuerySourceKind,
    BenchmarkRelevanceJudgment,
    BenchmarkRunArtifactDocument,
    BenchmarkRunRecord,
    BenchmarkRunStatus,
)
from codeman.contracts.retrieval import (
    LexicalRetrievalBuildContext,
    RetrievalRepositoryContext,
    RetrievalSnapshotContext,
)
from codeman.infrastructure.artifacts.filesystem_artifact_store import (
    FilesystemArtifactStore,
)


def test_write_chunk_payload_persists_json_artifact(tmp_path: Path) -> None:
    artifact_store = FilesystemArtifactStore(tmp_path)
    payload = ChunkPayloadDocument(
        chunk_id="chunk-123",
        snapshot_id="snapshot-123",
        repository_id="repo-123",
        source_file_id="source-123",
        relative_path="assets/app.js",
        language="javascript",
        strategy="javascript_structure",
        source_content_hash="hash-123",
        start_line=1,
        end_line=3,
        start_byte=0,
        end_byte=42,
        content='export function boot() {\n  return "codeman";\n}\n',
    )

    destination = artifact_store.write_chunk_payload(
        payload,
        snapshot_id=payload.snapshot_id,
    )

    assert destination == tmp_path / "snapshots" / "snapshot-123" / "chunks" / "chunk-123.json"
    stored = json.loads(destination.read_text(encoding="utf-8"))
    assert stored["chunk_id"] == "chunk-123"
    assert stored["relative_path"] == "assets/app.js"


def test_read_chunk_payload_round_trips_json_artifact(tmp_path: Path) -> None:
    artifact_store = FilesystemArtifactStore(tmp_path)
    payload = ChunkPayloadDocument(
        chunk_id="chunk-123",
        snapshot_id="snapshot-123",
        repository_id="repo-123",
        source_file_id="source-123",
        relative_path="assets/app.js",
        language="javascript",
        strategy="javascript_structure",
        source_content_hash="hash-123",
        start_line=1,
        end_line=3,
        start_byte=0,
        end_byte=42,
        content='export function boot() {\n  return "codeman";\n}\n',
    )

    destination = artifact_store.write_chunk_payload(
        payload,
        snapshot_id=payload.snapshot_id,
    )
    restored = artifact_store.read_chunk_payload(destination)

    assert restored.chunk_id == payload.chunk_id
    assert restored.snapshot_id == payload.snapshot_id
    assert restored.content == payload.content


def test_write_and_read_benchmark_run_artifact_round_trip(tmp_path: Path) -> None:
    artifact_store = FilesystemArtifactStore(tmp_path)
    artifact = BenchmarkRunArtifactDocument(
        run=BenchmarkRunRecord(
            run_id="run-123",
            repository_id="repo-123",
            snapshot_id="snapshot-123",
            retrieval_mode="lexical",
            dataset_id="fixture-benchmark",
            dataset_version="2026-03-15",
            dataset_fingerprint="f" * 64,
            case_count=1,
            completed_case_count=1,
            status=BenchmarkRunStatus.SUCCEEDED,
            artifact_path=tmp_path / "benchmarks" / "run-123" / "run.json",
            started_at=datetime(2026, 3, 15, 9, 0, tzinfo=UTC),
            completed_at=datetime(2026, 3, 15, 9, 1, tzinfo=UTC),
        ),
        repository=RetrievalRepositoryContext(
            repository_id="repo-123",
            repository_name="registered-repo",
        ),
        snapshot=RetrievalSnapshotContext(
            snapshot_id="snapshot-123",
            revision_identity="revision-abc",
            revision_source="filesystem_fingerprint",
        ),
        build=LexicalRetrievalBuildContext(
            build_id="lexical-build-123",
            indexing_config_fingerprint="index-fingerprint-123",
            lexical_engine="sqlite-fts5",
            tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
            indexed_fields=["content", "relative_path"],
        ),
        dataset=BenchmarkDatasetDocument(
            schema_version="1",
            dataset_id="fixture-benchmark",
            dataset_version="2026-03-15",
            cases=[
                BenchmarkQueryCase(
                    query_id="case-1",
                    query_text="home controller",
                    source_kind=BenchmarkQuerySourceKind.HUMAN_AUTHORED,
                    judgments=[
                        BenchmarkRelevanceJudgment(
                            relative_path="src/Controller/HomeController.php",
                            language="php",
                            start_line=4,
                            end_line=10,
                            relevance_grade=2,
                        )
                    ],
                )
            ],
        ),
        dataset_summary=BenchmarkDatasetSummary(
            dataset_path=tmp_path / "dataset.json",
            schema_version="1",
            dataset_id="fixture-benchmark",
            dataset_version="2026-03-15",
            case_count=1,
            judgment_count=1,
            dataset_fingerprint="f" * 64,
        ),
        max_results=5,
        cases=[],
    )

    destination = artifact_store.write_benchmark_run_artifact(artifact, run_id="run-123")
    restored = artifact_store.read_benchmark_run_artifact(destination)

    assert destination == tmp_path / "benchmarks" / "run-123" / "run.json"
    assert restored.run.run_id == "run-123"
    assert restored.dataset.dataset_id == "fixture-benchmark"

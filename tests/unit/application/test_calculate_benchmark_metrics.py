from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codeman.application.evaluation.calculate_benchmark_metrics import (
    BenchmarkArtifactCorruptError,
    BenchmarkArtifactMissingError,
    BenchmarkMetricsError,
    BenchmarkRunIncompleteError,
    CalculateBenchmarkMetricsUseCase,
)
from codeman.contracts.evaluation import (
    BenchmarkCaseExecutionArtifact,
    BenchmarkDatasetDocument,
    BenchmarkDatasetSummary,
    BenchmarkQueryCase,
    BenchmarkQuerySourceKind,
    BenchmarkRelevanceJudgment,
    BenchmarkRunArtifactDocument,
    BenchmarkRunRecord,
    BenchmarkRunStatus,
    CalculateBenchmarkMetricsRequest,
    build_benchmark_dataset_fingerprint,
)
from codeman.contracts.retrieval import (
    HybridComponentQueryDiagnostics,
    HybridQueryDiagnostics,
    HybridRetrievalBuildContext,
    LexicalIndexBuildRecord,
    LexicalRetrievalBuildContext,
    RetrievalQueryDiagnostics,
    RetrievalQueryMetadata,
    RetrievalRepositoryContext,
    RetrievalResultItem,
    RetrievalSnapshotContext,
    RunHybridQueryResult,
    RunLexicalQueryResult,
    SemanticIndexBuildRecord,
    SemanticRetrievalBuildContext,
)
from codeman.infrastructure.artifacts.filesystem_artifact_store import (
    FilesystemArtifactStore,
)
from codeman.runtime import build_runtime_paths

HYBRID_BUILD_ID = "hybrid-15a5348ca315"


@dataclass
class FakeBenchmarkRunStore:
    record: BenchmarkRunRecord | None
    initialized: int = 0
    updated_records: list[BenchmarkRunRecord] = field(default_factory=list)

    def initialize(self) -> None:
        self.initialized += 1

    def create_run(self, record: BenchmarkRunRecord) -> BenchmarkRunRecord:
        self.record = record
        return record

    def update_run(self, record: BenchmarkRunRecord) -> BenchmarkRunRecord:
        self.record = record
        self.updated_records.append(record)
        return record

    def get_by_run_id(self, run_id: str) -> BenchmarkRunRecord | None:
        if self.record is None or self.record.run_id != run_id:
            return None
        return self.record

    def list_by_repository_id(self, repository_id: str) -> list[BenchmarkRunRecord]:
        if self.record is None or self.record.repository_id != repository_id:
            return []
        return [self.record]


@dataclass
class FakeIndexBuildStore:
    build: LexicalIndexBuildRecord | None = None
    initialized: int = 0

    def initialize(self) -> None:
        self.initialized += 1

    def create_build(self, build: LexicalIndexBuildRecord) -> LexicalIndexBuildRecord:
        self.build = build
        return build

    def get_latest_build_for_snapshot(self, snapshot_id: str) -> LexicalIndexBuildRecord | None:
        return self.build

    def get_latest_build_for_repository(
        self,
        repository_id: str,
        indexing_config_fingerprint: str,
    ) -> LexicalIndexBuildRecord | None:
        return self.build

    def get_by_build_id(self, build_id: str) -> LexicalIndexBuildRecord | None:
        if self.build is None or self.build.build_id != build_id:
            return None
        return self.build


@dataclass
class FakeSemanticIndexBuildStore:
    build: SemanticIndexBuildRecord | None = None
    initialized: int = 0

    def initialize(self) -> None:
        self.initialized += 1

    def create_build(self, build: SemanticIndexBuildRecord) -> SemanticIndexBuildRecord:
        self.build = build
        return build

    def get_latest_build_for_snapshot(
        self,
        snapshot_id: str,
        semantic_config_fingerprint: str,
    ) -> SemanticIndexBuildRecord | None:
        return self.build

    def get_latest_build_for_repository(
        self,
        repository_id: str,
        semantic_config_fingerprint: str,
    ) -> SemanticIndexBuildRecord | None:
        return self.build

    def get_by_build_id(self, build_id: str) -> SemanticIndexBuildRecord | None:
        if self.build is None or self.build.build_id != build_id:
            return None
        return self.build


@dataclass
class BrokenMetricsArtifactStore:
    delegate: FilesystemArtifactStore

    def __getattr__(self, name: str) -> object:
        return getattr(self.delegate, name)

    def write_benchmark_metrics_artifact(
        self,
        artifact: object,
        *,
        run_id: str,
    ) -> Path:
        raise OSError("disk full")


@dataclass
class BrokenBenchmarkRunStore(FakeBenchmarkRunStore):
    def update_run(self, record: BenchmarkRunRecord) -> BenchmarkRunRecord:
        raise RuntimeError("database locked")


def build_run_record(
    *,
    artifact_path: Path | None,
    status: BenchmarkRunStatus = BenchmarkRunStatus.SUCCEEDED,
    dataset_fingerprint: str | None = None,
) -> BenchmarkRunRecord:
    resolved_dataset_fingerprint = dataset_fingerprint
    if resolved_dataset_fingerprint is None:
        resolved_dataset_fingerprint = build_dataset()[1].dataset_fingerprint
    return BenchmarkRunRecord(
        run_id="run-123",
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        retrieval_mode="lexical",
        dataset_id="fixture-benchmark",
        dataset_version="2026-03-15",
        dataset_fingerprint=resolved_dataset_fingerprint,
        case_count=2,
        completed_case_count=2 if status == BenchmarkRunStatus.SUCCEEDED else 1,
        status=status,
        artifact_path=artifact_path,
        started_at=datetime(2026, 3, 15, 9, 0, tzinfo=UTC),
        completed_at=(
            datetime(2026, 3, 15, 9, 1, tzinfo=UTC)
            if status != BenchmarkRunStatus.RUNNING
            else None
        ),
    )


def build_dataset() -> tuple[BenchmarkDatasetDocument, BenchmarkDatasetSummary]:
    dataset = BenchmarkDatasetDocument(
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
            ),
            BenchmarkQueryCase(
                query_id="case-2",
                query_text="settings controller",
                source_kind=BenchmarkQuerySourceKind.HUMAN_AUTHORED,
                judgments=[
                    BenchmarkRelevanceJudgment(
                        relative_path="src/Controller/SettingsController.php",
                        language="php",
                        start_line=4,
                        end_line=10,
                        relevance_grade=1,
                    )
                ],
            ),
        ],
    )
    dataset_fingerprint = build_benchmark_dataset_fingerprint(dataset)
    summary = BenchmarkDatasetSummary(
        dataset_path=Path("/tmp/dataset.json"),
        schema_version="1",
        dataset_id="fixture-benchmark",
        dataset_version="2026-03-15",
        case_count=2,
        judgment_count=2,
        dataset_fingerprint=dataset_fingerprint,
    )
    return dataset, summary


def build_result_item(*, rank: int, relative_path: str) -> RetrievalResultItem:
    return RetrievalResultItem(
        chunk_id=f"chunk-{rank}",
        relative_path=relative_path,
        language="php",
        strategy="php_structure",
        rank=rank,
        score=1.0 / rank,
        start_line=4,
        end_line=10,
        start_byte=0,
        end_byte=42,
        content_preview="fixture",
        explanation="fixture",
    )


def build_lexical_case_artifacts(
    *,
    build_context: LexicalRetrievalBuildContext | None = None,
) -> list[BenchmarkCaseExecutionArtifact]:
    default_build_context = build_context or LexicalRetrievalBuildContext(
        build_id="lexical-build-123",
        indexing_config_fingerprint="index-fingerprint-123",
        lexical_engine="sqlite-fts5",
        tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
        indexed_fields=["content", "relative_path"],
    )
    return [
        BenchmarkCaseExecutionArtifact(
            query_id="case-1",
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
            result=RunLexicalQueryResult(
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
                    **default_build_context.model_dump()
                ),
                query=RetrievalQueryMetadata(text="home controller"),
                results=[
                    build_result_item(
                        rank=1,
                        relative_path="src/Controller/HomeController.php",
                    )
                ],
                diagnostics=RetrievalQueryDiagnostics(
                    match_count=1,
                    total_match_count=1,
                    truncated=False,
                    query_latency_ms=5,
                ),
            ),
        ),
        BenchmarkCaseExecutionArtifact(
            query_id="case-2",
            source_kind=BenchmarkQuerySourceKind.HUMAN_AUTHORED,
            judgments=[
                BenchmarkRelevanceJudgment(
                    relative_path="src/Controller/SettingsController.php",
                    language="php",
                    start_line=4,
                    end_line=10,
                    relevance_grade=1,
                )
            ],
            result=RunLexicalQueryResult(
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
                    **default_build_context.model_dump()
                ),
                query=RetrievalQueryMetadata(text="settings controller"),
                results=[build_result_item(rank=1, relative_path="src/Controller/Miss.php")],
                diagnostics=RetrievalQueryDiagnostics(
                    match_count=1,
                    total_match_count=1,
                    truncated=False,
                    query_latency_ms=15,
                ),
            ),
        ),
    ]


def build_lexical_build_record(
    tmp_path: Path,
    *,
    duration_ms: int | None,
) -> LexicalIndexBuildRecord:
    artifact_path = tmp_path / "lexical.sqlite3"
    artifact_path.write_text("fixture", encoding="utf-8")
    return LexicalIndexBuildRecord(
        build_id="lexical-build-123",
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        indexing_config_fingerprint="index-fingerprint-123",
        lexical_engine="sqlite-fts5",
        tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
        indexed_fields=["content", "relative_path"],
        chunks_indexed=4,
        build_duration_ms=duration_ms,
        index_path=artifact_path,
        created_at=datetime(2026, 3, 15, 8, 59, tzinfo=UTC),
    )


def build_semantic_build_record(
    tmp_path: Path,
    *,
    duration_ms: int | None,
) -> SemanticIndexBuildRecord:
    artifact_path = tmp_path / "semantic.sqlite3"
    artifact_path.write_text("fixture", encoding="utf-8")
    return SemanticIndexBuildRecord(
        build_id="semantic-build-123",
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        semantic_config_fingerprint="semantic-fingerprint-123",
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="2026-03-14",
        vector_engine="sqlite-exact",
        document_count=4,
        embedding_dimension=8,
        build_duration_ms=duration_ms,
        artifact_path=artifact_path,
        created_at=datetime(2026, 3, 15, 8, 59, tzinfo=UTC),
    )


def build_use_case(
    *,
    tmp_path: Path,
    run_record: BenchmarkRunRecord,
    lexical_build: LexicalIndexBuildRecord | None = None,
    semantic_build: SemanticIndexBuildRecord | None = None,
) -> tuple[CalculateBenchmarkMetricsUseCase, FilesystemArtifactStore, FakeBenchmarkRunStore]:
    runtime_paths = build_runtime_paths(tmp_path / "workspace")
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    benchmark_run_store = FakeBenchmarkRunStore(record=run_record)
    use_case = CalculateBenchmarkMetricsUseCase(
        runtime_paths=runtime_paths,
        benchmark_run_store=benchmark_run_store,
        artifact_store=artifact_store,
        index_build_store=FakeIndexBuildStore(build=lexical_build),
        semantic_index_build_store=FakeSemanticIndexBuildStore(build=semantic_build),
    )
    return use_case, artifact_store, benchmark_run_store


def write_raw_benchmark_artifact(
    artifact_store: FilesystemArtifactStore,
    *,
    run: BenchmarkRunRecord,
    artifact: BenchmarkRunArtifactDocument | None = None,
) -> Path:
    if artifact is None:
        dataset, dataset_summary = build_dataset()
        artifact = BenchmarkRunArtifactDocument(
            run=run,
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
            dataset=dataset,
            dataset_summary=dataset_summary,
            max_results=5,
            cases=build_lexical_case_artifacts(),
        )
    return artifact_store.write_benchmark_run_artifact(artifact, run_id=run.run_id)


def test_calculate_benchmark_metrics_persists_summary_and_metrics_artifact(
    tmp_path: Path,
) -> None:
    expected_artifact_path = (
        build_runtime_paths(tmp_path / "workspace").artifacts
        / "benchmarks"
        / "run-123"
        / "run.json"
    )
    run_record = build_run_record(artifact_path=expected_artifact_path)
    use_case, artifact_store, benchmark_run_store = build_use_case(
        tmp_path=tmp_path,
        run_record=run_record,
        lexical_build=build_lexical_build_record(tmp_path, duration_ms=42),
    )
    raw_artifact_path = write_raw_benchmark_artifact(artifact_store, run=run_record)
    benchmark_run_store.record = run_record.model_copy(update={"artifact_path": raw_artifact_path})

    result = use_case.execute(CalculateBenchmarkMetricsRequest(run_id="run-123"))
    metrics_artifact = artifact_store.read_benchmark_metrics_artifact(result.metrics.artifact_path)

    assert result.run.evaluated_at_k == 5
    assert result.run.recall_at_k == 0.5
    assert result.run.mrr == 0.5
    assert result.run.ndcg_at_k == 0.5
    assert result.run.query_latency_mean_ms == 10.0
    assert result.run.query_latency_p95_ms == 15
    assert result.run.lexical_index_duration_ms == 42
    assert result.run.metrics_artifact_path == result.metrics.artifact_path
    assert result.metrics.metrics.recall_at_k == 0.5
    assert metrics_artifact.summary.performance.query_latency.p95_ms == 15
    assert metrics_artifact.summary.performance.indexing.lexical_build_duration_ms == 42


def test_calculate_benchmark_metrics_rejects_incomplete_runs(tmp_path: Path) -> None:
    use_case, _, _ = build_use_case(
        tmp_path=tmp_path,
        run_record=build_run_record(
            artifact_path=Path("/tmp/run.json"),
            status=BenchmarkRunStatus.FAILED,
        ),
    )

    with pytest.raises(BenchmarkRunIncompleteError):
        use_case.execute(CalculateBenchmarkMetricsRequest(run_id="run-123"))


def test_calculate_benchmark_metrics_fails_when_raw_artifact_is_missing(tmp_path: Path) -> None:
    use_case, _, _ = build_use_case(
        tmp_path=tmp_path,
        run_record=build_run_record(
            artifact_path=Path("/tmp/missing-run.json"),
        ),
    )

    with pytest.raises(BenchmarkArtifactMissingError):
        use_case.execute(CalculateBenchmarkMetricsRequest(run_id="run-123"))


def test_calculate_benchmark_metrics_fails_when_raw_artifact_is_corrupt(tmp_path: Path) -> None:
    runtime_paths = build_runtime_paths(tmp_path / "workspace")
    corrupt_path = runtime_paths.artifacts / "benchmarks" / "run-123" / "run.json"
    corrupt_path.parent.mkdir(parents=True, exist_ok=True)
    corrupt_path.write_text("{not-json", encoding="utf-8")
    use_case, _, _ = build_use_case(
        tmp_path=tmp_path,
        run_record=build_run_record(artifact_path=corrupt_path),
    )

    with pytest.raises(BenchmarkArtifactCorruptError):
        use_case.execute(CalculateBenchmarkMetricsRequest(run_id="run-123"))


def test_calculate_benchmark_metrics_wraps_metrics_artifact_write_failures(
    tmp_path: Path,
) -> None:
    runtime_paths = build_runtime_paths(tmp_path / "workspace")
    delegate_store = FilesystemArtifactStore(runtime_paths.artifacts)
    run_record = build_run_record(
        artifact_path=runtime_paths.artifacts / "benchmarks" / "run-123" / "run.json"
    )
    benchmark_run_store = FakeBenchmarkRunStore(record=run_record)
    use_case = CalculateBenchmarkMetricsUseCase(
        runtime_paths=runtime_paths,
        benchmark_run_store=benchmark_run_store,
        artifact_store=BrokenMetricsArtifactStore(delegate=delegate_store),
        index_build_store=FakeIndexBuildStore(
            build=build_lexical_build_record(tmp_path, duration_ms=42)
        ),
        semantic_index_build_store=FakeSemanticIndexBuildStore(),
    )
    raw_artifact_path = write_raw_benchmark_artifact(delegate_store, run=run_record)
    benchmark_run_store.record = run_record.model_copy(update={"artifact_path": raw_artifact_path})

    with pytest.raises(BenchmarkMetricsError) as exc_info:
        use_case.execute(CalculateBenchmarkMetricsRequest(run_id="run-123"))

    assert exc_info.value.details == {"run_id": "run-123", "reason": "disk full"}
    assert isinstance(exc_info.value.__cause__, OSError)


def test_calculate_benchmark_metrics_wraps_benchmark_run_update_failures(
    tmp_path: Path,
) -> None:
    runtime_paths = build_runtime_paths(tmp_path / "workspace")
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    run_record = build_run_record(
        artifact_path=runtime_paths.artifacts / "benchmarks" / "run-123" / "run.json"
    )
    benchmark_run_store = BrokenBenchmarkRunStore(record=run_record)
    use_case = CalculateBenchmarkMetricsUseCase(
        runtime_paths=runtime_paths,
        benchmark_run_store=benchmark_run_store,
        artifact_store=artifact_store,
        index_build_store=FakeIndexBuildStore(
            build=build_lexical_build_record(tmp_path, duration_ms=42)
        ),
        semantic_index_build_store=FakeSemanticIndexBuildStore(),
    )
    raw_artifact_path = write_raw_benchmark_artifact(artifact_store, run=run_record)
    benchmark_run_store.record = run_record.model_copy(update={"artifact_path": raw_artifact_path})

    with pytest.raises(BenchmarkMetricsError) as exc_info:
        use_case.execute(CalculateBenchmarkMetricsRequest(run_id="run-123"))

    assert exc_info.value.details == {"run_id": "run-123", "reason": "database locked"}
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_calculate_benchmark_metrics_rejects_artifact_with_mismatched_dataset_identity(
    tmp_path: Path,
) -> None:
    runtime_paths = build_runtime_paths(tmp_path / "workspace")
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    run_record = build_run_record(
        artifact_path=runtime_paths.artifacts / "benchmarks" / "run-123" / "run.json"
    )
    use_case, _, benchmark_run_store = build_use_case(
        tmp_path=tmp_path,
        run_record=run_record,
        lexical_build=build_lexical_build_record(tmp_path, duration_ms=42),
    )
    dataset, dataset_summary = build_dataset()
    corrupt_artifact = BenchmarkRunArtifactDocument(
        run=run_record.model_copy(update={"dataset_version": "2026-03-16"}),
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
        dataset=dataset.model_copy(update={"dataset_version": "2026-03-16"}),
        dataset_summary=dataset_summary.model_copy(update={"dataset_version": "2026-03-16"}),
        max_results=5,
        cases=build_lexical_case_artifacts(),
    )
    raw_artifact_path = write_raw_benchmark_artifact(
        artifact_store,
        run=run_record,
        artifact=corrupt_artifact,
    )
    benchmark_run_store.record = run_record.model_copy(update={"artifact_path": raw_artifact_path})

    with pytest.raises(BenchmarkArtifactCorruptError):
        use_case.execute(CalculateBenchmarkMetricsRequest(run_id="run-123"))


def test_calculate_benchmark_metrics_rejects_artifact_with_mismatched_build_context(
    tmp_path: Path,
) -> None:
    runtime_paths = build_runtime_paths(tmp_path / "workspace")
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    run_record = build_run_record(
        artifact_path=runtime_paths.artifacts / "benchmarks" / "run-123" / "run.json"
    )
    use_case, _, benchmark_run_store = build_use_case(
        tmp_path=tmp_path,
        run_record=run_record,
        lexical_build=build_lexical_build_record(tmp_path, duration_ms=42),
    )
    dataset, dataset_summary = build_dataset()
    mismatched_build = LexicalRetrievalBuildContext(
        build_id="lexical-build-other",
        indexing_config_fingerprint="index-fingerprint-123",
        lexical_engine="sqlite-fts5",
        tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
        indexed_fields=["content", "relative_path"],
    )
    corrupt_artifact = BenchmarkRunArtifactDocument(
        run=run_record,
        repository=RetrievalRepositoryContext(
            repository_id="repo-123",
            repository_name="registered-repo",
        ),
        snapshot=RetrievalSnapshotContext(
            snapshot_id="snapshot-123",
            revision_identity="revision-abc",
            revision_source="filesystem_fingerprint",
        ),
        build=mismatched_build,
        dataset=dataset,
        dataset_summary=dataset_summary,
        max_results=5,
        cases=build_lexical_case_artifacts(build_context=mismatched_build),
    )
    raw_artifact_path = write_raw_benchmark_artifact(
        artifact_store,
        run=run_record,
        artifact=corrupt_artifact,
    )
    benchmark_run_store.record = run_record.model_copy(update={"artifact_path": raw_artifact_path})

    with pytest.raises(BenchmarkArtifactCorruptError):
        use_case.execute(CalculateBenchmarkMetricsRequest(run_id="run-123"))


def test_calculate_benchmark_metrics_surfaces_hybrid_component_durations_separately(
    tmp_path: Path,
) -> None:
    runtime_paths = build_runtime_paths(tmp_path / "workspace")
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    dataset, dataset_summary = build_dataset()
    dataset = dataset.model_copy(update={"cases": [dataset.cases[0]]})
    dataset_fingerprint = build_benchmark_dataset_fingerprint(dataset)
    dataset_summary = dataset_summary.model_copy(
        update={
            "case_count": 1,
            "judgment_count": 1,
            "dataset_fingerprint": dataset_fingerprint,
        }
    )
    run_record = build_run_record(
        artifact_path=runtime_paths.artifacts / "benchmarks" / "run-123" / "run.json",
        dataset_fingerprint=dataset_fingerprint,
    ).model_copy(
        update={
            "retrieval_mode": "hybrid",
            "case_count": 1,
            "completed_case_count": 1,
        }
    )
    benchmark_run_store = FakeBenchmarkRunStore(record=run_record)
    lexical_build = build_lexical_build_record(tmp_path, duration_ms=21)
    semantic_build = build_semantic_build_record(tmp_path, duration_ms=34)
    use_case = CalculateBenchmarkMetricsUseCase(
        runtime_paths=runtime_paths,
        benchmark_run_store=benchmark_run_store,
        artifact_store=artifact_store,
        index_build_store=FakeIndexBuildStore(build=lexical_build),
        semantic_index_build_store=FakeSemanticIndexBuildStore(build=semantic_build),
    )
    hybrid_artifact = BenchmarkRunArtifactDocument(
        run=run_record,
        repository=RetrievalRepositoryContext(
            repository_id="repo-123",
            repository_name="registered-repo",
        ),
        snapshot=RetrievalSnapshotContext(
            snapshot_id="snapshot-123",
            revision_identity="revision-abc",
            revision_source="filesystem_fingerprint",
        ),
        build=HybridRetrievalBuildContext(
            build_id=HYBRID_BUILD_ID,
            rank_constant=60,
            rank_window_size=50,
            lexical_build=LexicalRetrievalBuildContext(
                build_id="lexical-build-123",
                indexing_config_fingerprint="index-fingerprint-123",
                lexical_engine="sqlite-fts5",
                tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
                indexed_fields=["content", "relative_path"],
            ),
            semantic_build=SemanticRetrievalBuildContext(
                build_id="semantic-build-123",
                provider_id="local-hash",
                model_id="fixture-local",
                model_version="2026-03-14",
                vector_engine="sqlite-exact",
                semantic_config_fingerprint="semantic-fingerprint-123",
            ),
        ),
        dataset=dataset,
        dataset_summary=dataset_summary,
        max_results=5,
        cases=[
            BenchmarkCaseExecutionArtifact(
                query_id="case-1",
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
                result=RunHybridQueryResult(
                    repository=RetrievalRepositoryContext(
                        repository_id="repo-123",
                        repository_name="registered-repo",
                    ),
                    snapshot=RetrievalSnapshotContext(
                        snapshot_id="snapshot-123",
                        revision_identity="revision-abc",
                        revision_source="filesystem_fingerprint",
                    ),
                    build=HybridRetrievalBuildContext(
                        build_id=HYBRID_BUILD_ID,
                        rank_constant=60,
                        rank_window_size=50,
                        lexical_build=LexicalRetrievalBuildContext(
                            build_id="lexical-build-123",
                            indexing_config_fingerprint="index-fingerprint-123",
                            lexical_engine="sqlite-fts5",
                            tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
                            indexed_fields=["content", "relative_path"],
                        ),
                        semantic_build=SemanticRetrievalBuildContext(
                            build_id="semantic-build-123",
                            provider_id="local-hash",
                            model_id="fixture-local",
                            model_version="2026-03-14",
                            vector_engine="sqlite-exact",
                            semantic_config_fingerprint="semantic-fingerprint-123",
                        ),
                    ),
                    query=RetrievalQueryMetadata(text="home controller"),
                    results=[
                        build_result_item(
                            rank=1,
                            relative_path="src/Controller/HomeController.php",
                        )
                    ],
                    diagnostics=HybridQueryDiagnostics(
                        match_count=1,
                        total_match_count=1,
                        truncated=False,
                        query_latency_ms=9,
                        rank_constant=60,
                        rank_window_size=50,
                        lexical=HybridComponentQueryDiagnostics(
                            match_count=1,
                            total_match_count=1,
                            truncated=False,
                            query_latency_ms=4,
                            contributed_result_count=1,
                        ),
                        semantic=HybridComponentQueryDiagnostics(
                            match_count=1,
                            total_match_count=1,
                            truncated=False,
                            query_latency_ms=6,
                            contributed_result_count=1,
                        ),
                    ),
                ),
            )
        ],
    )
    raw_artifact_path = artifact_store.write_benchmark_run_artifact(
        hybrid_artifact,
        run_id="run-123",
    )
    benchmark_run_store.record = run_record.model_copy(update={"artifact_path": raw_artifact_path})

    result = use_case.execute(CalculateBenchmarkMetricsRequest(run_id="run-123"))

    assert result.run.lexical_index_duration_ms == 21
    assert result.run.semantic_index_duration_ms == 34
    assert result.run.derived_index_duration_ms == 55

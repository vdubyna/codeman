from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codeman.application.evaluation.generate_report import (
    BenchmarkReportArtifactCorruptError,
    BenchmarkReportError,
    BenchmarkReportMetricsArtifactMissingError,
    BenchmarkReportProvenanceUnavailableError,
    BenchmarkReportRawArtifactMissingError,
    BenchmarkReportRunIncompleteError,
    BenchmarkReportRunNotFoundError,
    GenerateBenchmarkReportUseCase,
)
from codeman.config.loader import ConfigurationResolutionError
from codeman.config.retrieval_profiles import (
    RetrievalStrategyProfileEmbeddingProvidersConfig,
    RetrievalStrategyProfilePayload,
    RetrievalStrategyProfileProviderConfig,
)
from codeman.contracts.configuration import (
    ConfigurationReuseLineage,
    RunConfigurationProvenanceRecord,
    RunProvenanceWorkflowContext,
    ShowRunConfigurationProvenanceResult,
)
from codeman.contracts.evaluation import (
    BenchmarkAggregateMetrics,
    BenchmarkCaseExecutionArtifact,
    BenchmarkCaseMetricResult,
    BenchmarkDatasetDocument,
    BenchmarkDatasetSummary,
    BenchmarkIndexingDurationSummary,
    BenchmarkMetricsArtifactDocument,
    BenchmarkMetricsSummary,
    BenchmarkPerformanceSummary,
    BenchmarkQueryCase,
    BenchmarkQueryLatencySummary,
    BenchmarkQuerySourceKind,
    BenchmarkRelevanceJudgment,
    BenchmarkRunArtifactDocument,
    BenchmarkRunRecord,
    BenchmarkRunStatus,
    GenerateBenchmarkReportRequest,
    build_benchmark_dataset_fingerprint,
)
from codeman.contracts.retrieval import (
    HybridComponentQueryDiagnostics,
    HybridQueryDiagnostics,
    HybridRetrievalBuildContext,
    LexicalRetrievalBuildContext,
    RetrievalQueryDiagnostics,
    RetrievalQueryMetadata,
    RetrievalRepositoryContext,
    RetrievalResultItem,
    RetrievalSnapshotContext,
    RunHybridQueryResult,
    RunLexicalQueryResult,
    SemanticRetrievalBuildContext,
)
from codeman.infrastructure.artifacts.filesystem_artifact_store import (
    FilesystemArtifactStore,
)
from codeman.runtime import build_runtime_paths

REPORT_TIME = datetime(2026, 3, 15, 9, 2, tzinfo=UTC)
START_TIME = datetime(2026, 3, 15, 9, 0, tzinfo=UTC)
END_TIME = datetime(2026, 3, 15, 9, 1, tzinfo=UTC)


@dataclass
class FakeBenchmarkRunStore:
    record: BenchmarkRunRecord | None
    initialized: int = 0

    def initialize(self) -> None:
        self.initialized += 1

    def create_run(self, record: BenchmarkRunRecord) -> BenchmarkRunRecord:
        self.record = record
        return record

    def update_run(self, record: BenchmarkRunRecord) -> BenchmarkRunRecord:
        self.record = record
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
class FakeShowRunProvenanceUseCase:
    record: RunConfigurationProvenanceRecord | None = None
    error: Exception | None = None
    requested_run_ids: list[str] = field(default_factory=list)

    def execute(self, request: object) -> ShowRunConfigurationProvenanceResult:
        self.requested_run_ids.append(request.run_id)
        if self.error is not None:
            raise self.error
        assert self.record is not None
        return ShowRunConfigurationProvenanceResult(provenance=self.record)


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
                source_kind=BenchmarkQuerySourceKind.SYNTHETIC_REVIEWED,
                judgments=[
                    BenchmarkRelevanceJudgment(
                        relative_path="src/Controller/SettingsController.php",
                        language="php",
                        start_line=8,
                        end_line=16,
                        relevance_grade=1,
                    )
                ],
            ),
        ],
    )
    summary = BenchmarkDatasetSummary(
        dataset_path=Path("/tmp/dataset.json"),
        schema_version="1",
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        case_count=2,
        judgment_count=2,
        dataset_fingerprint=build_benchmark_dataset_fingerprint(dataset),
    )
    return dataset, summary


def build_repository_context() -> RetrievalRepositoryContext:
    return RetrievalRepositoryContext(
        repository_id="repo-123",
        repository_name="registered-repo",
    )


def build_snapshot_context() -> RetrievalSnapshotContext:
    return RetrievalSnapshotContext(
        snapshot_id="snapshot-123",
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
    )


def build_lexical_build_context() -> LexicalRetrievalBuildContext:
    return LexicalRetrievalBuildContext(
        build_id="lexical-build-123",
        indexing_config_fingerprint="index-fingerprint-123",
        lexical_engine="sqlite-fts5",
        tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
        indexed_fields=["content", "relative_path"],
        build_duration_ms=42,
    )


def build_semantic_build_context() -> SemanticRetrievalBuildContext:
    return SemanticRetrievalBuildContext(
        build_id="semantic-build-123",
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="2026-03-14",
        vector_engine="sqlite-exact",
        semantic_config_fingerprint="semantic-fingerprint-123",
        build_duration_ms=61,
    )


def build_build_context(
    retrieval_mode: str,
) -> LexicalRetrievalBuildContext | SemanticRetrievalBuildContext | HybridRetrievalBuildContext:
    lexical_build = build_lexical_build_context()
    semantic_build = build_semantic_build_context()
    if retrieval_mode == "lexical":
        return lexical_build
    if retrieval_mode == "semantic":
        return semantic_build
    return HybridRetrievalBuildContext(
        build_id="hybrid-build-123",
        rank_constant=60,
        rank_window_size=20,
        lexical_build=lexical_build,
        semantic_build=semantic_build,
    )


def build_run_record(
    *,
    artifacts_root: Path,
    retrieval_mode: str = "lexical",
    status: BenchmarkRunStatus = BenchmarkRunStatus.SUCCEEDED,
    completed_case_count: int = 2,
) -> BenchmarkRunRecord:
    run_dir = artifacts_root / "benchmarks" / "run-123"
    return BenchmarkRunRecord(
        run_id="run-123",
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        retrieval_mode=retrieval_mode,
        dataset_id="fixture-benchmark",
        dataset_version="2026-03-15",
        dataset_fingerprint=build_dataset()[1].dataset_fingerprint,
        case_count=2,
        completed_case_count=completed_case_count,
        status=status,
        artifact_path=run_dir / "run.json",
        evaluated_at_k=20,
        recall_at_k=0.75,
        mrr=0.5,
        ndcg_at_k=0.625,
        query_latency_mean_ms=7.5,
        query_latency_p95_ms=10,
        lexical_index_duration_ms=42,
        semantic_index_duration_ms=61 if retrieval_mode in {"semantic", "hybrid"} else None,
        derived_index_duration_ms=103 if retrieval_mode == "hybrid" else 42,
        metrics_artifact_path=run_dir / "metrics.json",
        metrics_computed_at=REPORT_TIME if status == BenchmarkRunStatus.SUCCEEDED else None,
        started_at=START_TIME,
        completed_at=END_TIME if status != BenchmarkRunStatus.RUNNING else None,
    )


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


def build_case_artifacts(retrieval_mode: str) -> list[BenchmarkCaseExecutionArtifact]:
    build_context = build_build_context(retrieval_mode)
    if retrieval_mode == "hybrid":
        first_result = RunHybridQueryResult(
            repository=build_repository_context(),
            snapshot=build_snapshot_context(),
            build=build_context,
            query=RetrievalQueryMetadata(text="home controller"),
            results=[build_result_item(rank=1, relative_path="src/Controller/HomeController.php")],
            diagnostics=HybridQueryDiagnostics(
                match_count=1,
                total_match_count=1,
                truncated=False,
                query_latency_ms=5,
                rank_constant=build_context.rank_constant,
                rank_window_size=build_context.rank_window_size,
                lexical=HybridComponentQueryDiagnostics(
                    match_count=1,
                    total_match_count=1,
                    truncated=False,
                    query_latency_ms=5,
                    contributed_result_count=1,
                ),
                semantic=HybridComponentQueryDiagnostics(
                    match_count=1,
                    total_match_count=1,
                    truncated=False,
                    query_latency_ms=5,
                    contributed_result_count=1,
                ),
            ),
        )
        second_result = RunHybridQueryResult(
            repository=build_repository_context(),
            snapshot=build_snapshot_context(),
            build=build_context,
            query=RetrievalQueryMetadata(text="settings controller"),
            results=[
                build_result_item(rank=1, relative_path="src/Controller/SettingsController.php")
            ],
            diagnostics=HybridQueryDiagnostics(
                match_count=1,
                total_match_count=1,
                truncated=False,
                query_latency_ms=10,
                rank_constant=build_context.rank_constant,
                rank_window_size=build_context.rank_window_size,
                lexical=HybridComponentQueryDiagnostics(
                    match_count=1,
                    total_match_count=1,
                    truncated=False,
                    query_latency_ms=10,
                    contributed_result_count=1,
                ),
                semantic=HybridComponentQueryDiagnostics(
                    match_count=1,
                    total_match_count=1,
                    truncated=False,
                    query_latency_ms=10,
                    contributed_result_count=1,
                ),
            ),
        )
    else:
        first_result = RunLexicalQueryResult(
            repository=build_repository_context(),
            snapshot=build_snapshot_context(),
            build=build_context,
            query=RetrievalQueryMetadata(text="home controller"),
            results=[build_result_item(rank=1, relative_path="src/Controller/HomeController.php")],
            diagnostics=RetrievalQueryDiagnostics(
                match_count=1,
                total_match_count=1,
                truncated=False,
                query_latency_ms=5,
            ),
        )
        second_result = RunLexicalQueryResult(
            repository=build_repository_context(),
            snapshot=build_snapshot_context(),
            build=build_context,
            query=RetrievalQueryMetadata(text="settings controller"),
            results=[
                build_result_item(rank=1, relative_path="src/Controller/SettingsController.php")
            ],
            diagnostics=RetrievalQueryDiagnostics(
                match_count=1,
                total_match_count=1,
                truncated=False,
                query_latency_ms=10,
            ),
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
            result=first_result,
        ),
        BenchmarkCaseExecutionArtifact(
            query_id="case-2",
            source_kind=BenchmarkQuerySourceKind.SYNTHETIC_REVIEWED,
            judgments=[
                BenchmarkRelevanceJudgment(
                    relative_path="src/Controller/SettingsController.php",
                    language="php",
                    start_line=8,
                    end_line=16,
                    relevance_grade=1,
                )
            ],
            result=second_result,
        ),
    ]


def build_metrics_artifact(
    *,
    run: BenchmarkRunRecord,
    retrieval_mode: str,
) -> BenchmarkMetricsArtifactDocument:
    return BenchmarkMetricsArtifactDocument(
        run=run,
        repository=build_repository_context(),
        snapshot=build_snapshot_context(),
        build=build_build_context(retrieval_mode),
        dataset=build_dataset()[1],
        summary=BenchmarkMetricsSummary(
            evaluated_at_k=20,
            metrics=BenchmarkAggregateMetrics(
                recall_at_k=0.75,
                mrr=0.5,
                ndcg_at_k=0.625,
            ),
            performance=BenchmarkPerformanceSummary(
                query_latency=BenchmarkQueryLatencySummary(
                    sample_count=2,
                    min_ms=5,
                    mean_ms=7.5,
                    median_ms=7.5,
                    p95_ms=10,
                    max_ms=10,
                ),
                indexing=BenchmarkIndexingDurationSummary(
                    lexical_build_duration_ms=42,
                    semantic_build_duration_ms=61
                    if retrieval_mode in {"semantic", "hybrid"}
                    else None,
                    derived_total_build_duration_ms=103 if retrieval_mode == "hybrid" else 42,
                ),
            ),
            metrics_computed_at=REPORT_TIME,
            artifact_path=run.metrics_artifact_path,
        ),
        cases=[
            BenchmarkCaseMetricResult(
                query_id="case-1",
                source_kind=BenchmarkQuerySourceKind.HUMAN_AUTHORED,
                evaluated_at_k=20,
                relevant_judgment_count=1,
                matched_judgment_count=1,
                first_relevant_rank=1,
                recall_at_k=1.0,
                reciprocal_rank=1.0,
                ndcg_at_k=1.0,
                query_latency_ms=5,
                judgments=[],
            ),
            BenchmarkCaseMetricResult(
                query_id="case-2",
                source_kind=BenchmarkQuerySourceKind.SYNTHETIC_REVIEWED,
                evaluated_at_k=20,
                relevant_judgment_count=1,
                matched_judgment_count=0,
                first_relevant_rank=None,
                recall_at_k=0.0,
                reciprocal_rank=0.0,
                ndcg_at_k=0.25,
                query_latency_ms=10,
                judgments=[],
            ),
        ],
    )


def build_provenance_record(retrieval_mode: str) -> RunConfigurationProvenanceRecord:
    build_context = build_build_context(retrieval_mode)
    workflow_context = RunProvenanceWorkflowContext(
        benchmark_dataset_id="fixture-benchmark",
        benchmark_dataset_version="2026-03-15",
        benchmark_dataset_fingerprint=build_dataset()[1].dataset_fingerprint,
        retrieval_mode=retrieval_mode,
        benchmark_case_count=2,
        max_results=20,
    )
    provider_id: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    indexing_config_fingerprint: str | None = None
    semantic_config_fingerprint: str | None = None

    if retrieval_mode == "lexical":
        workflow_context.lexical_build_id = build_context.build_id
        indexing_config_fingerprint = build_context.indexing_config_fingerprint
    elif retrieval_mode == "semantic":
        workflow_context.semantic_build_id = build_context.build_id
        provider_id = build_context.provider_id
        model_id = build_context.model_id
        model_version = build_context.model_version
        semantic_config_fingerprint = build_context.semantic_config_fingerprint
    else:
        workflow_context.lexical_build_id = build_context.lexical_build.build_id
        workflow_context.semantic_build_id = build_context.semantic_build.build_id
        workflow_context.rank_constant = build_context.rank_constant
        workflow_context.rank_window_size = build_context.rank_window_size
        provider_id = build_context.semantic_build.provider_id
        model_id = build_context.semantic_build.model_id
        model_version = build_context.semantic_build.model_version
        indexing_config_fingerprint = build_context.lexical_build.indexing_config_fingerprint
        semantic_config_fingerprint = build_context.semantic_build.semantic_config_fingerprint

    return RunConfigurationProvenanceRecord(
        run_id="run-123",
        workflow_type="eval.benchmark",
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        configuration_id="cfg-123",
        configuration_reuse=ConfigurationReuseLineage(
            reuse_kind="profile_reuse",
            effective_configuration_id="cfg-123",
            base_profile_id="profile-123",
            base_profile_name="fixture-profile",
        ),
        indexing_config_fingerprint=indexing_config_fingerprint,
        semantic_config_fingerprint=semantic_config_fingerprint,
        provider_id=provider_id,
        model_id=model_id,
        model_version=model_version,
        effective_config=RetrievalStrategyProfilePayload(
            embedding_providers=RetrievalStrategyProfileEmbeddingProvidersConfig(
                local_hash=RetrievalStrategyProfileProviderConfig(
                    model_id="fixture-local",
                    model_version="2026-03-14",
                    local_model_path=Path("/tmp/local-model"),
                )
            )
        ),
        workflow_context=workflow_context,
        created_at=REPORT_TIME,
    )


def write_benchmark_artifacts(
    *,
    artifact_store: FilesystemArtifactStore,
    run: BenchmarkRunRecord,
    retrieval_mode: str,
) -> None:
    dataset, dataset_summary = build_dataset()
    artifact_store.write_benchmark_run_artifact(
        BenchmarkRunArtifactDocument(
            run=run,
            repository=build_repository_context(),
            snapshot=build_snapshot_context(),
            build=build_build_context(retrieval_mode),
            dataset=dataset,
            dataset_summary=dataset_summary,
            max_results=20,
            cases=build_case_artifacts(retrieval_mode),
        ),
        run_id=run.run_id,
    )
    artifact_store.write_benchmark_metrics_artifact(
        build_metrics_artifact(run=run, retrieval_mode=retrieval_mode),
        run_id=run.run_id,
    )


def build_use_case(
    tmp_path: Path,
    *,
    retrieval_mode: str = "lexical",
    status: BenchmarkRunStatus = BenchmarkRunStatus.SUCCEEDED,
    completed_case_count: int = 2,
    provenance_error: Exception | None = None,
) -> tuple[
    GenerateBenchmarkReportUseCase,
    FilesystemArtifactStore,
    FakeBenchmarkRunStore,
    FakeShowRunProvenanceUseCase,
]:
    workspace_root = tmp_path / "workspace"
    runtime_paths = build_runtime_paths(workspace_root=workspace_root)
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    run = build_run_record(
        artifacts_root=runtime_paths.artifacts,
        retrieval_mode=retrieval_mode,
        status=status,
        completed_case_count=completed_case_count,
    )
    if status == BenchmarkRunStatus.SUCCEEDED:
        write_benchmark_artifacts(
            artifact_store=artifact_store,
            run=run,
            retrieval_mode=retrieval_mode,
        )

    run_store = FakeBenchmarkRunStore(record=run)
    provenance_use_case = FakeShowRunProvenanceUseCase(
        record=build_provenance_record(retrieval_mode),
        error=provenance_error,
    )
    use_case = GenerateBenchmarkReportUseCase(
        runtime_paths=runtime_paths,
        benchmark_run_store=run_store,
        artifact_store=artifact_store,
        show_run_provenance=provenance_use_case,
    )
    return use_case, artifact_store, run_store, provenance_use_case


def test_generate_benchmark_report_creates_deterministic_markdown_artifact(
    tmp_path: Path,
) -> None:
    use_case, artifact_store, run_store, provenance_use_case = build_use_case(tmp_path)
    progress_lines: list[str] = []

    result = use_case.execute(
        GenerateBenchmarkReportRequest(run_id="run-123"),
        progress=progress_lines.append,
    )
    first_report = artifact_store.read_benchmark_report(result.report_artifact_path)
    second_result = use_case.execute(GenerateBenchmarkReportRequest(run_id="run-123"))
    second_report = artifact_store.read_benchmark_report(second_result.report_artifact_path)

    assert run_store.initialized == 2
    assert provenance_use_case.requested_run_ids == ["run-123", "run-123"]
    assert result.report_artifact_path == (
        use_case.runtime_paths.artifacts / "benchmarks" / "run-123" / "report.md"
    )
    assert first_report == second_report
    assert "# Benchmark Report: run-123" in first_report
    assert "Retrieval Mode: lexical" in first_report
    assert "Configuration ID: cfg-123" in first_report
    assert "Reuse Kind: profile_reuse" in first_report
    assert "Base Profile Name: fixture-profile" in first_report
    assert "Recall@K | 0.7500" in first_report
    assert "case-2 | synthetic_reviewed | 0/1 | - | 0.0000 | 0.0000 | 0.2500 | 10" in first_report
    assert "api_key" not in first_report
    assert progress_lines == [
        "Loading benchmark evidence for run: run-123",
        "Writing benchmark report artifact for run: run-123",
    ]


def test_generate_benchmark_report_renders_hybrid_build_provenance(tmp_path: Path) -> None:
    use_case, artifact_store, _, _ = build_use_case(tmp_path, retrieval_mode="hybrid")

    result = use_case.execute(GenerateBenchmarkReportRequest(run_id="run-123"))
    report_text = artifact_store.read_benchmark_report(result.report_artifact_path)

    assert "Retrieval Mode: hybrid" in report_text
    assert "Fusion Strategy: rrf" in report_text
    assert "Rank Constant: 60" in report_text
    assert "Rank Window Size: 20" in report_text
    assert "Semantic Build ID: semantic-build-123" in report_text
    assert "Executed Provider: local-hash" in report_text
    assert "Executed Model: fixture-local" in report_text


def test_generate_benchmark_report_raises_for_unknown_run(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    runtime_paths = build_runtime_paths(workspace_root=workspace_root)
    use_case = GenerateBenchmarkReportUseCase(
        runtime_paths=runtime_paths,
        benchmark_run_store=FakeBenchmarkRunStore(record=None),
        artifact_store=FilesystemArtifactStore(runtime_paths.artifacts),
        show_run_provenance=FakeShowRunProvenanceUseCase(record=build_provenance_record("lexical")),
    )

    with pytest.raises(BenchmarkReportRunNotFoundError):
        use_case.execute(GenerateBenchmarkReportRequest(run_id="missing-run"))


@pytest.mark.parametrize(
    ("status", "completed_case_count"),
    [
        (BenchmarkRunStatus.RUNNING, 1),
        (BenchmarkRunStatus.FAILED, 1),
    ],
)
def test_generate_benchmark_report_refuses_incomplete_run_state(
    tmp_path: Path,
    status: BenchmarkRunStatus,
    completed_case_count: int,
) -> None:
    use_case, _, _, _ = build_use_case(
        tmp_path,
        status=status,
        completed_case_count=completed_case_count,
    )

    with pytest.raises(BenchmarkReportRunIncompleteError):
        use_case.execute(GenerateBenchmarkReportRequest(run_id="run-123"))


def test_generate_benchmark_report_raises_when_raw_artifact_is_missing(tmp_path: Path) -> None:
    use_case, _, run_store, _ = build_use_case(tmp_path)
    assert run_store.record is not None and run_store.record.artifact_path is not None
    run_store.record.artifact_path.unlink()

    with pytest.raises(BenchmarkReportRawArtifactMissingError):
        use_case.execute(GenerateBenchmarkReportRequest(run_id="run-123"))


def test_generate_benchmark_report_raises_when_metrics_artifact_is_missing(
    tmp_path: Path,
) -> None:
    use_case, _, run_store, _ = build_use_case(tmp_path)
    assert run_store.record is not None and run_store.record.metrics_artifact_path is not None
    run_store.record.metrics_artifact_path.unlink()

    with pytest.raises(BenchmarkReportMetricsArtifactMissingError):
        use_case.execute(GenerateBenchmarkReportRequest(run_id="run-123"))


@pytest.mark.parametrize(
    "provenance_error",
    [
        ConfigurationResolutionError("broken provenance", details={"run_id": "run-123"}),
        RuntimeError("unexpected provenance failure"),
    ],
)
def test_generate_benchmark_report_raises_when_provenance_is_unavailable(
    tmp_path: Path,
    provenance_error: Exception,
) -> None:
    use_case, _, _, _ = build_use_case(tmp_path, provenance_error=provenance_error)

    with pytest.raises(BenchmarkReportProvenanceUnavailableError):
        use_case.execute(GenerateBenchmarkReportRequest(run_id="run-123"))


def test_generate_benchmark_report_raises_for_mismatched_metrics_context(
    tmp_path: Path,
) -> None:
    use_case, artifact_store, run_store, _ = build_use_case(tmp_path)
    assert run_store.record is not None
    broken_artifact = build_metrics_artifact(
        run=run_store.record,
        retrieval_mode="lexical",
    ).model_copy(update={"build": build_semantic_build_context()})
    artifact_store.write_benchmark_metrics_artifact(broken_artifact, run_id="run-123")

    with pytest.raises(BenchmarkReportArtifactCorruptError):
        use_case.execute(GenerateBenchmarkReportRequest(run_id="run-123"))


def test_generate_benchmark_report_raises_for_mismatched_run_metrics_summary(
    tmp_path: Path,
) -> None:
    use_case, _, run_store, _ = build_use_case(tmp_path)
    assert run_store.record is not None
    run_store.record = run_store.record.model_copy(update={"recall_at_k": 0.5})

    with pytest.raises(BenchmarkReportArtifactCorruptError) as exc_info:
        use_case.execute(GenerateBenchmarkReportRequest(run_id="run-123"))

    assert exc_info.value.details == {
        "run_id": "run-123",
        "fields": [
            "artifact_run.recall_at_k",
            "summary.metrics.recall_at_k",
        ],
    }


def test_generate_benchmark_report_wraps_report_write_failures(
    tmp_path: Path,
) -> None:
    use_case, _, _, _ = build_use_case(tmp_path)

    class FailingReportArtifactStore(FilesystemArtifactStore):
        def write_benchmark_report(
            self,
            report_markdown: str,
            *,
            run_id: str,
        ) -> Path:
            raise OSError("disk full")

    use_case.artifact_store = FailingReportArtifactStore(use_case.runtime_paths.artifacts)

    with pytest.raises(BenchmarkReportError) as exc_info:
        use_case.execute(GenerateBenchmarkReportRequest(run_id="run-123"))

    assert exc_info.value.error_code == "benchmark_report_failed"
    assert exc_info.value.details == {
        "run_id": "run-123",
        "artifact_path": str(
            use_case.runtime_paths.artifacts / "benchmarks" / "run-123" / "report.md"
        ),
    }

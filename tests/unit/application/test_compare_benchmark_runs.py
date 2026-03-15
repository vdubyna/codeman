from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from codeman.application.evaluation.compare_runs import (
    CompareBenchmarkRunsArtifactCorruptError,
    CompareBenchmarkRunsCrossRepositoryError,
    CompareBenchmarkRunsMetricsArtifactMissingError,
    CompareBenchmarkRunsProvenanceUnavailableError,
    CompareBenchmarkRunsRawArtifactMissingError,
    CompareBenchmarkRunsRunIncompleteError,
    CompareBenchmarkRunsRunNotFoundError,
    CompareBenchmarkRunsUseCase,
)
from codeman.config.loader import ConfigurationResolutionError
from codeman.config.retrieval_profiles import RetrievalStrategyProfilePayload
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
    CompareBenchmarkRunsRequest,
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
    RunSemanticQueryResult,
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
    records: dict[str, BenchmarkRunRecord]
    initialized: int = 0

    def initialize(self) -> None:
        self.initialized += 1

    def create_run(self, record: BenchmarkRunRecord) -> BenchmarkRunRecord:
        self.records[record.run_id] = record
        return record

    def update_run(self, record: BenchmarkRunRecord) -> BenchmarkRunRecord:
        self.records[record.run_id] = record
        return record

    def get_by_run_id(self, run_id: str) -> BenchmarkRunRecord | None:
        return self.records.get(run_id)

    def list_by_repository_id(self, repository_id: str) -> list[BenchmarkRunRecord]:
        return [
            record
            for record in self.records.values()
            if record.repository_id == repository_id
        ]


@dataclass
class FakeShowRunProvenanceUseCase:
    records: dict[str, RunConfigurationProvenanceRecord] = field(default_factory=dict)
    error: Exception | None = None
    requested_run_ids: list[str] = field(default_factory=list)

    def execute(self, request: object) -> ShowRunConfigurationProvenanceResult:
        self.requested_run_ids.append(request.run_id)
        if self.error is not None:
            raise self.error
        return ShowRunConfigurationProvenanceResult(
            provenance=self.records[request.run_id]
        )


def build_effective_config() -> RetrievalStrategyProfilePayload:
    return RetrievalStrategyProfilePayload.model_validate(
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
                    "model_version": "2026-03-14",
                    "local_model_path": "/tmp/local-model",
                }
            },
        }
    )


def build_dataset(
    *,
    dataset_version: str = "2026-03-15",
) -> tuple[BenchmarkDatasetDocument, BenchmarkDatasetSummary]:
    dataset = BenchmarkDatasetDocument(
        schema_version="1",
        dataset_id="fixture-benchmark",
        dataset_version=dataset_version,
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


def build_repository_context(
    repository_id: str = "repo-123",
) -> RetrievalRepositoryContext:
    return RetrievalRepositoryContext(
        repository_id=repository_id,
        repository_name=f"repo-{repository_id}",
    )


def build_snapshot_context(
    snapshot_id: str = "snapshot-123",
) -> RetrievalSnapshotContext:
    return RetrievalSnapshotContext(
        snapshot_id=snapshot_id,
        revision_identity=f"revision-{snapshot_id}",
        revision_source="filesystem_fingerprint",
    )


def build_lexical_build_context(
    indexing_fingerprint: str = "index-fingerprint-123",
) -> LexicalRetrievalBuildContext:
    return LexicalRetrievalBuildContext(
        build_id="lexical-build-123",
        indexing_config_fingerprint=indexing_fingerprint,
        lexical_engine="sqlite-fts5",
        tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
        indexed_fields=["content", "relative_path"],
        build_duration_ms=42,
    )


def build_semantic_build_context(
    semantic_fingerprint: str = "semantic-fingerprint-123",
) -> SemanticRetrievalBuildContext:
    return SemanticRetrievalBuildContext(
        build_id="semantic-build-123",
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="2026-03-14",
        vector_engine="sqlite-exact",
        semantic_config_fingerprint=semantic_fingerprint,
        build_duration_ms=61,
    )


def build_build_context(
    retrieval_mode: str,
    *,
    indexing_fingerprint: str = "index-fingerprint-123",
    semantic_fingerprint: str = "semantic-fingerprint-123",
):
    lexical_build = build_lexical_build_context(indexing_fingerprint)
    semantic_build = build_semantic_build_context(semantic_fingerprint)
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


def build_case_artifacts(
    retrieval_mode: str,
    *,
    repository_id: str,
    snapshot_id: str,
) -> list[BenchmarkCaseExecutionArtifact]:
    build_context = build_build_context(retrieval_mode)
    if retrieval_mode == "hybrid":
        first_result = RunHybridQueryResult(
            repository=build_repository_context(repository_id),
            snapshot=build_snapshot_context(snapshot_id),
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
            repository=build_repository_context(repository_id),
            snapshot=build_snapshot_context(snapshot_id),
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
    elif retrieval_mode == "semantic":
        first_result = RunSemanticQueryResult(
            repository=build_repository_context(repository_id),
            snapshot=build_snapshot_context(snapshot_id),
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
        second_result = RunSemanticQueryResult(
            repository=build_repository_context(repository_id),
            snapshot=build_snapshot_context(snapshot_id),
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
    else:
        first_result = RunLexicalQueryResult(
            repository=build_repository_context(repository_id),
            snapshot=build_snapshot_context(snapshot_id),
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
            repository=build_repository_context(repository_id),
            snapshot=build_snapshot_context(snapshot_id),
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


def build_metric_values(
    **overrides: float | int | None,
) -> dict[str, float | int | None]:
    values: dict[str, float | int | None] = {
        "evaluated_at_k": 20,
        "recall_at_k": 0.75,
        "mrr": 0.5,
        "ndcg_at_k": 0.625,
        "query_latency_mean_ms": 7.5,
        "query_latency_p95_ms": 10,
        "lexical_index_duration_ms": 42,
        "semantic_index_duration_ms": None,
        "derived_index_duration_ms": 42,
    }
    values.update(overrides)
    return values


def build_run_record(
    *,
    run_id: str,
    artifacts_root: Path,
    dataset_summary: BenchmarkDatasetSummary,
    retrieval_mode: str = "lexical",
    repository_id: str = "repo-123",
    snapshot_id: str = "snapshot-123",
    status: BenchmarkRunStatus = BenchmarkRunStatus.SUCCEEDED,
    completed_case_count: int | None = None,
    metric_values: dict[str, float | int | None] | None = None,
) -> BenchmarkRunRecord:
    values = build_metric_values(**(metric_values or {}))
    run_dir = artifacts_root / "benchmarks" / run_id
    final_completed_case_count = (
        dataset_summary.case_count if completed_case_count is None else completed_case_count
    )
    return BenchmarkRunRecord(
        run_id=run_id,
        repository_id=repository_id,
        snapshot_id=snapshot_id,
        retrieval_mode=retrieval_mode,
        dataset_id=dataset_summary.dataset_id,
        dataset_version=dataset_summary.dataset_version,
        dataset_fingerprint=dataset_summary.dataset_fingerprint,
        case_count=dataset_summary.case_count,
        completed_case_count=final_completed_case_count,
        status=status,
        artifact_path=run_dir / "run.json",
        evaluated_at_k=values["evaluated_at_k"],
        recall_at_k=values["recall_at_k"],
        mrr=values["mrr"],
        ndcg_at_k=values["ndcg_at_k"],
        query_latency_mean_ms=values["query_latency_mean_ms"],
        query_latency_p95_ms=values["query_latency_p95_ms"],
        lexical_index_duration_ms=values["lexical_index_duration_ms"],
        semantic_index_duration_ms=values["semantic_index_duration_ms"],
        derived_index_duration_ms=values["derived_index_duration_ms"],
        metrics_artifact_path=run_dir / "metrics.json",
        metrics_computed_at=REPORT_TIME if status == BenchmarkRunStatus.SUCCEEDED else None,
        started_at=START_TIME,
        completed_at=END_TIME if status != BenchmarkRunStatus.RUNNING else None,
    )


def build_run_artifact(
    *,
    run: BenchmarkRunRecord,
    dataset: BenchmarkDatasetDocument,
    dataset_summary: BenchmarkDatasetSummary,
) -> BenchmarkRunArtifactDocument:
    return BenchmarkRunArtifactDocument(
        run=run,
        repository=build_repository_context(run.repository_id),
        snapshot=build_snapshot_context(run.snapshot_id),
        build=build_build_context(run.retrieval_mode),
        dataset=dataset,
        dataset_summary=dataset_summary,
        max_results=run.evaluated_at_k or 20,
        cases=build_case_artifacts(
            run.retrieval_mode,
            repository_id=run.repository_id,
            snapshot_id=run.snapshot_id,
        ),
    )


def build_metrics_artifact(
    *,
    run: BenchmarkRunRecord,
    dataset_summary: BenchmarkDatasetSummary,
) -> BenchmarkMetricsArtifactDocument:
    return BenchmarkMetricsArtifactDocument(
        run=run,
        repository=build_repository_context(run.repository_id),
        snapshot=build_snapshot_context(run.snapshot_id),
        build=build_build_context(run.retrieval_mode),
        dataset=dataset_summary,
        summary=BenchmarkMetricsSummary(
            evaluated_at_k=run.evaluated_at_k or 20,
            metrics=BenchmarkAggregateMetrics(
                recall_at_k=run.recall_at_k or 0.0,
                mrr=run.mrr or 0.0,
                ndcg_at_k=run.ndcg_at_k or 0.0,
            ),
            performance=BenchmarkPerformanceSummary(
                query_latency=BenchmarkQueryLatencySummary(
                    sample_count=dataset_summary.case_count,
                    min_ms=5,
                    mean_ms=run.query_latency_mean_ms,
                    median_ms=run.query_latency_mean_ms,
                    p95_ms=run.query_latency_p95_ms,
                    max_ms=run.query_latency_p95_ms,
                ),
                indexing=BenchmarkIndexingDurationSummary(
                    lexical_build_duration_ms=run.lexical_index_duration_ms,
                    semantic_build_duration_ms=run.semantic_index_duration_ms,
                    derived_total_build_duration_ms=run.derived_index_duration_ms,
                ),
            ),
            metrics_computed_at=REPORT_TIME,
            artifact_path=run.metrics_artifact_path,
        ),
        cases=[
            BenchmarkCaseMetricResult(
                query_id="case-1",
                source_kind=BenchmarkQuerySourceKind.HUMAN_AUTHORED,
                evaluated_at_k=run.evaluated_at_k or 20,
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
                evaluated_at_k=run.evaluated_at_k or 20,
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


def build_provenance_record(run: BenchmarkRunRecord) -> RunConfigurationProvenanceRecord:
    build_context = build_build_context(run.retrieval_mode)
    workflow_context = RunProvenanceWorkflowContext(
        benchmark_dataset_id=run.dataset_id,
        benchmark_dataset_version=run.dataset_version,
        benchmark_dataset_fingerprint=run.dataset_fingerprint,
        retrieval_mode=run.retrieval_mode,
        benchmark_case_count=run.case_count,
        max_results=run.evaluated_at_k,
    )
    provider_id: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    indexing_config_fingerprint: str | None = None
    semantic_config_fingerprint: str | None = None

    if run.retrieval_mode == "lexical":
        workflow_context.lexical_build_id = build_context.build_id
        indexing_config_fingerprint = build_context.indexing_config_fingerprint
    elif run.retrieval_mode == "semantic":
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
        run_id=run.run_id,
        workflow_type="eval.benchmark",
        repository_id=run.repository_id,
        snapshot_id=run.snapshot_id,
        configuration_id=f"cfg-{run.run_id}",
        configuration_reuse=ConfigurationReuseLineage(
            reuse_kind="profile_reuse",
            effective_configuration_id=f"cfg-{run.run_id}",
            base_profile_id="profile-123",
            base_profile_name="fixture-profile",
        ),
        indexing_config_fingerprint=indexing_config_fingerprint,
        semantic_config_fingerprint=semantic_config_fingerprint,
        provider_id=provider_id,
        model_id=model_id,
        model_version=model_version,
        effective_config=build_effective_config(),
        workflow_context=workflow_context,
        created_at=REPORT_TIME,
    )


def write_benchmark_artifacts(
    *,
    artifact_store: FilesystemArtifactStore,
    run: BenchmarkRunRecord,
    dataset: BenchmarkDatasetDocument,
    dataset_summary: BenchmarkDatasetSummary,
) -> None:
    artifact_store.write_benchmark_run_artifact(
        build_run_artifact(
            run=run,
            dataset=dataset,
            dataset_summary=dataset_summary,
        ),
        run_id=run.run_id,
    )
    artifact_store.write_benchmark_metrics_artifact(
        build_metrics_artifact(
            run=run,
            dataset_summary=dataset_summary,
        ),
        run_id=run.run_id,
    )


def build_use_case(
    *,
    tmp_path: Path,
    records: dict[str, BenchmarkRunRecord],
    provenance_records: dict[str, RunConfigurationProvenanceRecord],
    provenance_error: Exception | None = None,
) -> CompareBenchmarkRunsUseCase:
    workspace = tmp_path / "workspace"
    runtime_paths = build_runtime_paths(workspace_root=workspace)
    return CompareBenchmarkRunsUseCase(
        runtime_paths=runtime_paths,
        benchmark_run_store=FakeBenchmarkRunStore(records=records),
        artifact_store=FilesystemArtifactStore(runtime_paths.artifacts),
        show_run_provenance=FakeShowRunProvenanceUseCase(
            records=provenance_records,
            error=provenance_error,
        ),
    )


def test_compare_benchmark_runs_request_requires_at_least_two_run_ids() -> None:
    with pytest.raises(ValidationError):
        CompareBenchmarkRunsRequest(run_ids=["run-001"])


def test_compare_benchmark_runs_request_rejects_duplicate_run_ids() -> None:
    with pytest.raises(ValidationError):
        CompareBenchmarkRunsRequest(run_ids=["run-001", "run-001"])


def test_compare_benchmark_runs_preserves_order_and_reports_winners(
    tmp_path: Path,
) -> None:
    dataset, dataset_summary = build_dataset()
    runtime_paths = build_runtime_paths(workspace_root=tmp_path / "workspace")
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)

    lexical_run = build_run_record(
        run_id="run-001",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
        retrieval_mode="lexical",
        metric_values=build_metric_values(
            recall_at_k=0.75,
            mrr=0.5,
            ndcg_at_k=0.625,
            query_latency_mean_ms=7.5,
            semantic_index_duration_ms=None,
        ),
    )
    semantic_run = build_run_record(
        run_id="run-002",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
        retrieval_mode="semantic",
        metric_values=build_metric_values(
            recall_at_k=0.75,
            mrr=0.6,
            ndcg_at_k=0.625,
            query_latency_mean_ms=9.0,
            semantic_index_duration_ms=61,
            derived_index_duration_ms=61,
        ),
    )
    write_benchmark_artifacts(
        artifact_store=artifact_store,
        run=lexical_run,
        dataset=dataset,
        dataset_summary=dataset_summary,
    )
    write_benchmark_artifacts(
        artifact_store=artifact_store,
        run=semantic_run,
        dataset=dataset,
        dataset_summary=dataset_summary,
    )

    use_case = build_use_case(
        tmp_path=tmp_path,
        records={
            lexical_run.run_id: lexical_run,
            semantic_run.run_id: semantic_run,
        },
        provenance_records={
            lexical_run.run_id: build_provenance_record(lexical_run),
            semantic_run.run_id: build_provenance_record(semantic_run),
        },
    )

    result = use_case.execute(CompareBenchmarkRunsRequest(run_ids=["run-002", "run-001"]))

    assert [entry.run.run_id for entry in result.entries] == ["run-002", "run-001"]
    assert result.comparability.is_apples_to_apples is True
    difference_keys = {difference.key for difference in result.comparability.differences}
    assert "configuration_id" in difference_keys
    assert "provider_id" in difference_keys

    comparisons = {
        comparison.metric_key: comparison for comparison in result.metric_comparisons
    }
    assert comparisons["recall_at_k"].outcome == "tie"
    assert comparisons["recall_at_k"].winner_run_ids == ["run-002", "run-001"]
    assert comparisons["mrr"].outcome == "winner"
    assert comparisons["mrr"].winner_run_ids == ["run-002"]
    assert comparisons["query_latency_mean_ms"].winner_run_ids == ["run-001"]


def test_compare_benchmark_runs_marks_snapshot_and_dataset_differences(
    tmp_path: Path,
) -> None:
    dataset_one, summary_one = build_dataset(dataset_version="2026-03-15")
    dataset_two, summary_two = build_dataset(dataset_version="2026-03-16")
    runtime_paths = build_runtime_paths(workspace_root=tmp_path / "workspace")
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)

    first_run = build_run_record(
        run_id="run-001",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=summary_one,
        retrieval_mode="lexical",
        snapshot_id="snapshot-123",
    )
    second_run = build_run_record(
        run_id="run-002",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=summary_two,
        retrieval_mode="lexical",
        snapshot_id="snapshot-456",
    )
    write_benchmark_artifacts(
        artifact_store=artifact_store,
        run=first_run,
        dataset=dataset_one,
        dataset_summary=summary_one,
    )
    write_benchmark_artifacts(
        artifact_store=artifact_store,
        run=second_run,
        dataset=dataset_two,
        dataset_summary=summary_two,
    )
    use_case = build_use_case(
        tmp_path=tmp_path,
        records={first_run.run_id: first_run, second_run.run_id: second_run},
        provenance_records={
            first_run.run_id: build_provenance_record(first_run),
            second_run.run_id: build_provenance_record(second_run),
        },
    )

    result = use_case.execute(
        CompareBenchmarkRunsRequest(run_ids=[first_run.run_id, second_run.run_id])
    )

    difference_keys = {difference.key for difference in result.comparability.differences}
    assert result.comparability.is_apples_to_apples is False
    assert {"snapshot_id", "dataset_version", "dataset_fingerprint"} <= difference_keys
    assert any(
        "not apples-to-apples" in note for note in result.comparability.notes
    )


def test_compare_benchmark_runs_fails_for_unknown_run(tmp_path: Path) -> None:
    use_case = build_use_case(
        tmp_path=tmp_path,
        records={},
        provenance_records={},
    )

    with pytest.raises(CompareBenchmarkRunsRunNotFoundError):
        use_case.execute(
            CompareBenchmarkRunsRequest(run_ids=["run-001", "run-002"])
        )


def test_compare_benchmark_runs_fails_for_incomplete_run(tmp_path: Path) -> None:
    dataset, dataset_summary = build_dataset()
    runtime_paths = build_runtime_paths(workspace_root=tmp_path / "workspace")
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)

    incomplete_run = build_run_record(
        run_id="run-001",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
        status=BenchmarkRunStatus.RUNNING,
        completed_case_count=1,
    )
    complete_run = build_run_record(
        run_id="run-002",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
    )
    write_benchmark_artifacts(
        artifact_store=artifact_store,
        run=complete_run,
        dataset=dataset,
        dataset_summary=dataset_summary,
    )
    use_case = build_use_case(
        tmp_path=tmp_path,
        records={
            incomplete_run.run_id: incomplete_run,
            complete_run.run_id: complete_run,
        },
        provenance_records={complete_run.run_id: build_provenance_record(complete_run)},
    )

    with pytest.raises(CompareBenchmarkRunsRunIncompleteError):
        use_case.execute(
            CompareBenchmarkRunsRequest(run_ids=[incomplete_run.run_id, complete_run.run_id])
        )


def test_compare_benchmark_runs_fails_for_missing_run_artifact(tmp_path: Path) -> None:
    dataset, dataset_summary = build_dataset()
    runtime_paths = build_runtime_paths(workspace_root=tmp_path / "workspace")
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)

    missing_artifact_run = build_run_record(
        run_id="run-001",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
    )
    complete_run = build_run_record(
        run_id="run-002",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
    )
    write_benchmark_artifacts(
        artifact_store=artifact_store,
        run=complete_run,
        dataset=dataset,
        dataset_summary=dataset_summary,
    )
    use_case = build_use_case(
        tmp_path=tmp_path,
        records={
            missing_artifact_run.run_id: missing_artifact_run,
            complete_run.run_id: complete_run,
        },
        provenance_records={complete_run.run_id: build_provenance_record(complete_run)},
    )

    with pytest.raises(CompareBenchmarkRunsRawArtifactMissingError):
        use_case.execute(
            CompareBenchmarkRunsRequest(
                run_ids=[missing_artifact_run.run_id, complete_run.run_id]
            )
        )


def test_compare_benchmark_runs_fails_for_missing_metrics_artifact(
    tmp_path: Path,
) -> None:
    dataset, dataset_summary = build_dataset()
    runtime_paths = build_runtime_paths(workspace_root=tmp_path / "workspace")
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)

    missing_metrics_run = build_run_record(
        run_id="run-001",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
    )
    artifact_store.write_benchmark_run_artifact(
        build_run_artifact(
            run=missing_metrics_run,
            dataset=dataset,
            dataset_summary=dataset_summary,
        ),
        run_id=missing_metrics_run.run_id,
    )
    complete_run = build_run_record(
        run_id="run-002",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
    )
    write_benchmark_artifacts(
        artifact_store=artifact_store,
        run=complete_run,
        dataset=dataset,
        dataset_summary=dataset_summary,
    )
    use_case = build_use_case(
        tmp_path=tmp_path,
        records={
            missing_metrics_run.run_id: missing_metrics_run,
            complete_run.run_id: complete_run,
        },
        provenance_records={
            missing_metrics_run.run_id: build_provenance_record(missing_metrics_run),
            complete_run.run_id: build_provenance_record(complete_run),
        },
    )

    with pytest.raises(CompareBenchmarkRunsMetricsArtifactMissingError):
        use_case.execute(
            CompareBenchmarkRunsRequest(
                run_ids=[missing_metrics_run.run_id, complete_run.run_id]
            )
        )


def test_compare_benchmark_runs_fails_for_corrupt_metrics_artifact(
    tmp_path: Path,
) -> None:
    dataset, dataset_summary = build_dataset()
    runtime_paths = build_runtime_paths(workspace_root=tmp_path / "workspace")
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)

    corrupt_run = build_run_record(
        run_id="run-001",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
    )
    artifact_store.write_benchmark_run_artifact(
        build_run_artifact(
            run=corrupt_run,
            dataset=dataset,
            dataset_summary=dataset_summary,
        ),
        run_id=corrupt_run.run_id,
    )
    corrupt_metrics = build_metrics_artifact(
        run=corrupt_run,
        dataset_summary=dataset_summary,
    ).model_copy(update={"summary": BenchmarkMetricsSummary(
        evaluated_at_k=10,
        metrics=BenchmarkAggregateMetrics(
            recall_at_k=corrupt_run.recall_at_k or 0.0,
            mrr=corrupt_run.mrr or 0.0,
            ndcg_at_k=corrupt_run.ndcg_at_k or 0.0,
        ),
        performance=BenchmarkPerformanceSummary(
            query_latency=BenchmarkQueryLatencySummary(
                sample_count=2,
                min_ms=5,
                mean_ms=corrupt_run.query_latency_mean_ms,
                median_ms=corrupt_run.query_latency_mean_ms,
                p95_ms=corrupt_run.query_latency_p95_ms,
                max_ms=corrupt_run.query_latency_p95_ms,
            ),
            indexing=BenchmarkIndexingDurationSummary(
                lexical_build_duration_ms=corrupt_run.lexical_index_duration_ms,
                semantic_build_duration_ms=corrupt_run.semantic_index_duration_ms,
                derived_total_build_duration_ms=corrupt_run.derived_index_duration_ms,
            ),
        ),
        metrics_computed_at=REPORT_TIME,
        artifact_path=corrupt_run.metrics_artifact_path,
    )})
    artifact_store.write_benchmark_metrics_artifact(
        corrupt_metrics,
        run_id=corrupt_run.run_id,
    )

    complete_run = build_run_record(
        run_id="run-002",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
    )
    write_benchmark_artifacts(
        artifact_store=artifact_store,
        run=complete_run,
        dataset=dataset,
        dataset_summary=dataset_summary,
    )
    use_case = build_use_case(
        tmp_path=tmp_path,
        records={corrupt_run.run_id: corrupt_run, complete_run.run_id: complete_run},
        provenance_records={
            corrupt_run.run_id: build_provenance_record(corrupt_run),
            complete_run.run_id: build_provenance_record(complete_run),
        },
    )

    with pytest.raises(CompareBenchmarkRunsArtifactCorruptError):
        use_case.execute(
            CompareBenchmarkRunsRequest(run_ids=[corrupt_run.run_id, complete_run.run_id])
        )


def test_compare_benchmark_runs_fails_for_unavailable_provenance(
    tmp_path: Path,
) -> None:
    dataset, dataset_summary = build_dataset()
    runtime_paths = build_runtime_paths(workspace_root=tmp_path / "workspace")
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    first_run = build_run_record(
        run_id="run-001",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
    )
    second_run = build_run_record(
        run_id="run-002",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
    )
    write_benchmark_artifacts(
        artifact_store=artifact_store,
        run=first_run,
        dataset=dataset,
        dataset_summary=dataset_summary,
    )
    write_benchmark_artifacts(
        artifact_store=artifact_store,
        run=second_run,
        dataset=dataset,
        dataset_summary=dataset_summary,
    )
    use_case = build_use_case(
        tmp_path=tmp_path,
        records={first_run.run_id: first_run, second_run.run_id: second_run},
        provenance_records={},
        provenance_error=ConfigurationResolutionError("missing provenance"),
    )

    with pytest.raises(CompareBenchmarkRunsProvenanceUnavailableError):
        use_case.execute(
            CompareBenchmarkRunsRequest(run_ids=[first_run.run_id, second_run.run_id])
        )


def test_compare_benchmark_runs_fails_for_cross_repository_comparison(
    tmp_path: Path,
) -> None:
    dataset, dataset_summary = build_dataset()
    runtime_paths = build_runtime_paths(workspace_root=tmp_path / "workspace")
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    first_run = build_run_record(
        run_id="run-001",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
        repository_id="repo-123",
    )
    second_run = build_run_record(
        run_id="run-002",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
        repository_id="repo-999",
    )
    write_benchmark_artifacts(
        artifact_store=artifact_store,
        run=first_run,
        dataset=dataset,
        dataset_summary=dataset_summary,
    )
    write_benchmark_artifacts(
        artifact_store=artifact_store,
        run=second_run,
        dataset=dataset,
        dataset_summary=dataset_summary,
    )
    use_case = build_use_case(
        tmp_path=tmp_path,
        records={first_run.run_id: first_run, second_run.run_id: second_run},
        provenance_records={
            first_run.run_id: build_provenance_record(first_run),
            second_run.run_id: build_provenance_record(second_run),
        },
    )

    with pytest.raises(CompareBenchmarkRunsCrossRepositoryError):
        use_case.execute(
            CompareBenchmarkRunsRequest(run_ids=[first_run.run_id, second_run.run_id])
        )


def test_compare_benchmark_runs_prioritizes_cross_repository_mismatch_over_missing_evidence(
    tmp_path: Path,
) -> None:
    dataset, dataset_summary = build_dataset()
    runtime_paths = build_runtime_paths(workspace_root=tmp_path / "workspace")
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    first_run = build_run_record(
        run_id="run-001",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
        repository_id="repo-123",
    )
    second_run = build_run_record(
        run_id="run-002",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=dataset_summary,
        repository_id="repo-999",
    )
    write_benchmark_artifacts(
        artifact_store=artifact_store,
        run=first_run,
        dataset=dataset,
        dataset_summary=dataset_summary,
    )
    use_case = build_use_case(
        tmp_path=tmp_path,
        records={first_run.run_id: first_run, second_run.run_id: second_run},
        provenance_records={first_run.run_id: build_provenance_record(first_run)},
    )

    with pytest.raises(CompareBenchmarkRunsCrossRepositoryError):
        use_case.execute(
            CompareBenchmarkRunsRequest(run_ids=[first_run.run_id, second_run.run_id])
        )

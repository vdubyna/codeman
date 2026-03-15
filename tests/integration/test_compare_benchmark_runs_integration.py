from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codeman.application.evaluation.compare_runs import CompareBenchmarkRunsUseCase
from codeman.application.provenance.show_run_provenance import (
    ShowRunConfigurationProvenanceUseCase,
)
from codeman.config.retrieval_profiles import RetrievalStrategyProfilePayload
from codeman.contracts.configuration import (
    ConfigurationReuseLineage,
    RunConfigurationProvenanceRecord,
    RunProvenanceWorkflowContext,
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
    LexicalRetrievalBuildContext,
    RetrievalQueryDiagnostics,
    RetrievalQueryMetadata,
    RetrievalRepositoryContext,
    RetrievalResultItem,
    RetrievalSnapshotContext,
    RunLexicalQueryResult,
)
from codeman.infrastructure.artifacts.filesystem_artifact_store import (
    FilesystemArtifactStore,
)
from codeman.infrastructure.persistence.sqlite.engine import create_sqlite_engine
from codeman.infrastructure.persistence.sqlite.repositories.benchmark_run_repository import (
    SqliteBenchmarkRunStore,
)
from codeman.infrastructure.persistence.sqlite.repositories.run_provenance_repository import (
    SqliteRunProvenanceStore,
)
from codeman.runtime import build_runtime_paths

RUN_TIME = datetime(2026, 3, 15, 9, 0, tzinfo=UTC)


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
    dataset_version: str,
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


def build_run_record(
    *,
    run_id: str,
    artifacts_root: Path,
    dataset_summary: BenchmarkDatasetSummary,
    snapshot_id: str,
    recall_at_k: float,
) -> BenchmarkRunRecord:
    run_dir = artifacts_root / "benchmarks" / run_id
    return BenchmarkRunRecord(
        run_id=run_id,
        repository_id="repo-123",
        snapshot_id=snapshot_id,
        retrieval_mode="lexical",
        dataset_id=dataset_summary.dataset_id,
        dataset_version=dataset_summary.dataset_version,
        dataset_fingerprint=dataset_summary.dataset_fingerprint,
        case_count=2,
        completed_case_count=2,
        status=BenchmarkRunStatus.SUCCEEDED,
        artifact_path=run_dir / "run.json",
        evaluated_at_k=20,
        recall_at_k=recall_at_k,
        mrr=0.5,
        ndcg_at_k=0.625,
        query_latency_mean_ms=7.5,
        query_latency_p95_ms=10,
        lexical_index_duration_ms=42,
        semantic_index_duration_ms=None,
        derived_index_duration_ms=42,
        metrics_artifact_path=run_dir / "metrics.json",
        metrics_computed_at=RUN_TIME,
        started_at=RUN_TIME,
        completed_at=RUN_TIME,
    )


def build_repository_context() -> RetrievalRepositoryContext:
    return RetrievalRepositoryContext(
        repository_id="repo-123",
        repository_name="registered-repo",
    )


def build_snapshot_context(snapshot_id: str) -> RetrievalSnapshotContext:
    return RetrievalSnapshotContext(
        snapshot_id=snapshot_id,
        revision_identity=f"revision-{snapshot_id}",
        revision_source="filesystem_fingerprint",
    )


def build_build_context() -> LexicalRetrievalBuildContext:
    return LexicalRetrievalBuildContext(
        build_id="lexical-build-123",
        indexing_config_fingerprint="index-fingerprint-123",
        lexical_engine="sqlite-fts5",
        tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
        indexed_fields=["content", "relative_path"],
    )


def build_case_artifacts(snapshot_id: str) -> list[BenchmarkCaseExecutionArtifact]:
    first_result = RunLexicalQueryResult(
        repository=build_repository_context(),
        snapshot=build_snapshot_context(snapshot_id),
        build=build_build_context(),
        query=RetrievalQueryMetadata(text="home controller"),
        results=[
            RetrievalResultItem(
                chunk_id="chunk-1",
                relative_path="src/Controller/HomeController.php",
                language="php",
                strategy="php_structure",
                rank=1,
                score=1.0,
                start_line=4,
                end_line=10,
                start_byte=0,
                end_byte=42,
                content_preview="fixture",
                explanation="fixture",
            )
        ],
        diagnostics=RetrievalQueryDiagnostics(
            match_count=1,
            total_match_count=1,
            truncated=False,
            query_latency_ms=5,
        ),
    )
    second_result = RunLexicalQueryResult(
        repository=build_repository_context(),
        snapshot=build_snapshot_context(snapshot_id),
        build=build_build_context(),
        query=RetrievalQueryMetadata(text="settings controller"),
        results=[
            RetrievalResultItem(
                chunk_id="chunk-2",
                relative_path="src/Controller/SettingsController.php",
                language="php",
                strategy="php_structure",
                rank=1,
                score=1.0,
                start_line=8,
                end_line=16,
                start_byte=0,
                end_byte=42,
                content_preview="fixture",
                explanation="fixture",
            )
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


def write_benchmark_artifacts(
    *,
    artifact_store: FilesystemArtifactStore,
    run: BenchmarkRunRecord,
    dataset: BenchmarkDatasetDocument,
    dataset_summary: BenchmarkDatasetSummary,
) -> None:
    artifact_store.write_benchmark_run_artifact(
        BenchmarkRunArtifactDocument(
            run=run,
            repository=build_repository_context(),
            snapshot=build_snapshot_context(run.snapshot_id),
            build=build_build_context(),
            dataset=dataset,
            dataset_summary=dataset_summary,
            max_results=20,
            cases=build_case_artifacts(run.snapshot_id),
        ),
        run_id=run.run_id,
    )
    artifact_store.write_benchmark_metrics_artifact(
        BenchmarkMetricsArtifactDocument(
            run=run,
            repository=build_repository_context(),
            snapshot=build_snapshot_context(run.snapshot_id),
            build=build_build_context(),
            dataset=dataset_summary,
            summary=BenchmarkMetricsSummary(
                evaluated_at_k=20,
                metrics=BenchmarkAggregateMetrics(
                    recall_at_k=run.recall_at_k or 0.0,
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
                        semantic_build_duration_ms=None,
                        derived_total_build_duration_ms=42,
                    ),
                ),
                metrics_computed_at=RUN_TIME,
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
        ),
        run_id=run.run_id,
    )


def build_provenance_record(run: BenchmarkRunRecord) -> RunConfigurationProvenanceRecord:
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
        indexing_config_fingerprint="index-fingerprint-123",
        effective_config=build_effective_config(),
        workflow_context=RunProvenanceWorkflowContext(
            lexical_build_id="lexical-build-123",
            benchmark_dataset_id=run.dataset_id,
            benchmark_dataset_version=run.dataset_version,
            benchmark_dataset_fingerprint=run.dataset_fingerprint,
            retrieval_mode="lexical",
            benchmark_case_count=run.case_count,
            max_results=20,
        ),
        created_at=RUN_TIME,
    )


def test_compare_benchmark_runs_reads_persisted_evidence_and_marks_context_differences(
    tmp_path: Path,
) -> None:
    runtime_paths = build_runtime_paths(workspace_root=tmp_path / "workspace")
    database_path = runtime_paths.metadata_database_path
    engine = create_sqlite_engine(database_path)
    benchmark_run_store = SqliteBenchmarkRunStore(engine=engine, database_path=database_path)
    provenance_store = SqliteRunProvenanceStore(engine=engine, database_path=database_path)
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)

    benchmark_run_store.initialize()
    provenance_store.initialize()

    first_dataset, first_summary = build_dataset(dataset_version="2026-03-15")
    second_dataset, second_summary = build_dataset(dataset_version="2026-03-16")
    first_run = build_run_record(
        run_id="run-001",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=first_summary,
        snapshot_id="snapshot-123",
        recall_at_k=0.7,
    )
    second_run = build_run_record(
        run_id="run-002",
        artifacts_root=runtime_paths.artifacts,
        dataset_summary=second_summary,
        snapshot_id="snapshot-456",
        recall_at_k=0.9,
    )

    benchmark_run_store.create_run(first_run)
    benchmark_run_store.create_run(second_run)
    write_benchmark_artifacts(
        artifact_store=artifact_store,
        run=first_run,
        dataset=first_dataset,
        dataset_summary=first_summary,
    )
    write_benchmark_artifacts(
        artifact_store=artifact_store,
        run=second_run,
        dataset=second_dataset,
        dataset_summary=second_summary,
    )
    provenance_store.create_record(build_provenance_record(first_run))
    provenance_store.create_record(build_provenance_record(second_run))

    use_case = CompareBenchmarkRunsUseCase(
        runtime_paths=runtime_paths,
        benchmark_run_store=benchmark_run_store,
        artifact_store=artifact_store,
        show_run_provenance=ShowRunConfigurationProvenanceUseCase(
            provenance_store=provenance_store,
        ),
    )

    result = use_case.execute(
        CompareBenchmarkRunsRequest(run_ids=["run-002", "run-001"])
    )

    assert [entry.run.run_id for entry in result.entries] == ["run-002", "run-001"]
    assert result.comparability.is_apples_to_apples is False
    assert {
        difference.key for difference in result.comparability.differences
    } >= {"snapshot_id", "dataset_version", "dataset_fingerprint"}
    metric_comparisons = {
        comparison.metric_key: comparison for comparison in result.metric_comparisons
    }
    assert metric_comparisons["recall_at_k"].winner_run_ids == ["run-002"]

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from codeman.application.evaluation.compare_runs import (
    CompareBenchmarkRunsCrossRepositoryError,
)
from codeman.application.query.compare_retrieval_modes import (
    CompareRetrievalModesBaselineMissingError,
)
from codeman.bootstrap import bootstrap
from codeman.cli.app import app
from codeman.config.retrieval_profiles import RetrievalStrategyProfilePayload
from codeman.contracts.configuration import (
    ConfigurationReuseLineage,
    RunConfigurationProvenanceRecord,
    RunProvenanceWorkflowContext,
)
from codeman.contracts.evaluation import (
    BenchmarkAggregateMetrics,
    BenchmarkDatasetSummary,
    BenchmarkIndexingDurationSummary,
    BenchmarkMetricComparison,
    BenchmarkMetricComparisonValue,
    BenchmarkMetricsSummary,
    BenchmarkPerformanceSummary,
    BenchmarkQueryLatencySummary,
    BenchmarkRunComparability,
    BenchmarkRunComparisonEntry,
    BenchmarkRunRecord,
    BenchmarkRunStatus,
    CompareBenchmarkRunsResult,
)
from codeman.contracts.retrieval import (
    CompareRetrievalModesDiagnostics,
    CompareRetrievalModesResult,
    HybridComponentQueryDiagnostics,
    HybridQueryDiagnostics,
    HybridRetrievalBuildContext,
    LexicalRetrievalBuildContext,
    RetrievalModeComparisonEntry,
    RetrievalModeRankAlignment,
    RetrievalQueryDiagnostics,
    RetrievalQueryMetadata,
    RetrievalRepositoryContext,
    RetrievalResultItem,
    RetrievalSnapshotContext,
    SemanticRetrievalBuildContext,
)

runner = CliRunner()
RUN_TIME = datetime(2026, 3, 15, 9, 0, tzinfo=UTC)


def build_result_item(
    *,
    chunk_id: str,
    relative_path: str,
    rank: int,
    score: float,
    explanation: str,
) -> RetrievalResultItem:
    return RetrievalResultItem(
        chunk_id=chunk_id,
        relative_path=relative_path,
        language="php",
        strategy="php_structure",
        rank=rank,
        score=score,
        start_line=4,
        end_line=10,
        start_byte=32,
        end_byte=180,
        content_preview=f"preview for {chunk_id}",
        explanation=explanation,
    )


def build_compare_result(
    repository_path: Path,
    *,
    query: str = "controller home route",
) -> CompareRetrievalModesResult:
    repository = RetrievalRepositoryContext(
        repository_id="repo-123",
        repository_name=repository_path.name,
    )
    snapshot = RetrievalSnapshotContext(
        snapshot_id="snapshot-123",
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
    )
    lexical_item = build_result_item(
        chunk_id="chunk-shared",
        relative_path="src/Controller/HomeController.php",
        rank=1,
        score=-1.0,
        explanation="Matched lexical terms in path src/Controller/[HomeController].php.",
    )
    semantic_item = build_result_item(
        chunk_id="chunk-shared",
        relative_path="src/Controller/HomeController.php",
        rank=1,
        score=0.92,
        explanation="Ranked by embedding similarity against the persisted semantic index.",
    )
    hybrid_item = build_result_item(
        chunk_id="chunk-shared",
        relative_path="src/Controller/HomeController.php",
        rank=1,
        score=0.0328,
        explanation=(
            "Fused hybrid rank from lexical and semantic evidence for this persisted chunk."
        ),
    )
    return CompareRetrievalModesResult(
        query=RetrievalQueryMetadata(text=query),
        repository=repository,
        snapshot=snapshot,
        entries=[
            RetrievalModeComparisonEntry(
                retrieval_mode="lexical",
                build=LexicalRetrievalBuildContext(
                    build_id="lexical-build-123",
                    lexical_engine="sqlite-fts5",
                    tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
                    indexed_fields=["content", "relative_path"],
                ),
                diagnostics=RetrievalQueryDiagnostics(
                    match_count=1,
                    query_latency_ms=4,
                    total_match_count=1,
                    truncated=False,
                ),
                results=[lexical_item],
            ),
            RetrievalModeComparisonEntry(
                retrieval_mode="semantic",
                build=SemanticRetrievalBuildContext(
                    build_id="semantic-build-123",
                    provider_id="local-hash",
                    model_id="fixture-local",
                    model_version="2026-03-14",
                    vector_engine="sqlite-exact",
                    semantic_config_fingerprint="semantic-fingerprint-123",
                ),
                diagnostics=RetrievalQueryDiagnostics(
                    match_count=1,
                    query_latency_ms=7,
                    total_match_count=8,
                    truncated=True,
                ),
                results=[semantic_item],
            ),
            RetrievalModeComparisonEntry(
                retrieval_mode="hybrid",
                build=HybridRetrievalBuildContext(
                    build_id="hybrid-build-123",
                    rank_constant=60,
                    rank_window_size=50,
                    lexical_build=LexicalRetrievalBuildContext(
                        build_id="lexical-build-123",
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
                diagnostics=HybridQueryDiagnostics(
                    match_count=1,
                    query_latency_ms=9,
                    total_match_count=4,
                    truncated=False,
                    rank_constant=60,
                    rank_window_size=50,
                    total_match_count_is_lower_bound=False,
                    lexical=HybridComponentQueryDiagnostics(
                        match_count=2,
                        total_match_count=2,
                        query_latency_ms=4,
                        truncated=False,
                        contributed_result_count=1,
                    ),
                    semantic=HybridComponentQueryDiagnostics(
                        match_count=3,
                        total_match_count=6,
                        query_latency_ms=5,
                        truncated=True,
                        contributed_result_count=1,
                    ),
                ),
                results=[hybrid_item],
            ),
        ],
        alignment=[
            RetrievalModeRankAlignment(
                chunk_id="chunk-shared",
                relative_path="src/Controller/HomeController.php",
                language="php",
                strategy="php_structure",
                lexical_rank=1,
                semantic_rank=1,
                hybrid_rank=1,
                lexical_score=-1.0,
                semantic_score=0.92,
                hybrid_score=0.0328,
            )
        ],
        diagnostics=CompareRetrievalModesDiagnostics(
            alignment_count=1,
            overlap_count=1,
            query_latency_ms=11,
        ),
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


def build_benchmark_entry(
    *,
    run_id: str,
    repository_id: str,
    repository_name: str,
    retrieval_mode: str,
    snapshot_id: str,
    dataset_version: str,
    config_id: str,
    recall_at_k: float,
    mrr: float,
    query_latency_mean_ms: float,
) -> BenchmarkRunComparisonEntry:
    dataset = BenchmarkDatasetSummary(
        dataset_path=Path("/tmp/dataset.json"),
        schema_version="1",
        dataset_id="fixture-benchmark",
        dataset_version=dataset_version,
        case_count=2,
        judgment_count=2,
        dataset_fingerprint=f"fingerprint-{dataset_version}",
    )
    run = BenchmarkRunRecord(
        run_id=run_id,
        repository_id=repository_id,
        snapshot_id=snapshot_id,
        retrieval_mode=retrieval_mode,
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        dataset_fingerprint=dataset.dataset_fingerprint,
        case_count=2,
        completed_case_count=2,
        status=BenchmarkRunStatus.SUCCEEDED,
        artifact_path=Path(f"/tmp/{run_id}/run.json"),
        evaluated_at_k=20,
        recall_at_k=recall_at_k,
        mrr=mrr,
        ndcg_at_k=0.625,
        query_latency_mean_ms=query_latency_mean_ms,
        query_latency_p95_ms=10,
        lexical_index_duration_ms=42,
        semantic_index_duration_ms=61 if retrieval_mode == "semantic" else None,
        derived_index_duration_ms=61 if retrieval_mode == "semantic" else 42,
        metrics_artifact_path=Path(f"/tmp/{run_id}/metrics.json"),
        metrics_computed_at=RUN_TIME,
        started_at=RUN_TIME,
        completed_at=RUN_TIME,
    )
    build = (
        LexicalRetrievalBuildContext(
            build_id=f"{run_id}-lexical-build",
            indexing_config_fingerprint="index-fingerprint-123",
            lexical_engine="sqlite-fts5",
            tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
            indexed_fields=["content", "relative_path"],
        )
        if retrieval_mode == "lexical"
        else SemanticRetrievalBuildContext(
            build_id=f"{run_id}-semantic-build",
            provider_id="local-hash",
            model_id="fixture-local",
            model_version="2026-03-14",
            vector_engine="sqlite-exact",
            semantic_config_fingerprint="semantic-fingerprint-123",
        )
    )
    return BenchmarkRunComparisonEntry(
        run=run,
        repository=RetrievalRepositoryContext(
            repository_id=repository_id,
            repository_name=repository_name,
        ),
        snapshot=RetrievalSnapshotContext(
            snapshot_id=snapshot_id,
            revision_identity=f"revision-{snapshot_id}",
            revision_source="filesystem_fingerprint",
        ),
        build=build,
        dataset=dataset,
        metrics=BenchmarkMetricsSummary(
            evaluated_at_k=20,
            metrics=BenchmarkAggregateMetrics(
                recall_at_k=recall_at_k,
                mrr=mrr,
                ndcg_at_k=0.625,
            ),
            performance=BenchmarkPerformanceSummary(
                query_latency=BenchmarkQueryLatencySummary(
                    sample_count=2,
                    min_ms=5,
                    mean_ms=query_latency_mean_ms,
                    median_ms=query_latency_mean_ms,
                    p95_ms=10,
                    max_ms=10,
                ),
                indexing=BenchmarkIndexingDurationSummary(
                    lexical_build_duration_ms=42,
                    semantic_build_duration_ms=61 if retrieval_mode == "semantic" else None,
                    derived_total_build_duration_ms=61 if retrieval_mode == "semantic" else 42,
                ),
            ),
            metrics_computed_at=RUN_TIME,
            artifact_path=Path(f"/tmp/{run_id}/metrics.json"),
        ),
        provenance=RunConfigurationProvenanceRecord(
            run_id=run_id,
            workflow_type="eval.benchmark",
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            configuration_id=config_id,
            configuration_reuse=ConfigurationReuseLineage(
                reuse_kind="profile_reuse",
                effective_configuration_id=config_id,
                base_profile_id="profile-123",
                base_profile_name="fixture-profile",
            ),
            indexing_config_fingerprint="index-fingerprint-123",
            semantic_config_fingerprint=(
                "semantic-fingerprint-123" if retrieval_mode == "semantic" else None
            ),
            provider_id="local-hash" if retrieval_mode == "semantic" else None,
            model_id="fixture-local" if retrieval_mode == "semantic" else None,
            model_version="2026-03-14" if retrieval_mode == "semantic" else None,
            effective_config=build_effective_config(),
            workflow_context=RunProvenanceWorkflowContext(
                benchmark_dataset_id=dataset.dataset_id,
                benchmark_dataset_version=dataset.dataset_version,
                benchmark_dataset_fingerprint=dataset.dataset_fingerprint,
                retrieval_mode=retrieval_mode,
                benchmark_case_count=2,
                max_results=20,
            ),
            created_at=RUN_TIME,
        ),
    )


def build_benchmark_compare_result(repository_path: Path) -> CompareBenchmarkRunsResult:
    first_entry = build_benchmark_entry(
        run_id="run-001",
        repository_id="repo-123",
        repository_name=repository_path.name,
        retrieval_mode="lexical",
        snapshot_id="snapshot-123",
        dataset_version="2026-03-15",
        config_id="cfg-run-001",
        recall_at_k=0.7,
        mrr=0.5,
        query_latency_mean_ms=7.5,
    )
    second_entry = build_benchmark_entry(
        run_id="run-002",
        repository_id="repo-123",
        repository_name=repository_path.name,
        retrieval_mode="semantic",
        snapshot_id="snapshot-123",
        dataset_version="2026-03-15",
        config_id="cfg-run-002",
        recall_at_k=0.8,
        mrr=0.5,
        query_latency_mean_ms=9.0,
    )
    return CompareBenchmarkRunsResult(
        repository=first_entry.repository,
        entries=[first_entry, second_entry],
        metric_comparisons=[
            BenchmarkMetricComparison(
                metric_key="recall_at_k",
                label="Recall@K",
                direction="higher_is_better",
                outcome="winner",
                best_value=0.8,
                winner_run_ids=["run-002"],
                values=[
                    BenchmarkMetricComparisonValue(
                        run_id="run-001",
                        retrieval_mode="lexical",
                        value=0.7,
                    ),
                    BenchmarkMetricComparisonValue(
                        run_id="run-002",
                        retrieval_mode="semantic",
                        value=0.8,
                    ),
                ],
            ),
            BenchmarkMetricComparison(
                metric_key="mrr",
                label="MRR",
                direction="higher_is_better",
                outcome="tie",
                best_value=0.5,
                winner_run_ids=["run-001", "run-002"],
                values=[
                    BenchmarkMetricComparisonValue(
                        run_id="run-001",
                        retrieval_mode="lexical",
                        value=0.5,
                    ),
                    BenchmarkMetricComparisonValue(
                        run_id="run-002",
                        retrieval_mode="semantic",
                        value=0.5,
                    ),
                ],
            ),
        ],
        comparability=BenchmarkRunComparability(
            is_apples_to_apples=True,
            notes=[
                (
                    "Benchmark context is apples-to-apples across snapshot, "
                    "dataset identity, evaluated cutoff, and case count."
                ),
                "Compared runs resolved different effective configuration ids.",
            ],
        ),
    )


def test_compare_query_modes_command_renders_text_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubCompareRetrievalModesUseCase:
        def execute(self, _request: object) -> CompareRetrievalModesResult:
            return build_compare_result(target_repo.resolve())

    container.compare_retrieval_modes = StubCompareRetrievalModesUseCase()

    result = runner.invoke(
        app,
        ["compare", "query-modes", "repo-123", "controller home route"],
        obj=container,
    )

    assert result.exit_code == 0, result.stdout
    assert "Compared Modes: lexical, semantic, hybrid" in result.stdout
    assert "Rank Alignment:" in result.stdout
    assert "delta(h-l)=0" in result.stdout
    assert "Lexical Results:" in result.stdout
    assert "Semantic Results:" in result.stdout
    assert "Hybrid Results:" in result.stdout
    assert "Running retrieval mode comparison for repository" in result.stderr


def test_compare_query_modes_command_accepts_option_like_query_via_explicit_flag(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)
    seen_requests: list[object] = []

    class StubCompareRetrievalModesUseCase:
        def execute(self, request: object) -> CompareRetrievalModesResult:
            seen_requests.append(request)
            return build_compare_result(
                target_repo.resolve(),
                query="--query",
            )

    container.compare_retrieval_modes = StubCompareRetrievalModesUseCase()

    result = runner.invoke(
        app,
        [
            "compare",
            "query-modes",
            "repo-123",
            "--query=--query",
            "--output-format",
            "json",
        ],
        obj=container,
    )

    payload = json.loads(result.stdout.splitlines()[-1])

    assert result.exit_code == 0, result.stdout
    assert seen_requests[0].query_text == "--query"
    assert payload["ok"] is True
    assert payload["data"]["query"]["text"] == "--query"
    assert payload["meta"]["command"] == "compare.query_modes"


def test_compare_query_modes_command_returns_json_failure_for_missing_baseline(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubCompareRetrievalModesUseCase:
        def execute(self, _request: object) -> object:
            raise CompareRetrievalModesBaselineMissingError(
                "Comparison cannot run because the semantic retrieval mode is unavailable.",
                details={
                    "mode": "semantic",
                    "mode_error_code": "semantic_build_baseline_missing",
                },
            )

    container.compare_retrieval_modes = StubCompareRetrievalModesUseCase()

    result = runner.invoke(
        app,
        [
            "compare",
            "query-modes",
            "repo-123",
            "controller home route",
            "--output-format",
            "json",
        ],
        obj=container,
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 52
    assert payload["ok"] is False
    assert payload["error"]["code"] == "compare_retrieval_mode_baseline_missing"
    assert payload["error"]["details"]["mode"] == "semantic"
    assert payload["meta"]["command"] == "compare.query_modes"


def test_compare_benchmark_runs_command_renders_text_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubCompareBenchmarkRunsUseCase:
        def execute(self, _request: object, *, progress: object | None = None) -> object:
            if progress is not None:
                progress("Loading benchmark comparison evidence for run: run-001")
            return build_benchmark_compare_result(target_repo.resolve())

    container.compare_benchmark_runs = StubCompareBenchmarkRunsUseCase()

    result = runner.invoke(
        app,
        [
            "compare",
            "benchmark-runs",
            "--run-id",
            "run-001",
            "--run-id",
            "run-002",
        ],
        obj=container,
    )

    assert result.exit_code == 0, result.stdout
    assert "Benchmark run comparison completed." in result.stdout
    assert "Run Summaries:" in result.stdout
    assert "Metric Winners:" in result.stdout
    assert "Recall@K (higher is better): winner: run-002" in result.stdout
    assert "MRR (higher is better): tie: run-001, run-002" in result.stdout
    assert "Running benchmark comparison for runs: run-001, run-002" in result.stderr
    assert "Loading benchmark comparison evidence for run: run-001" in result.stderr


def test_compare_benchmark_runs_command_accepts_repeated_run_ids_and_returns_json(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)
    seen_requests: list[object] = []

    class StubCompareBenchmarkRunsUseCase:
        def execute(self, request: object, *, progress: object | None = None) -> object:
            seen_requests.append(request)
            if progress is not None:
                progress("Loading benchmark comparison evidence for run: run-001")
            return build_benchmark_compare_result(target_repo.resolve())

    container.compare_benchmark_runs = StubCompareBenchmarkRunsUseCase()

    result = runner.invoke(
        app,
        [
            "compare",
            "benchmark-runs",
            "--run-id",
            "run-001",
            "--run-id",
            "run-002",
            "--output-format",
            "json",
        ],
        obj=container,
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 0, result.stdout
    assert seen_requests[0].run_ids == ["run-001", "run-002"]
    assert payload["ok"] is True
    assert payload["data"]["entries"][0]["run"]["run_id"] == "run-001"
    assert payload["meta"]["command"] == "compare.benchmark_runs"
    assert "Benchmark run comparison completed." not in result.stdout
    assert "Running benchmark comparison for runs: run-001, run-002" in result.stderr


def test_compare_benchmark_runs_command_returns_failure_envelope_for_invalid_input(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container = bootstrap(workspace_root=workspace)

    result = runner.invoke(
        app,
        [
            "compare",
            "benchmark-runs",
            "--run-id",
            "run-001",
            "--output-format",
            "json",
        ],
        obj=container,
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 2
    assert payload["ok"] is False
    assert payload["error"]["code"] == "input_validation_failed"
    assert payload["meta"]["command"] == "compare.benchmark_runs"


def test_compare_benchmark_runs_command_rejects_duplicate_run_ids(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container = bootstrap(workspace_root=workspace)

    result = runner.invoke(
        app,
        [
            "compare",
            "benchmark-runs",
            "--run-id",
            "run-001",
            "--run-id",
            "run-001",
            "--output-format",
            "json",
        ],
        obj=container,
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 2
    assert payload["ok"] is False
    assert payload["error"]["code"] == "input_validation_failed"
    assert payload["meta"]["command"] == "compare.benchmark_runs"


def test_compare_benchmark_runs_command_returns_failure_envelope_for_use_case_error(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubCompareBenchmarkRunsUseCase:
        def execute(self, _request: object, *, progress: object | None = None) -> object:
            raise CompareBenchmarkRunsCrossRepositoryError(
                "Benchmark comparison cannot compare runs from different repositories.",
                details={
                    "repositories_by_run_id": {
                        "run-001": "repo-123",
                        "run-002": "repo-999",
                    }
                },
            )

    container.compare_benchmark_runs = StubCompareBenchmarkRunsUseCase()

    result = runner.invoke(
        app,
        [
            "compare",
            "benchmark-runs",
            "--run-id",
            "run-001",
            "--run-id",
            "run-002",
            "--output-format",
            "json",
        ],
        obj=container,
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 88
    assert payload["ok"] is False
    assert payload["error"]["code"] == "compare_benchmark_run_repository_mismatch"
    assert payload["meta"]["command"] == "compare.benchmark_runs"

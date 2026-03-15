"""Calculate and persist metrics for one completed benchmark run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha1
from typing import Any

from pydantic import ValidationError

from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.application.ports.benchmark_run_store_port import BenchmarkRunStorePort
from codeman.application.ports.index_build_store_port import IndexBuildStorePort
from codeman.application.ports.semantic_index_build_store_port import (
    SemanticIndexBuildStorePort,
)
from codeman.contracts.errors import ErrorCode
from codeman.contracts.evaluation import (
    BenchmarkCaseMetricResult,
    BenchmarkIndexingDurationSummary,
    BenchmarkMetricsArtifactDocument,
    BenchmarkMetricsSummary,
    BenchmarkPerformanceSummary,
    BenchmarkRunArtifactDocument,
    BenchmarkRunRecord,
    BenchmarkRunStatus,
    CalculateBenchmarkMetricsRequest,
    CalculateBenchmarkMetricsResult,
    build_benchmark_dataset_fingerprint,
)
from codeman.contracts.retrieval import (
    HybridRetrievalBuildContext,
    LexicalRetrievalBuildContext,
    SemanticRetrievalBuildContext,
)
from codeman.domain.evaluation import (
    BenchmarkMetricsInputShapeError as DomainBenchmarkMetricsInputShapeError,
)
from codeman.domain.evaluation import (
    aggregate_benchmark_metrics,
    calculate_benchmark_case_metrics,
    summarize_query_latencies,
)
from codeman.runtime import RuntimePaths, provision_runtime_paths

__all__ = [
    "BenchmarkArtifactCorruptError",
    "BenchmarkArtifactMissingError",
    "BenchmarkMetricsError",
    "BenchmarkMetricsInputShapeError",
    "BenchmarkRunIncompleteError",
    "BenchmarkRunNotFoundError",
    "CalculateBenchmarkMetricsUseCase",
]


class BenchmarkMetricsError(Exception):
    """Base exception for benchmark metrics calculation failures."""

    exit_code = 68
    error_code = ErrorCode.BENCHMARK_METRICS_CALCULATION_FAILED

    def __init__(self, message: str, *, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class BenchmarkRunNotFoundError(BenchmarkMetricsError):
    """Raised when metrics are requested for an unknown benchmark run."""

    exit_code = 69
    error_code = ErrorCode.BENCHMARK_RUN_NOT_FOUND


class BenchmarkArtifactMissingError(BenchmarkMetricsError):
    """Raised when the persisted raw benchmark artifact cannot be loaded."""

    exit_code = 70
    error_code = ErrorCode.BENCHMARK_ARTIFACT_MISSING


class BenchmarkArtifactCorruptError(BenchmarkMetricsError):
    """Raised when the persisted raw benchmark artifact is unreadable or inconsistent."""

    exit_code = 71
    error_code = ErrorCode.BENCHMARK_ARTIFACT_CORRUPT


class BenchmarkRunIncompleteError(BenchmarkMetricsError):
    """Raised when metrics are requested for a run that is not truthfully complete."""

    exit_code = 72
    error_code = ErrorCode.BENCHMARK_RUN_INCOMPLETE


class BenchmarkMetricsInputShapeError(BenchmarkMetricsError):
    """Raised when the persisted ranking shape cannot be evaluated deterministically."""

    exit_code = 73
    error_code = ErrorCode.BENCHMARK_METRICS_INPUT_UNSUPPORTED


@dataclass(slots=True)
class CalculateBenchmarkMetricsUseCase:
    """Calculate and persist benchmark metrics for one completed benchmark run."""

    runtime_paths: RuntimePaths
    benchmark_run_store: BenchmarkRunStorePort
    artifact_store: ArtifactStorePort
    index_build_store: IndexBuildStorePort
    semantic_index_build_store: SemanticIndexBuildStorePort

    def execute(
        self,
        request: CalculateBenchmarkMetricsRequest,
    ) -> CalculateBenchmarkMetricsResult:
        """Calculate benchmark metrics from the persisted raw benchmark artifact."""

        provision_runtime_paths(self.runtime_paths)
        self.benchmark_run_store.initialize()
        self.index_build_store.initialize()
        self.semantic_index_build_store.initialize()

        run = self.benchmark_run_store.get_by_run_id(request.run_id)
        if run is None:
            raise BenchmarkRunNotFoundError(
                f"Benchmark run is not registered: {request.run_id}",
            )
        if run.status != BenchmarkRunStatus.SUCCEEDED or run.completed_case_count != run.case_count:
            raise BenchmarkRunIncompleteError(
                "Benchmark metrics can only be calculated for a completed successful run.",
            )
        if run.artifact_path is None:
            raise BenchmarkArtifactMissingError(
                "Benchmark metrics require the persisted raw benchmark artifact.",
            )

        artifact = self._load_artifact(run)
        try:
            case_metrics = self._calculate_case_metrics(artifact)
            aggregate_metrics = aggregate_benchmark_metrics(case_metrics)
            performance_summary = BenchmarkPerformanceSummary(
                query_latency=summarize_query_latencies(
                    [case.result.diagnostics.query_latency_ms for case in artifact.cases]
                ),
                indexing=self._summarize_indexing_durations(artifact),
            )
            metrics_computed_at = datetime.now(UTC)
            metrics_summary = BenchmarkMetricsSummary(
                evaluated_at_k=artifact.max_results,
                metrics=aggregate_metrics,
                performance=performance_summary,
                metrics_computed_at=metrics_computed_at,
            )
            updated_run = run.model_copy(
                update={
                    "evaluated_at_k": artifact.max_results,
                    "recall_at_k": aggregate_metrics.recall_at_k,
                    "mrr": aggregate_metrics.mrr,
                    "ndcg_at_k": aggregate_metrics.ndcg_at_k,
                    "query_latency_mean_ms": performance_summary.query_latency.mean_ms,
                    "query_latency_p95_ms": performance_summary.query_latency.p95_ms,
                    "lexical_index_duration_ms": (
                        performance_summary.indexing.lexical_build_duration_ms
                    ),
                    "semantic_index_duration_ms": (
                        performance_summary.indexing.semantic_build_duration_ms
                    ),
                    "derived_index_duration_ms": (
                        performance_summary.indexing.derived_total_build_duration_ms
                    ),
                    "metrics_computed_at": metrics_computed_at,
                }
            )
            metrics_artifact = BenchmarkMetricsArtifactDocument(
                run=updated_run,
                repository=artifact.repository,
                snapshot=artifact.snapshot,
                build=artifact.build,
                dataset=artifact.dataset_summary,
                summary=metrics_summary,
                cases=case_metrics,
            )
            metrics_artifact_path = self.artifact_store.write_benchmark_metrics_artifact(
                metrics_artifact,
                run_id=run.run_id,
            )
            updated_run = updated_run.model_copy(
                update={"metrics_artifact_path": metrics_artifact_path}
            )
            metrics_summary = metrics_summary.model_copy(
                update={"artifact_path": metrics_artifact_path}
            )
            self.artifact_store.write_benchmark_metrics_artifact(
                metrics_artifact.model_copy(
                    update={
                        "run": updated_run,
                        "summary": metrics_summary,
                    }
                ),
                run_id=run.run_id,
            )
            self.benchmark_run_store.update_run(updated_run)
        except BenchmarkMetricsError:
            raise
        except Exception as exc:
            raise BenchmarkMetricsError(
                f"Benchmark metrics calculation failed for run: {request.run_id}",
                details={
                    "run_id": request.run_id,
                    "reason": str(exc),
                },
            ) from exc
        return CalculateBenchmarkMetricsResult(run=updated_run, metrics=metrics_summary)

    def _load_artifact(self, run: BenchmarkRunRecord) -> BenchmarkRunArtifactDocument:
        try:
            artifact = self.artifact_store.read_benchmark_run_artifact(run.artifact_path)
        except FileNotFoundError as exc:
            raise BenchmarkArtifactMissingError(
                "Benchmark metrics require the persisted raw benchmark artifact.",
            ) from exc
        except OSError as exc:
            raise BenchmarkArtifactMissingError(
                "Benchmark metrics require the persisted raw benchmark artifact.",
            ) from exc
        except ValidationError as exc:
            raise BenchmarkArtifactCorruptError(
                (
                    "Benchmark metrics cannot be calculated because the raw "
                    "benchmark artifact is corrupt."
                ),
            ) from exc

        if artifact.failure is not None:
            raise BenchmarkRunIncompleteError(
                "Benchmark metrics cannot be calculated for failed or partial benchmark artifacts.",
            )
        if artifact.run.status != BenchmarkRunStatus.SUCCEEDED:
            raise BenchmarkRunIncompleteError(
                "Benchmark metrics can only be calculated for a completed successful run.",
            )
        if len(artifact.cases) != artifact.run.case_count:
            raise BenchmarkRunIncompleteError(
                "Benchmark metrics cannot be calculated for a partial benchmark artifact.",
            )
        self._validate_artifact_identity(artifact, run)
        return artifact

    def _validate_artifact_identity(
        self,
        artifact: BenchmarkRunArtifactDocument,
        run: BenchmarkRunRecord,
    ) -> None:
        artifact_dataset_fingerprint = build_benchmark_dataset_fingerprint(artifact.dataset)
        mismatches: list[str] = []
        expected_values: tuple[tuple[str, object, object], ...] = (
            ("run.run_id", artifact.run.run_id, run.run_id),
            ("run.repository_id", artifact.run.repository_id, run.repository_id),
            ("run.snapshot_id", artifact.run.snapshot_id, run.snapshot_id),
            ("run.retrieval_mode", artifact.run.retrieval_mode, run.retrieval_mode),
            ("run.dataset_id", artifact.run.dataset_id, run.dataset_id),
            ("run.dataset_version", artifact.run.dataset_version, run.dataset_version),
            (
                "run.dataset_fingerprint",
                artifact.run.dataset_fingerprint,
                run.dataset_fingerprint,
            ),
            ("run.case_count", artifact.run.case_count, run.case_count),
            (
                "run.completed_case_count",
                artifact.run.completed_case_count,
                run.completed_case_count,
            ),
            ("repository.repository_id", artifact.repository.repository_id, run.repository_id),
            ("snapshot.snapshot_id", artifact.snapshot.snapshot_id, run.snapshot_id),
            ("dataset.dataset_id", artifact.dataset.dataset_id, run.dataset_id),
            ("dataset.dataset_version", artifact.dataset.dataset_version, run.dataset_version),
            (
                "dataset_summary.dataset_id",
                artifact.dataset_summary.dataset_id,
                run.dataset_id,
            ),
            (
                "dataset_summary.dataset_version",
                artifact.dataset_summary.dataset_version,
                run.dataset_version,
            ),
            (
                "dataset_summary.dataset_fingerprint",
                artifact.dataset_summary.dataset_fingerprint,
                run.dataset_fingerprint,
            ),
            (
                "dataset_summary.case_count",
                artifact.dataset_summary.case_count,
                run.case_count,
            ),
            ("dataset_fingerprint", artifact_dataset_fingerprint, run.dataset_fingerprint),
        )
        for field_name, actual, expected in expected_values:
            if actual != expected:
                mismatches.append(field_name)

        if run.artifact_path is not None and artifact.run.artifact_path != run.artifact_path:
            mismatches.append("run.artifact_path")

        dataset_query_ids = [case.query_id for case in artifact.dataset.cases]
        artifact_query_ids = [case.query_id for case in artifact.cases]
        if artifact_query_ids != dataset_query_ids:
            mismatches.append("cases.query_id_order")

        for artifact_case, dataset_case in zip(
            artifact.cases,
            artifact.dataset.cases,
            strict=False,
        ):
            if artifact_case.judgments != dataset_case.judgments:
                mismatches.append(f"cases[{artifact_case.query_id}].judgments")
            if artifact_case.result.repository != artifact.repository:
                mismatches.append(f"cases[{artifact_case.query_id}].repository")
            if artifact_case.result.snapshot != artifact.snapshot:
                mismatches.append(f"cases[{artifact_case.query_id}].snapshot")
            if not self._case_build_matches_artifact_build(
                case_build=artifact_case.result.build,
                artifact_build=artifact.build,
            ):
                mismatches.append(f"cases[{artifact_case.query_id}].build")

        if mismatches:
            raise BenchmarkArtifactCorruptError(
                (
                    "Benchmark metrics cannot be calculated because the raw benchmark "
                    "artifact does not match the stored run."
                ),
            )

        self._validate_build_context(
            build=artifact.build,
            repository_id=run.repository_id,
            snapshot_id=run.snapshot_id,
        )

    def _validate_build_context(
        self,
        *,
        build: (
            LexicalRetrievalBuildContext
            | SemanticRetrievalBuildContext
            | HybridRetrievalBuildContext
        ),
        repository_id: str,
        snapshot_id: str,
    ) -> None:
        if isinstance(build, LexicalRetrievalBuildContext):
            self._validate_lexical_build_context(
                build=build,
                repository_id=repository_id,
                snapshot_id=snapshot_id,
            )
            return
        if isinstance(build, SemanticRetrievalBuildContext):
            self._validate_semantic_build_context(
                build=build,
                repository_id=repository_id,
                snapshot_id=snapshot_id,
            )
            return

        self._validate_lexical_build_context(
            build=build.lexical_build,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
        )
        self._validate_semantic_build_context(
            build=build.semantic_build,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
        )
        expected_build_id = _build_hybrid_context_id(
            lexical_build_id=build.lexical_build.build_id,
            semantic_build_id=build.semantic_build.build_id,
        )
        if build.build_id != expected_build_id:
            raise BenchmarkArtifactCorruptError(
                (
                    "Benchmark metrics cannot be calculated because the raw benchmark "
                    "artifact build context is inconsistent."
                ),
            )

    def _case_build_matches_artifact_build(
        self,
        *,
        case_build: (
            LexicalRetrievalBuildContext
            | SemanticRetrievalBuildContext
            | HybridRetrievalBuildContext
        ),
        artifact_build: (
            LexicalRetrievalBuildContext
            | SemanticRetrievalBuildContext
            | HybridRetrievalBuildContext
        ),
    ) -> bool:
        if isinstance(case_build, LexicalRetrievalBuildContext) and isinstance(
            artifact_build,
            LexicalRetrievalBuildContext,
        ):
            return self._lexical_build_identity_matches(case_build, artifact_build)
        if isinstance(case_build, SemanticRetrievalBuildContext) and isinstance(
            artifact_build,
            SemanticRetrievalBuildContext,
        ):
            return self._semantic_build_identity_matches(case_build, artifact_build)
        if not isinstance(case_build, HybridRetrievalBuildContext) or not isinstance(
            artifact_build,
            HybridRetrievalBuildContext,
        ):
            return False
        return (
            case_build.build_id == artifact_build.build_id
            and case_build.rank_constant == artifact_build.rank_constant
            and case_build.rank_window_size == artifact_build.rank_window_size
            and self._lexical_build_identity_matches(
                case_build.lexical_build,
                artifact_build.lexical_build,
            )
            and self._semantic_build_identity_matches(
                case_build.semantic_build,
                artifact_build.semantic_build,
            )
        )

    def _validate_lexical_build_context(
        self,
        *,
        build: LexicalRetrievalBuildContext,
        repository_id: str,
        snapshot_id: str,
    ) -> None:
        persisted_build = self.index_build_store.get_by_build_id(build.build_id)
        if persisted_build is None:
            raise BenchmarkArtifactCorruptError(
                (
                    "Benchmark metrics cannot be calculated because the raw benchmark "
                    "artifact build context is inconsistent."
                ),
            )
        if not self._lexical_build_identity_matches(
            build,
            LexicalRetrievalBuildContext(
                build_id=persisted_build.build_id,
                indexing_config_fingerprint=persisted_build.indexing_config_fingerprint,
                lexical_engine=persisted_build.lexical_engine,
                tokenizer_spec=persisted_build.tokenizer_spec,
                indexed_fields=list(persisted_build.indexed_fields),
                build_duration_ms=persisted_build.build_duration_ms,
            ),
        ):
            raise BenchmarkArtifactCorruptError(
                (
                    "Benchmark metrics cannot be calculated because the raw benchmark "
                    "artifact build context is inconsistent."
                ),
            )
        if (
            persisted_build.repository_id != repository_id
            or persisted_build.snapshot_id != snapshot_id
            or (
                build.build_duration_ms is not None
                and build.build_duration_ms != persisted_build.build_duration_ms
            )
        ):
            raise BenchmarkArtifactCorruptError(
                (
                    "Benchmark metrics cannot be calculated because the raw benchmark "
                    "artifact build context is inconsistent."
                ),
            )

    def _validate_semantic_build_context(
        self,
        *,
        build: SemanticRetrievalBuildContext,
        repository_id: str,
        snapshot_id: str,
    ) -> None:
        persisted_build = self.semantic_index_build_store.get_by_build_id(build.build_id)
        if persisted_build is None:
            raise BenchmarkArtifactCorruptError(
                (
                    "Benchmark metrics cannot be calculated because the raw benchmark "
                    "artifact build context is inconsistent."
                ),
            )
        if not self._semantic_build_identity_matches(
            build,
            SemanticRetrievalBuildContext(
                build_id=persisted_build.build_id,
                provider_id=persisted_build.provider_id,
                model_id=persisted_build.model_id,
                model_version=persisted_build.model_version,
                vector_engine=persisted_build.vector_engine,
                semantic_config_fingerprint=persisted_build.semantic_config_fingerprint,
                build_duration_ms=persisted_build.build_duration_ms,
            ),
        ):
            raise BenchmarkArtifactCorruptError(
                (
                    "Benchmark metrics cannot be calculated because the raw benchmark "
                    "artifact build context is inconsistent."
                ),
            )
        if (
            persisted_build.repository_id != repository_id
            or persisted_build.snapshot_id != snapshot_id
            or (
                build.build_duration_ms is not None
                and build.build_duration_ms != persisted_build.build_duration_ms
            )
        ):
            raise BenchmarkArtifactCorruptError(
                (
                    "Benchmark metrics cannot be calculated because the raw benchmark "
                    "artifact build context is inconsistent."
                ),
            )

    @staticmethod
    def _lexical_build_identity_matches(
        left: LexicalRetrievalBuildContext,
        right: LexicalRetrievalBuildContext,
    ) -> bool:
        return (
            left.build_id == right.build_id
            and left.indexing_config_fingerprint == right.indexing_config_fingerprint
            and left.lexical_engine == right.lexical_engine
            and left.tokenizer_spec == right.tokenizer_spec
            and left.indexed_fields == right.indexed_fields
        )

    @staticmethod
    def _semantic_build_identity_matches(
        left: SemanticRetrievalBuildContext,
        right: SemanticRetrievalBuildContext,
    ) -> bool:
        return (
            left.build_id == right.build_id
            and left.provider_id == right.provider_id
            and left.model_id == right.model_id
            and left.model_version == right.model_version
            and left.vector_engine == right.vector_engine
            and left.semantic_config_fingerprint == right.semantic_config_fingerprint
        )

    def _calculate_case_metrics(
        self,
        artifact: BenchmarkRunArtifactDocument,
    ) -> list[BenchmarkCaseMetricResult]:
        try:
            return [
                calculate_benchmark_case_metrics(case, k=artifact.max_results)
                for case in artifact.cases
            ]
        except DomainBenchmarkMetricsInputShapeError as exc:
            raise BenchmarkMetricsInputShapeError(str(exc)) from exc

    def _summarize_indexing_durations(
        self,
        artifact: BenchmarkRunArtifactDocument,
    ) -> BenchmarkIndexingDurationSummary:
        build = artifact.build
        if isinstance(build, LexicalRetrievalBuildContext):
            return BenchmarkIndexingDurationSummary(
                lexical_build_duration_ms=self._resolve_lexical_build_duration(build),
            )
        if isinstance(build, SemanticRetrievalBuildContext):
            return BenchmarkIndexingDurationSummary(
                semantic_build_duration_ms=self._resolve_semantic_build_duration(build),
            )

        lexical_duration_ms = self._resolve_lexical_build_duration(build.lexical_build)
        semantic_duration_ms = self._resolve_semantic_build_duration(build.semantic_build)
        derived_total_duration_ms = None
        if lexical_duration_ms is not None and semantic_duration_ms is not None:
            derived_total_duration_ms = lexical_duration_ms + semantic_duration_ms
        return BenchmarkIndexingDurationSummary(
            lexical_build_duration_ms=lexical_duration_ms,
            semantic_build_duration_ms=semantic_duration_ms,
            derived_total_build_duration_ms=derived_total_duration_ms,
        )

    def _resolve_lexical_build_duration(
        self,
        build: LexicalRetrievalBuildContext,
    ) -> int | None:
        if build.build_duration_ms is not None:
            return build.build_duration_ms
        persisted_build = self.index_build_store.get_by_build_id(build.build_id)
        if persisted_build is None:
            return None
        return persisted_build.build_duration_ms

    def _resolve_semantic_build_duration(
        self,
        build: SemanticRetrievalBuildContext,
    ) -> int | None:
        if build.build_duration_ms is not None:
            return build.build_duration_ms
        persisted_build = self.semantic_index_build_store.get_by_build_id(build.build_id)
        if persisted_build is None:
            return None
        return persisted_build.build_duration_ms


def _build_hybrid_context_id(
    *,
    lexical_build_id: str,
    semantic_build_id: str,
) -> str:
    digest = sha1(
        f"{lexical_build_id}:{semantic_build_id}".encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()
    return f"hybrid-{digest[:12]}"

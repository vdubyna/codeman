"""Compare persisted benchmark runs without rerunning retrieval or metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import ValidationError

from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.application.ports.benchmark_run_store_port import BenchmarkRunStorePort
from codeman.application.provenance.show_run_provenance import (
    ShowRunConfigurationProvenanceUseCase,
)
from codeman.config.loader import ConfigurationResolutionError
from codeman.contracts.configuration import (
    RunConfigurationProvenanceRecord,
    ShowRunConfigurationProvenanceRequest,
)
from codeman.contracts.errors import ErrorCode
from codeman.contracts.evaluation import (
    BenchmarkMetricComparison,
    BenchmarkMetricComparisonValue,
    BenchmarkMetricsArtifactDocument,
    BenchmarkRunArtifactDocument,
    BenchmarkRunComparability,
    BenchmarkRunComparabilityDifference,
    BenchmarkRunComparisonEntry,
    BenchmarkRunRecord,
    BenchmarkRunStatus,
    CompareBenchmarkRunsRequest,
    CompareBenchmarkRunsResult,
    build_benchmark_dataset_fingerprint,
)
from codeman.contracts.retrieval import LexicalRetrievalBuildContext, SemanticRetrievalBuildContext
from codeman.runtime import RuntimePaths, provision_runtime_paths

ProgressReporter = Callable[[str], None]
MetricValue = float | int | None

__all__ = [
    "CompareBenchmarkRunsArtifactCorruptError",
    "CompareBenchmarkRunsCrossRepositoryError",
    "CompareBenchmarkRunsError",
    "CompareBenchmarkRunsMetricsArtifactMissingError",
    "CompareBenchmarkRunsRawArtifactMissingError",
    "CompareBenchmarkRunsRunIncompleteError",
    "CompareBenchmarkRunsRunNotFoundError",
    "CompareBenchmarkRunsUseCase",
    "CompareBenchmarkRunsProvenanceUnavailableError",
]


class CompareBenchmarkRunsError(Exception):
    """Base exception for benchmark-run comparison failures."""

    exit_code = 81
    error_code = ErrorCode.COMPARE_BENCHMARK_RUNS_FAILED

    def __init__(self, message: str, *, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class CompareBenchmarkRunsRunNotFoundError(CompareBenchmarkRunsError):
    """Raised when at least one requested benchmark run is unknown."""

    exit_code = 82
    error_code = ErrorCode.COMPARE_BENCHMARK_RUN_NOT_FOUND


class CompareBenchmarkRunsRawArtifactMissingError(CompareBenchmarkRunsError):
    """Raised when one compared run lacks run.json."""

    exit_code = 83
    error_code = ErrorCode.COMPARE_BENCHMARK_RUN_ARTIFACT_MISSING


class CompareBenchmarkRunsMetricsArtifactMissingError(CompareBenchmarkRunsError):
    """Raised when one compared run lacks metrics.json."""

    exit_code = 84
    error_code = ErrorCode.COMPARE_BENCHMARK_RUN_METRICS_ARTIFACT_MISSING


class CompareBenchmarkRunsRunIncompleteError(CompareBenchmarkRunsError):
    """Raised when one compared run is not truthfully complete."""

    exit_code = 85
    error_code = ErrorCode.COMPARE_BENCHMARK_RUN_INCOMPLETE


class CompareBenchmarkRunsArtifactCorruptError(CompareBenchmarkRunsError):
    """Raised when persisted benchmark evidence is corrupt or mismatched."""

    exit_code = 86
    error_code = ErrorCode.COMPARE_BENCHMARK_RUN_ARTIFACT_CORRUPT


class CompareBenchmarkRunsProvenanceUnavailableError(CompareBenchmarkRunsError):
    """Raised when run provenance is missing or inconsistent."""

    exit_code = 87
    error_code = ErrorCode.COMPARE_BENCHMARK_RUN_PROVENANCE_UNAVAILABLE


class CompareBenchmarkRunsCrossRepositoryError(CompareBenchmarkRunsError):
    """Raised when compared runs belong to different repositories."""

    exit_code = 88
    error_code = ErrorCode.COMPARE_BENCHMARK_RUN_REPOSITORY_MISMATCH


@dataclass(slots=True, frozen=True)
class LoadedBenchmarkComparisonRun:
    """One fully loaded benchmark run and its persisted evidence."""

    run: BenchmarkRunRecord
    artifact: BenchmarkRunArtifactDocument
    metrics_artifact: BenchmarkMetricsArtifactDocument
    provenance: RunConfigurationProvenanceRecord

    def to_entry(self) -> BenchmarkRunComparisonEntry:
        """Convert the loaded package into the public comparison entry DTO."""

        return BenchmarkRunComparisonEntry(
            run=self.run,
            repository=self.artifact.repository,
            snapshot=self.artifact.snapshot,
            build=self.artifact.build,
            dataset=self.artifact.dataset_summary,
            metrics=self.metrics_artifact.summary,
            provenance=self.provenance,
        )


@dataclass(slots=True)
class CompareBenchmarkRunsUseCase:
    """Compare two or more benchmark runs from persisted evidence only."""

    runtime_paths: RuntimePaths
    benchmark_run_store: BenchmarkRunStorePort
    artifact_store: ArtifactStorePort
    show_run_provenance: ShowRunConfigurationProvenanceUseCase

    def execute(
        self,
        request: CompareBenchmarkRunsRequest,
        *,
        progress: ProgressReporter | None = None,
    ) -> CompareBenchmarkRunsResult:
        """Load, validate, and compare benchmark runs in the requested order."""

        provision_runtime_paths(self.runtime_paths)
        self.benchmark_run_store.initialize()

        requested_runs = [
            self._load_requested_run(run_id, progress=progress) for run_id in request.run_ids
        ]
        self._validate_same_repository(requested_runs)
        loaded_runs = [self._load_comparison_run(run) for run in requested_runs]

        entries = [loaded_run.to_entry() for loaded_run in loaded_runs]
        return CompareBenchmarkRunsResult(
            repository=entries[0].repository,
            entries=entries,
            metric_comparisons=self._build_metric_comparisons(entries),
            comparability=self._build_comparability(entries),
        )

    def _load_requested_run(
        self,
        run_id: str,
        *,
        progress: ProgressReporter | None,
    ) -> BenchmarkRunRecord:
        self._report(progress, f"Loading benchmark comparison evidence for run: {run_id}")
        run = self.benchmark_run_store.get_by_run_id(run_id)
        if run is None:
            raise CompareBenchmarkRunsRunNotFoundError(
                f"Benchmark comparison cannot continue because the run is unknown: {run_id}",
                details={"run_id": run_id},
            )
        return run

    def _load_comparison_run(
        self,
        run: BenchmarkRunRecord,
    ) -> LoadedBenchmarkComparisonRun:

        self._validate_run_state(run)
        artifact = self._load_run_artifact(run)
        metrics_artifact = self._load_metrics_artifact(run)
        provenance = self._load_provenance(run.run_id)

        self._validate_run_artifact_identity(artifact, run)
        self._validate_metrics_artifact_identity(metrics_artifact, run, artifact)
        self._validate_provenance_identity(provenance, run, artifact)

        return LoadedBenchmarkComparisonRun(
            run=run,
            artifact=artifact,
            metrics_artifact=metrics_artifact,
            provenance=provenance,
        )

    def _validate_run_state(self, run: BenchmarkRunRecord) -> None:
        if run.status != BenchmarkRunStatus.SUCCEEDED or run.completed_case_count != run.case_count:
            raise CompareBenchmarkRunsRunIncompleteError(
                "Benchmark comparison requires completed successful benchmark runs.",
                details={
                    "run_id": run.run_id,
                    "status": run.status,
                    "completed_case_count": run.completed_case_count,
                    "case_count": run.case_count,
                },
            )
        if run.artifact_path is None:
            raise CompareBenchmarkRunsRawArtifactMissingError(
                "Benchmark comparison requires the persisted raw benchmark artifact.",
                details={"run_id": run.run_id},
            )
        if run.metrics_artifact_path is None:
            raise CompareBenchmarkRunsMetricsArtifactMissingError(
                "Benchmark comparison requires the persisted benchmark metrics artifact.",
                details={"run_id": run.run_id},
            )

    def _load_run_artifact(self, run: BenchmarkRunRecord) -> BenchmarkRunArtifactDocument:
        assert run.artifact_path is not None
        try:
            return self.artifact_store.read_benchmark_run_artifact(run.artifact_path)
        except (FileNotFoundError, OSError) as exc:
            raise CompareBenchmarkRunsRawArtifactMissingError(
                "Benchmark comparison requires the persisted raw benchmark artifact.",
                details={"run_id": run.run_id, "artifact_path": str(run.artifact_path)},
            ) from exc
        except ValidationError as exc:
            raise CompareBenchmarkRunsArtifactCorruptError(
                "Benchmark comparison cannot continue because run.json is corrupt.",
                details={"run_id": run.run_id, "artifact_path": str(run.artifact_path)},
            ) from exc

    def _load_metrics_artifact(
        self,
        run: BenchmarkRunRecord,
    ) -> BenchmarkMetricsArtifactDocument:
        assert run.metrics_artifact_path is not None
        try:
            return self.artifact_store.read_benchmark_metrics_artifact(run.metrics_artifact_path)
        except (FileNotFoundError, OSError) as exc:
            raise CompareBenchmarkRunsMetricsArtifactMissingError(
                "Benchmark comparison requires the persisted benchmark metrics artifact.",
                details={
                    "run_id": run.run_id,
                    "artifact_path": str(run.metrics_artifact_path),
                },
            ) from exc
        except ValidationError as exc:
            raise CompareBenchmarkRunsArtifactCorruptError(
                "Benchmark comparison cannot continue because metrics.json is corrupt.",
                details={
                    "run_id": run.run_id,
                    "artifact_path": str(run.metrics_artifact_path),
                },
            ) from exc

    def _load_provenance(self, run_id: str) -> RunConfigurationProvenanceRecord:
        try:
            return self.show_run_provenance.execute(
                ShowRunConfigurationProvenanceRequest(run_id=run_id)
            ).provenance
        except Exception as exc:
            details = {"run_id": run_id}
            if isinstance(exc, ConfigurationResolutionError) and exc.details is not None:
                details = exc.details
            raise CompareBenchmarkRunsProvenanceUnavailableError(
                "Benchmark comparison cannot continue because run provenance is unavailable.",
                details=details,
            ) from exc

    def _validate_run_artifact_identity(
        self,
        artifact: BenchmarkRunArtifactDocument,
        run: BenchmarkRunRecord,
    ) -> None:
        if artifact.failure is not None or artifact.run.status != BenchmarkRunStatus.SUCCEEDED:
            raise CompareBenchmarkRunsRunIncompleteError(
                "Benchmark comparison requires successful benchmark artifacts.",
                details={"run_id": run.run_id},
            )
        if len(artifact.cases) != run.case_count:
            raise CompareBenchmarkRunsRunIncompleteError(
                "Benchmark comparison requires complete benchmark artifacts.",
                details={"run_id": run.run_id, "case_count": len(artifact.cases)},
            )

        artifact_dataset_fingerprint = build_benchmark_dataset_fingerprint(artifact.dataset)
        mismatches: list[str] = []
        expected_values: tuple[tuple[str, object, object], ...] = (
            ("run.run_id", artifact.run.run_id, run.run_id),
            ("run.repository_id", artifact.run.repository_id, run.repository_id),
            ("run.snapshot_id", artifact.run.snapshot_id, run.snapshot_id),
            ("run.retrieval_mode", artifact.run.retrieval_mode, run.retrieval_mode),
            ("run.dataset_id", artifact.run.dataset_id, run.dataset_id),
            ("run.dataset_version", artifact.run.dataset_version, run.dataset_version),
            ("run.dataset_fingerprint", artifact.run.dataset_fingerprint, run.dataset_fingerprint),
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
            ("dataset_summary.dataset_id", artifact.dataset_summary.dataset_id, run.dataset_id),
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
            ("dataset_summary.case_count", artifact.dataset_summary.case_count, run.case_count),
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

        for index, (artifact_case, dataset_case) in enumerate(
            zip(artifact.cases, artifact.dataset.cases, strict=False)
        ):
            if artifact_case.source_kind != dataset_case.source_kind:
                mismatches.append(f"cases[{index}].source_kind")
            if artifact_case.judgments != dataset_case.judgments:
                mismatches.append(f"cases[{index}].judgments")

        if mismatches:
            raise CompareBenchmarkRunsArtifactCorruptError(
                "Benchmark comparison cannot continue because run.json is inconsistent.",
                details={"run_id": run.run_id, "fields": mismatches},
            )

    def _validate_metrics_artifact_identity(
        self,
        metrics_artifact: BenchmarkMetricsArtifactDocument,
        run: BenchmarkRunRecord,
        artifact: BenchmarkRunArtifactDocument,
    ) -> None:
        if metrics_artifact.run.status != BenchmarkRunStatus.SUCCEEDED:
            raise CompareBenchmarkRunsRunIncompleteError(
                "Benchmark comparison requires benchmark metrics from successful runs.",
                details={"run_id": run.run_id},
            )
        if len(metrics_artifact.cases) != run.case_count:
            raise CompareBenchmarkRunsRunIncompleteError(
                "Benchmark comparison requires complete benchmark metrics evidence.",
                details={"run_id": run.run_id, "case_count": len(metrics_artifact.cases)},
            )

        mismatches: list[str] = []
        expected_values: tuple[tuple[str, object, object], ...] = (
            ("run.run_id", metrics_artifact.run.run_id, run.run_id),
            ("run.repository_id", metrics_artifact.run.repository_id, run.repository_id),
            ("run.snapshot_id", metrics_artifact.run.snapshot_id, run.snapshot_id),
            ("run.retrieval_mode", metrics_artifact.run.retrieval_mode, run.retrieval_mode),
            ("run.dataset_id", metrics_artifact.run.dataset_id, run.dataset_id),
            ("run.dataset_version", metrics_artifact.run.dataset_version, run.dataset_version),
            (
                "run.dataset_fingerprint",
                metrics_artifact.run.dataset_fingerprint,
                run.dataset_fingerprint,
            ),
            ("run.case_count", metrics_artifact.run.case_count, run.case_count),
            (
                "run.completed_case_count",
                metrics_artifact.run.completed_case_count,
                run.completed_case_count,
            ),
            ("dataset.dataset_id", metrics_artifact.dataset.dataset_id, run.dataset_id),
            (
                "dataset.dataset_version",
                metrics_artifact.dataset.dataset_version,
                run.dataset_version,
            ),
            (
                "dataset.dataset_fingerprint",
                metrics_artifact.dataset.dataset_fingerprint,
                run.dataset_fingerprint,
            ),
            ("dataset.case_count", metrics_artifact.dataset.case_count, run.case_count),
            ("repository", metrics_artifact.repository, artifact.repository),
            ("snapshot", metrics_artifact.snapshot, artifact.snapshot),
            ("build", metrics_artifact.build, artifact.build),
            (
                "summary.evaluated_at_k",
                metrics_artifact.summary.evaluated_at_k,
                artifact.max_results,
            ),
        )
        for field_name, actual, expected in expected_values:
            if actual != expected:
                mismatches.append(field_name)

        if (
            run.artifact_path is not None
            and metrics_artifact.run.artifact_path != run.artifact_path
        ):
            mismatches.append("run.artifact_path")
        if (
            run.metrics_artifact_path is not None
            and metrics_artifact.run.metrics_artifact_path != run.metrics_artifact_path
        ):
            mismatches.append("run.metrics_artifact_path")
        if (
            run.metrics_artifact_path is not None
            and metrics_artifact.summary.artifact_path != run.metrics_artifact_path
        ):
            mismatches.append("summary.artifact_path")

        summary_metrics = metrics_artifact.summary.metrics
        summary_query_latency = metrics_artifact.summary.performance.query_latency
        summary_indexing = metrics_artifact.summary.performance.indexing
        summary_consistency_values: tuple[tuple[str, object, object], ...] = (
            (
                "artifact_run.evaluated_at_k",
                metrics_artifact.run.evaluated_at_k,
                run.evaluated_at_k,
            ),
            ("artifact_run.recall_at_k", metrics_artifact.run.recall_at_k, run.recall_at_k),
            ("artifact_run.mrr", metrics_artifact.run.mrr, run.mrr),
            ("artifact_run.ndcg_at_k", metrics_artifact.run.ndcg_at_k, run.ndcg_at_k),
            (
                "artifact_run.query_latency_mean_ms",
                metrics_artifact.run.query_latency_mean_ms,
                run.query_latency_mean_ms,
            ),
            (
                "artifact_run.query_latency_p95_ms",
                metrics_artifact.run.query_latency_p95_ms,
                run.query_latency_p95_ms,
            ),
            (
                "artifact_run.lexical_index_duration_ms",
                metrics_artifact.run.lexical_index_duration_ms,
                run.lexical_index_duration_ms,
            ),
            (
                "artifact_run.semantic_index_duration_ms",
                metrics_artifact.run.semantic_index_duration_ms,
                run.semantic_index_duration_ms,
            ),
            (
                "artifact_run.derived_index_duration_ms",
                metrics_artifact.run.derived_index_duration_ms,
                run.derived_index_duration_ms,
            ),
            (
                "artifact_run.metrics_computed_at",
                metrics_artifact.run.metrics_computed_at,
                run.metrics_computed_at,
            ),
            ("summary.evaluated_at_k", metrics_artifact.summary.evaluated_at_k, run.evaluated_at_k),
            ("summary.metrics.recall_at_k", summary_metrics.recall_at_k, run.recall_at_k),
            ("summary.metrics.mrr", summary_metrics.mrr, run.mrr),
            ("summary.metrics.ndcg_at_k", summary_metrics.ndcg_at_k, run.ndcg_at_k),
            (
                "summary.performance.query_latency.mean_ms",
                summary_query_latency.mean_ms,
                run.query_latency_mean_ms,
            ),
            (
                "summary.performance.query_latency.p95_ms",
                summary_query_latency.p95_ms,
                run.query_latency_p95_ms,
            ),
            (
                "summary.performance.indexing.lexical_build_duration_ms",
                summary_indexing.lexical_build_duration_ms,
                run.lexical_index_duration_ms,
            ),
            (
                "summary.performance.indexing.semantic_build_duration_ms",
                summary_indexing.semantic_build_duration_ms,
                run.semantic_index_duration_ms,
            ),
            (
                "summary.performance.indexing.derived_total_build_duration_ms",
                summary_indexing.derived_total_build_duration_ms,
                run.derived_index_duration_ms,
            ),
            (
                "summary.metrics_computed_at",
                metrics_artifact.summary.metrics_computed_at,
                run.metrics_computed_at,
            ),
        )
        for field_name, actual, expected in summary_consistency_values:
            if actual != expected:
                mismatches.append(field_name)

        expected_query_ids = [case.query_id for case in artifact.dataset.cases]
        case_query_ids = [case.query_id for case in metrics_artifact.cases]
        if case_query_ids != expected_query_ids:
            mismatches.append("cases.query_id_order")

        expected_source_kinds = [case.source_kind for case in artifact.dataset.cases]
        case_source_kinds = [case.source_kind for case in metrics_artifact.cases]
        if case_source_kinds != expected_source_kinds:
            mismatches.append("cases.source_kind_order")

        if mismatches:
            raise CompareBenchmarkRunsArtifactCorruptError(
                "Benchmark comparison cannot continue because metrics.json is inconsistent.",
                details={"run_id": run.run_id, "fields": mismatches},
            )

    def _validate_provenance_identity(
        self,
        provenance: RunConfigurationProvenanceRecord,
        run: BenchmarkRunRecord,
        artifact: BenchmarkRunArtifactDocument,
    ) -> None:
        workflow_context = provenance.workflow_context
        mismatches: list[str] = []
        expected_values: tuple[tuple[str, object, object], ...] = (
            ("run_id", provenance.run_id, run.run_id),
            ("workflow_type", provenance.workflow_type, "eval.benchmark"),
            ("repository_id", provenance.repository_id, run.repository_id),
            ("snapshot_id", provenance.snapshot_id, run.snapshot_id),
            ("dataset_id", workflow_context.benchmark_dataset_id, run.dataset_id),
            (
                "dataset_version",
                workflow_context.benchmark_dataset_version,
                run.dataset_version,
            ),
            (
                "dataset_fingerprint",
                workflow_context.benchmark_dataset_fingerprint,
                run.dataset_fingerprint,
            ),
            ("retrieval_mode", workflow_context.retrieval_mode, run.retrieval_mode),
            ("benchmark_case_count", workflow_context.benchmark_case_count, run.case_count),
            ("max_results", workflow_context.max_results, artifact.max_results),
        )
        for field_name, actual, expected in expected_values:
            if actual != expected:
                mismatches.append(field_name)

        build = artifact.build
        if isinstance(build, LexicalRetrievalBuildContext):
            if workflow_context.lexical_build_id != build.build_id:
                mismatches.append("workflow_context.lexical_build_id")
            if provenance.indexing_config_fingerprint != build.indexing_config_fingerprint:
                mismatches.append("indexing_config_fingerprint")
        elif isinstance(build, SemanticRetrievalBuildContext):
            if workflow_context.semantic_build_id != build.build_id:
                mismatches.append("workflow_context.semantic_build_id")
            if provenance.semantic_config_fingerprint != build.semantic_config_fingerprint:
                mismatches.append("semantic_config_fingerprint")
            if provenance.provider_id != build.provider_id:
                mismatches.append("provider_id")
            if provenance.model_id != build.model_id:
                mismatches.append("model_id")
            if provenance.model_version != build.model_version:
                mismatches.append("model_version")
        else:
            if workflow_context.lexical_build_id != build.lexical_build.build_id:
                mismatches.append("workflow_context.lexical_build_id")
            if workflow_context.semantic_build_id != build.semantic_build.build_id:
                mismatches.append("workflow_context.semantic_build_id")
            if workflow_context.rank_constant != build.rank_constant:
                mismatches.append("workflow_context.rank_constant")
            if workflow_context.rank_window_size != build.rank_window_size:
                mismatches.append("workflow_context.rank_window_size")
            if (
                provenance.indexing_config_fingerprint
                != build.lexical_build.indexing_config_fingerprint
            ):
                mismatches.append("indexing_config_fingerprint")
            if (
                provenance.semantic_config_fingerprint
                != build.semantic_build.semantic_config_fingerprint
            ):
                mismatches.append("semantic_config_fingerprint")
            if provenance.provider_id != build.semantic_build.provider_id:
                mismatches.append("provider_id")
            if provenance.model_id != build.semantic_build.model_id:
                mismatches.append("model_id")
            if provenance.model_version != build.semantic_build.model_version:
                mismatches.append("model_version")

        if mismatches:
            raise CompareBenchmarkRunsProvenanceUnavailableError(
                "Benchmark comparison cannot continue because run provenance is inconsistent.",
                details={"run_id": run.run_id, "fields": mismatches},
            )

    def _validate_same_repository(self, runs: list[BenchmarkRunRecord]) -> None:
        repository_values = {run.run_id: run.repository_id for run in runs}
        if len(set(repository_values.values())) == 1:
            return
        raise CompareBenchmarkRunsCrossRepositoryError(
            "Benchmark comparison cannot compare runs from different repositories.",
            details={"repositories_by_run_id": repository_values},
        )

    def _build_comparability(
        self,
        entries: list[BenchmarkRunComparisonEntry],
    ) -> BenchmarkRunComparability:
        differences: list[BenchmarkRunComparabilityDifference] = []
        difference_specs = (
            (
                "snapshot_id",
                "Snapshot ID",
                "Compared runs resolved different repository snapshots.",
                lambda entry: entry.snapshot.snapshot_id,
            ),
            (
                "dataset_id",
                "Dataset ID",
                "Compared runs used different benchmark dataset ids.",
                lambda entry: entry.dataset.dataset_id,
            ),
            (
                "dataset_version",
                "Dataset Version",
                "Compared runs used different benchmark dataset versions.",
                lambda entry: entry.dataset.dataset_version,
            ),
            (
                "dataset_fingerprint",
                "Dataset Fingerprint",
                "Compared runs used different benchmark dataset fingerprints.",
                lambda entry: entry.dataset.dataset_fingerprint,
            ),
            (
                "evaluated_at_k",
                "Evaluated At K",
                "Compared runs evaluated different ranking cutoffs (k).",
                lambda entry: entry.metrics.evaluated_at_k,
            ),
            (
                "case_count",
                "Case Count",
                "Compared runs cover different benchmark case counts.",
                lambda entry: entry.run.case_count,
            ),
            (
                "configuration_id",
                "Configuration ID",
                "Compared runs resolved different effective configuration ids.",
                lambda entry: entry.provenance.configuration_id,
            ),
            (
                "indexing_config_fingerprint",
                "Indexing Config Fingerprint",
                "Compared runs resolved different indexing configuration fingerprints.",
                lambda entry: entry.provenance.indexing_config_fingerprint,
            ),
            (
                "semantic_config_fingerprint",
                "Semantic Config Fingerprint",
                "Compared runs resolved different semantic configuration fingerprints.",
                lambda entry: entry.provenance.semantic_config_fingerprint,
            ),
            (
                "provider_id",
                "Provider",
                "Compared runs executed with different semantic providers.",
                lambda entry: entry.provenance.provider_id,
            ),
            (
                "model_id",
                "Model",
                "Compared runs executed with different semantic models.",
                lambda entry: entry.provenance.model_id,
            ),
            (
                "model_version",
                "Model Version",
                "Compared runs executed with different semantic model versions.",
                lambda entry: entry.provenance.model_version,
            ),
        )

        for key, label, note, extractor in difference_specs:
            values_by_run_id = {
                entry.run.run_id: extractor(entry) for entry in entries
            }
            if len(set(values_by_run_id.values())) <= 1:
                continue
            differences.append(
                BenchmarkRunComparabilityDifference(
                    key=key,
                    label=label,
                    note=note,
                    values_by_run_id=values_by_run_id,
                )
            )

        context_difference_keys = {
            "snapshot_id",
            "dataset_id",
            "dataset_version",
            "dataset_fingerprint",
            "evaluated_at_k",
            "case_count",
        }
        is_apples_to_apples = not any(
            difference.key in context_difference_keys for difference in differences
        )
        notes = [
            (
                "Benchmark context is apples-to-apples across snapshot, dataset identity, "
                "evaluated cutoff, and case count."
            )
            if is_apples_to_apples
            else (
                "Benchmark context differs across compared runs; metric winners are "
                "informative but not apples-to-apples."
            )
        ]
        notes.extend(difference.note for difference in differences)

        return BenchmarkRunComparability(
            is_apples_to_apples=is_apples_to_apples,
            differences=differences,
            notes=notes,
        )

    def _build_metric_comparisons(
        self,
        entries: list[BenchmarkRunComparisonEntry],
    ) -> list[BenchmarkMetricComparison]:
        metric_specs = (
            (
                "recall_at_k",
                "Recall@K",
                "higher_is_better",
                lambda entry: entry.metrics.metrics.recall_at_k,
            ),
            ("mrr", "MRR", "higher_is_better", lambda entry: entry.metrics.metrics.mrr),
            (
                "ndcg_at_k",
                "NDCG@K",
                "higher_is_better",
                lambda entry: entry.metrics.metrics.ndcg_at_k,
            ),
            (
                "query_latency_mean_ms",
                "Query Latency Mean (ms)",
                "lower_is_better",
                lambda entry: entry.metrics.performance.query_latency.mean_ms,
            ),
            (
                "query_latency_p95_ms",
                "Query Latency P95 (ms)",
                "lower_is_better",
                lambda entry: entry.metrics.performance.query_latency.p95_ms,
            ),
            (
                "lexical_index_duration_ms",
                "Lexical Build Duration (ms)",
                "lower_is_better",
                lambda entry: entry.metrics.performance.indexing.lexical_build_duration_ms,
            ),
            (
                "semantic_index_duration_ms",
                "Semantic Build Duration (ms)",
                "lower_is_better",
                lambda entry: entry.metrics.performance.indexing.semantic_build_duration_ms,
            ),
            (
                "derived_index_duration_ms",
                "Derived Total Build Duration (ms)",
                "lower_is_better",
                lambda entry: entry.metrics.performance.indexing.derived_total_build_duration_ms,
            ),
        )

        return [
            self._build_metric_comparison(
                entries=entries,
                metric_key=metric_key,
                label=label,
                direction=direction,
                extractor=extractor,
            )
            for metric_key, label, direction, extractor in metric_specs
        ]

    def _build_metric_comparison(
        self,
        *,
        entries: list[BenchmarkRunComparisonEntry],
        metric_key: str,
        label: str,
        direction: str,
        extractor: Callable[[BenchmarkRunComparisonEntry], MetricValue],
    ) -> BenchmarkMetricComparison:
        values = [
            BenchmarkMetricComparisonValue(
                run_id=entry.run.run_id,
                retrieval_mode=entry.run.retrieval_mode,
                value=extractor(entry),
            )
            for entry in entries
        ]
        available_values = [value for value in values if value.value is not None]
        unavailable_run_ids = [value.run_id for value in values if value.value is None]

        if not available_values:
            return BenchmarkMetricComparison(
                metric_key=metric_key,
                label=label,
                direction=direction,
                outcome="unavailable",
                unavailable_run_ids=unavailable_run_ids,
                values=values,
            )

        comparator = max if direction == "higher_is_better" else min
        best_value = comparator(value.value for value in available_values)
        winner_run_ids = [
            value.run_id for value in available_values if value.value == best_value
        ]
        outcome = "tie" if len(winner_run_ids) > 1 else "winner"
        return BenchmarkMetricComparison(
            metric_key=metric_key,
            label=label,
            direction=direction,
            outcome=outcome,
            best_value=best_value,
            winner_run_ids=winner_run_ids,
            unavailable_run_ids=unavailable_run_ids,
            values=values,
        )

    @staticmethod
    def _report(progress: ProgressReporter | None, message: str) -> None:
        if progress is not None:
            progress(message)

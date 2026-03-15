"""Generate a deterministic benchmark report from persisted evidence only."""

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
    ShowRunConfigurationProvenanceRequest,
)
from codeman.contracts.errors import ErrorCode
from codeman.contracts.evaluation import (
    BenchmarkMetricsArtifactDocument,
    BenchmarkMetricsSummary,
    BenchmarkRunArtifactDocument,
    BenchmarkRunRecord,
    BenchmarkRunStatus,
    GenerateBenchmarkReportRequest,
    GenerateBenchmarkReportResult,
    build_benchmark_dataset_fingerprint,
)
from codeman.contracts.retrieval import (
    LexicalRetrievalBuildContext,
    RetrievalBuildContext,
    SemanticRetrievalBuildContext,
)
from codeman.runtime import RuntimePaths, provision_runtime_paths

ProgressReporter = Callable[[str], None]

__all__ = [
    "BenchmarkReportArtifactCorruptError",
    "BenchmarkReportError",
    "BenchmarkReportMetricsArtifactMissingError",
    "BenchmarkReportProvenanceUnavailableError",
    "BenchmarkReportRawArtifactMissingError",
    "BenchmarkReportRunIncompleteError",
    "BenchmarkReportRunNotFoundError",
    "GenerateBenchmarkReportUseCase",
]


class BenchmarkReportError(Exception):
    """Base exception for benchmark report generation failures."""

    exit_code = 74
    error_code = ErrorCode.BENCHMARK_REPORT_FAILED

    def __init__(self, message: str, *, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class BenchmarkReportRunNotFoundError(BenchmarkReportError):
    """Raised when a benchmark report is requested for an unknown run."""

    exit_code = 75
    error_code = ErrorCode.BENCHMARK_REPORT_RUN_NOT_FOUND


class BenchmarkReportRawArtifactMissingError(BenchmarkReportError):
    """Raised when the persisted raw benchmark artifact is unavailable."""

    exit_code = 76
    error_code = ErrorCode.BENCHMARK_REPORT_RAW_ARTIFACT_MISSING


class BenchmarkReportMetricsArtifactMissingError(BenchmarkReportError):
    """Raised when the persisted metrics artifact is unavailable."""

    exit_code = 77
    error_code = ErrorCode.BENCHMARK_REPORT_METRICS_ARTIFACT_MISSING


class BenchmarkReportRunIncompleteError(BenchmarkReportError):
    """Raised when the benchmark run is not truthfully complete."""

    exit_code = 78
    error_code = ErrorCode.BENCHMARK_REPORT_INCOMPLETE


class BenchmarkReportProvenanceUnavailableError(BenchmarkReportError):
    """Raised when the persisted run provenance is missing or inconsistent."""

    exit_code = 79
    error_code = ErrorCode.BENCHMARK_REPORT_PROVENANCE_UNAVAILABLE


class BenchmarkReportArtifactCorruptError(BenchmarkReportError):
    """Raised when persisted benchmark artifacts are unreadable or mismatched."""

    exit_code = 80
    error_code = ErrorCode.BENCHMARK_REPORT_ARTIFACT_CORRUPT


@dataclass(slots=True)
class GenerateBenchmarkReportUseCase:
    """Render one benchmark report from the persisted benchmark truth surface."""

    runtime_paths: RuntimePaths
    benchmark_run_store: BenchmarkRunStorePort
    artifact_store: ArtifactStorePort
    show_run_provenance: ShowRunConfigurationProvenanceUseCase

    def execute(
        self,
        request: GenerateBenchmarkReportRequest,
        *,
        progress: ProgressReporter | None = None,
    ) -> GenerateBenchmarkReportResult:
        """Generate a deterministic benchmark report for one completed run."""

        provision_runtime_paths(self.runtime_paths)
        self.benchmark_run_store.initialize()
        self._report(progress, f"Loading benchmark evidence for run: {request.run_id}")

        run = self.benchmark_run_store.get_by_run_id(request.run_id)
        if run is None:
            raise BenchmarkReportRunNotFoundError(
                (
                    "Benchmark report cannot be generated because the run is unknown: "
                    f"{request.run_id}"
                ),
                details={"run_id": request.run_id},
            )

        self._validate_run_state(run)
        artifact = self._load_run_artifact(run)
        metrics_artifact = self._load_metrics_artifact(run)
        provenance = self._load_provenance(run.run_id)

        self._validate_run_artifact_identity(artifact, run)
        self._validate_metrics_artifact_identity(metrics_artifact, run, artifact)
        self._validate_provenance_identity(provenance, run, artifact)

        report_markdown = self._render_report(
            run=run,
            artifact=artifact,
            metrics=metrics_artifact.summary,
            metrics_artifact=metrics_artifact,
            provenance=provenance,
        )
        self._report(progress, f"Writing benchmark report artifact for run: {run.run_id}")
        report_artifact_path = self._write_report_artifact(
            report_markdown,
            run_id=run.run_id,
        )

        return GenerateBenchmarkReportResult(
            run=run,
            repository=artifact.repository,
            snapshot=artifact.snapshot,
            build=artifact.build,
            dataset=artifact.dataset_summary,
            metrics=metrics_artifact.summary,
            provenance=provenance,
            report_artifact_path=report_artifact_path,
        )

    def _validate_run_state(self, run: BenchmarkRunRecord) -> None:
        if run.status != BenchmarkRunStatus.SUCCEEDED or run.completed_case_count != run.case_count:
            raise BenchmarkReportRunIncompleteError(
                "Benchmark report generation requires a completed successful benchmark run.",
                details={
                    "run_id": run.run_id,
                    "status": run.status,
                    "completed_case_count": run.completed_case_count,
                    "case_count": run.case_count,
                },
            )
        if run.artifact_path is None:
            raise BenchmarkReportRawArtifactMissingError(
                "Benchmark report generation requires the persisted raw benchmark artifact.",
                details={"run_id": run.run_id},
            )
        if run.metrics_artifact_path is None:
            raise BenchmarkReportMetricsArtifactMissingError(
                "Benchmark report generation requires the persisted benchmark metrics artifact.",
                details={"run_id": run.run_id},
            )

    def _load_run_artifact(self, run: BenchmarkRunRecord) -> BenchmarkRunArtifactDocument:
        assert run.artifact_path is not None
        try:
            return self.artifact_store.read_benchmark_run_artifact(run.artifact_path)
        except (FileNotFoundError, OSError) as exc:
            raise BenchmarkReportRawArtifactMissingError(
                "Benchmark report generation requires the persisted raw benchmark artifact.",
                details={"run_id": run.run_id, "artifact_path": str(run.artifact_path)},
            ) from exc
        except ValidationError as exc:
            raise BenchmarkReportArtifactCorruptError(
                "Benchmark report generation cannot continue because run.json is corrupt.",
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
            raise BenchmarkReportMetricsArtifactMissingError(
                "Benchmark report generation requires the persisted benchmark metrics artifact.",
                details={
                    "run_id": run.run_id,
                    "artifact_path": str(run.metrics_artifact_path),
                },
            ) from exc
        except ValidationError as exc:
            raise BenchmarkReportArtifactCorruptError(
                "Benchmark report generation cannot continue because metrics.json is corrupt.",
                details={
                    "run_id": run.run_id,
                    "artifact_path": str(run.metrics_artifact_path),
                },
            ) from exc

    def _load_provenance(self, run_id: str) -> Any:
        try:
            return self.show_run_provenance.execute(
                ShowRunConfigurationProvenanceRequest(run_id=run_id)
            ).provenance
        except Exception as exc:
            if isinstance(exc, BenchmarkReportError):
                raise
            details = {"run_id": run_id}
            if isinstance(exc, ConfigurationResolutionError) and exc.details is not None:
                details = exc.details
            raise BenchmarkReportProvenanceUnavailableError(
                "Benchmark report cannot be generated because run provenance is unavailable.",
                details=details,
            ) from exc

    def _write_report_artifact(
        self,
        report_markdown: str,
        *,
        run_id: str,
    ):
        try:
            return self.artifact_store.write_benchmark_report(
                report_markdown,
                run_id=run_id,
            )
        except Exception as exc:
            if isinstance(exc, BenchmarkReportError):
                raise
            raise BenchmarkReportError(
                "Benchmark report generation failed while writing the report artifact.",
                details={
                    "run_id": run_id,
                    "artifact_path": str(
                        self.runtime_paths.artifacts / "benchmarks" / run_id / "report.md"
                    ),
                },
            ) from exc

    def _validate_run_artifact_identity(
        self,
        artifact: BenchmarkRunArtifactDocument,
        run: BenchmarkRunRecord,
    ) -> None:
        if artifact.failure is not None or artifact.run.status != BenchmarkRunStatus.SUCCEEDED:
            raise BenchmarkReportRunIncompleteError(
                "Benchmark report generation requires a successful benchmark artifact.",
                details={"run_id": run.run_id},
            )
        if len(artifact.cases) != run.case_count:
            raise BenchmarkReportRunIncompleteError(
                "Benchmark report generation requires a complete benchmark artifact.",
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
            raise BenchmarkReportArtifactCorruptError(
                "Benchmark report generation cannot continue because run.json is inconsistent.",
                details={"run_id": run.run_id, "fields": mismatches},
            )

    def _validate_metrics_artifact_identity(
        self,
        metrics_artifact: BenchmarkMetricsArtifactDocument,
        run: BenchmarkRunRecord,
        artifact: BenchmarkRunArtifactDocument,
    ) -> None:
        if metrics_artifact.run.status != BenchmarkRunStatus.SUCCEEDED:
            raise BenchmarkReportRunIncompleteError(
                "Benchmark report generation requires benchmark metrics from a successful run.",
                details={"run_id": run.run_id},
            )
        if len(metrics_artifact.cases) != run.case_count:
            raise BenchmarkReportRunIncompleteError(
                "Benchmark report generation requires complete benchmark metrics evidence.",
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
            (
                "artifact_run.recall_at_k",
                metrics_artifact.run.recall_at_k,
                run.recall_at_k,
            ),
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
            (
                "summary.evaluated_at_k",
                metrics_artifact.summary.evaluated_at_k,
                run.evaluated_at_k,
            ),
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
            raise BenchmarkReportArtifactCorruptError(
                "Benchmark report generation cannot continue because metrics.json is inconsistent.",
                details={"run_id": run.run_id, "fields": mismatches},
            )

    def _validate_provenance_identity(
        self,
        provenance: Any,
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
            ("dataset_version", workflow_context.benchmark_dataset_version, run.dataset_version),
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
            raise BenchmarkReportProvenanceUnavailableError(
                "Benchmark report cannot be generated because run provenance is unavailable.",
                details={"run_id": run.run_id, "fields": mismatches},
            )

    def _render_report(
        self,
        *,
        run: BenchmarkRunRecord,
        artifact: BenchmarkRunArtifactDocument,
        metrics: BenchmarkMetricsSummary,
        metrics_artifact: BenchmarkMetricsArtifactDocument,
        provenance: Any,
    ) -> str:
        lines = [
            f"# Benchmark Report: {run.run_id}",
            "",
            "## Benchmark Identity",
            f"- Run ID: {run.run_id}",
            f"- Repository ID: {artifact.repository.repository_id}",
            f"- Repository Name: {artifact.repository.repository_name}",
            f"- Snapshot ID: {artifact.snapshot.snapshot_id}",
            f"- Revision Identity: {artifact.snapshot.revision_identity}",
            f"- Revision Source: {artifact.snapshot.revision_source}",
            f"- Retrieval Mode: {run.retrieval_mode}",
            f"- Build ID: {artifact.build.build_id}",
            f"- Dataset ID: {artifact.dataset_summary.dataset_id}",
            f"- Dataset Version: {artifact.dataset_summary.dataset_version}",
            f"- Dataset Fingerprint: {artifact.dataset_summary.dataset_fingerprint}",
            f"- Case Count: {run.case_count}",
            f"- Evaluated At K: {metrics.evaluated_at_k}",
        ]

        lines.extend(self._render_build_section(artifact.build))
        lines.extend(
            [
                "",
                "## Aggregate Metrics",
                "| Metric | Value |",
                "| --- | --- |",
                f"| Recall@K | {self._format_ratio(metrics.metrics.recall_at_k)} |",
                f"| MRR | {self._format_ratio(metrics.metrics.mrr)} |",
                f"| NDCG@K | {self._format_ratio(metrics.metrics.ndcg_at_k)} |",
                (
                    f"| Query Latency Mean (ms) | "
                    f"{self._format_number(metrics.performance.query_latency.mean_ms)} |"
                ),
                (
                    f"| Query Latency P95 (ms) | "
                    f"{self._format_number(metrics.performance.query_latency.p95_ms)} |"
                ),
                (
                    f"| Lexical Build Duration (ms) | "
                    f"{
                        self._format_number(metrics.performance.indexing.lexical_build_duration_ms)
                    } |"
                ),
                (
                    f"| Semantic Build Duration (ms) | "
                    f"{
                        self._format_number(metrics.performance.indexing.semantic_build_duration_ms)
                    } |"
                ),
                (
                    f"| Derived Total Build Duration (ms) | "
                    f"{
                        self._format_number(
                            metrics.performance.indexing.derived_total_build_duration_ms
                        )
                    } |"
                ),
            ]
        )

        provider_config = provenance.effective_config.embedding_providers.get_provider_config(
            provenance.effective_config.semantic_indexing.provider_id
        )
        lines.extend(
            [
                "",
                "## Configuration Provenance",
                f"- Configuration ID: {provenance.configuration_id}",
                f"- Reuse Kind: {provenance.configuration_reuse.reuse_kind}",
                (
                    f"- Base Profile Name: "
                    f"{self._format_optional(provenance.configuration_reuse.base_profile_name)}"
                ),
                (
                    f"- Base Profile ID: "
                    f"{self._format_optional(provenance.configuration_reuse.base_profile_id)}"
                ),
                (
                    f"- Indexing Config Fingerprint: "
                    f"{self._format_optional(provenance.indexing_config_fingerprint)}"
                ),
                (
                    f"- Semantic Config Fingerprint: "
                    f"{self._format_optional(provenance.semantic_config_fingerprint)}"
                ),
                f"- Executed Provider: {self._format_optional(provenance.provider_id)}",
                f"- Executed Model: {self._format_optional(provenance.model_id)}",
                (f"- Executed Model Version: {self._format_optional(provenance.model_version)}"),
                (
                    f"- Effective Semantic Provider: "
                    f"{self._format_optional(provenance.effective_config.semantic_indexing.provider_id)}"
                ),
                (
                    f"- Effective Vector Engine: "
                    f"{provenance.effective_config.semantic_indexing.vector_engine}"
                ),
                (
                    f"- Effective Vector Dimension: "
                    f"{provenance.effective_config.semantic_indexing.vector_dimension}"
                ),
                (
                    f"- Effective Local Model Path: "
                    f"{
                        self._format_optional(
                            provider_config.local_model_path if provider_config else None
                        )
                    }"
                ),
            ]
        )

        lines.extend(
            [
                "",
                "## Per-Case Review Appendix",
                (
                    "| Query ID | Source Kind | Matched/Relevant | First Relevant Rank | "
                    "Recall@K | RR | NDCG@K | Latency (ms) |"
                ),
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for case in metrics_artifact.cases:
            lines.append(
                (
                    f"| {case.query_id} | {case.source_kind} | "
                    f"{case.matched_judgment_count}/{case.relevant_judgment_count} | "
                    f"{self._format_number(case.first_relevant_rank)} | "
                    f"{self._format_ratio(case.recall_at_k)} | "
                    f"{self._format_ratio(case.reciprocal_rank)} | "
                    f"{self._format_ratio(case.ndcg_at_k)} | "
                    f"{case.query_latency_ms} |"
                )
            )

        return "\n".join(lines) + "\n"

    def _render_build_section(self, build: RetrievalBuildContext) -> list[str]:
        if isinstance(build, LexicalRetrievalBuildContext):
            return [
                f"- Lexical Engine: {build.lexical_engine}",
                f"- Tokenizer: {build.tokenizer_spec}",
                f"- Indexed Fields: {', '.join(build.indexed_fields)}",
            ]
        if isinstance(build, SemanticRetrievalBuildContext):
            return [
                f"- Executed Provider: {build.provider_id}",
                f"- Executed Model: {build.model_id}",
                f"- Executed Model Version: {build.model_version}",
                f"- Vector Engine: {build.vector_engine}",
            ]
        return [
            f"- Fusion Strategy: {build.fusion_strategy}",
            f"- Rank Constant: {build.rank_constant}",
            f"- Rank Window Size: {build.rank_window_size}",
            f"- Lexical Build ID: {build.lexical_build.build_id}",
            f"- Semantic Build ID: {build.semantic_build.build_id}",
            f"- Executed Provider: {build.semantic_build.provider_id}",
            f"- Executed Model: {build.semantic_build.model_id}",
            f"- Executed Model Version: {build.semantic_build.model_version}",
        ]

    def _report(self, progress: ProgressReporter | None, line: str) -> None:
        if progress is not None:
            progress(line)

    @staticmethod
    def _format_optional(value: object | None) -> str:
        if value in (None, ""):
            return "-"
        return str(value)

    @staticmethod
    def _format_number(value: float | int | None) -> str:
        if value is None:
            return "-"
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    @staticmethod
    def _format_ratio(value: float) -> str:
        return f"{value:.4f}"

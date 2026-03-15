"""Execute one benchmark dataset against one indexed retrieval mode."""

from __future__ import annotations

import signal
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha1
from types import FrameType
from typing import Any, Callable
from uuid import uuid4

from codeman.application.evaluation.load_benchmark_dataset import (
    LoadBenchmarkDatasetRequest,
    LoadBenchmarkDatasetUseCase,
)
from codeman.application.indexing.build_embeddings import resolve_local_embedding_provider
from codeman.application.indexing.semantic_index_errors import (
    EmbeddingProviderUnavailableError,
)
from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.application.ports.benchmark_run_store_port import BenchmarkRunStorePort
from codeman.application.ports.index_build_store_port import IndexBuildStorePort
from codeman.application.ports.metadata_store_port import RepositoryMetadataStorePort
from codeman.application.ports.semantic_index_build_store_port import (
    SemanticIndexBuildStorePort,
)
from codeman.application.ports.snapshot_port import SnapshotMetadataStorePort
from codeman.application.provenance.record_run_provenance import (
    RecordRunConfigurationProvenanceUseCase,
)
from codeman.application.query.run_hybrid_query import (
    HybridComponentBaselineMissingError,
    HybridComponentUnavailableError,
    HybridQueryError,
    HybridQueryRepositoryNotRegisteredError,
    HybridSnapshotMismatchError,
    RunHybridQueryUseCase,
)
from codeman.application.query.run_lexical_query import (
    LexicalArtifactMissingError,
    LexicalBuildBaselineMissingError,
    LexicalQueryError,
    LexicalQueryRepositoryNotRegisteredError,
    RunLexicalQueryUseCase,
)
from codeman.application.query.run_semantic_query import (
    RunSemanticQueryUseCase,
    SemanticArtifactCorruptError,
    SemanticArtifactMissingError,
    SemanticBuildBaselineMissingError,
    SemanticQueryError,
    SemanticQueryProviderUnavailableError,
    SemanticQueryRepositoryNotRegisteredError,
)
from codeman.config.embedding_providers import EmbeddingProvidersConfig
from codeman.config.indexing import IndexingConfig, build_indexing_fingerprint
from codeman.config.semantic_indexing import (
    SemanticIndexingConfig,
    build_semantic_indexing_fingerprint,
)
from codeman.contracts.configuration import (
    RecordRunConfigurationProvenanceRequest,
    RunProvenanceWorkflowContext,
)
from codeman.contracts.errors import ErrorCode
from codeman.contracts.evaluation import (
    BenchmarkCaseExecutionArtifact,
    BenchmarkCaseRetrievalResult,
    BenchmarkRunArtifactDocument,
    BenchmarkRunFailure,
    BenchmarkRunRecord,
    BenchmarkRunStatus,
    RunBenchmarkRequest,
    RunBenchmarkResult,
)
from codeman.contracts.repository import RepositoryRecord, SnapshotRecord
from codeman.contracts.retrieval import (
    HybridRetrievalBuildContext,
    LexicalIndexBuildRecord,
    LexicalRetrievalBuildContext,
    RetrievalMode,
    RetrievalRepositoryContext,
    RetrievalSnapshotContext,
    RunHybridQueryRequest,
    RunLexicalQueryRequest,
    RunSemanticQueryRequest,
    SemanticIndexBuildRecord,
    SemanticRetrievalBuildContext,
)
from codeman.runtime import RuntimePaths, provision_runtime_paths

ProgressReporter = Callable[[str], None]

__all__ = [
    "BenchmarkRunBaselineMissingError",
    "BenchmarkRunError",
    "BenchmarkRunInterruptedError",
    "BenchmarkRunModeUnavailableError",
    "BenchmarkRunRepositoryNotRegisteredError",
    "RunBenchmarkUseCase",
]


class BenchmarkRunError(Exception):
    """Base exception for benchmark execution failures."""

    exit_code = 65
    error_code = ErrorCode.BENCHMARK_EXECUTION_FAILED

    def __init__(
        self,
        message: str,
        *,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class BenchmarkRunRepositoryNotRegisteredError(BenchmarkRunError):
    """Raised when a benchmark targets an unknown repository."""

    exit_code = 24
    error_code = ErrorCode.REPOSITORY_NOT_REGISTERED


class BenchmarkRunBaselineMissingError(BenchmarkRunError):
    """Raised when the selected retrieval mode has no usable current baseline."""

    exit_code = 66
    error_code = ErrorCode.BENCHMARK_RETRIEVAL_BASELINE_MISSING


class BenchmarkRunModeUnavailableError(BenchmarkRunError):
    """Raised when the selected retrieval mode cannot execute truthfully."""

    exit_code = 67
    error_code = ErrorCode.BENCHMARK_RETRIEVAL_MODE_UNAVAILABLE


class BenchmarkRunInterruptedError(BenchmarkRunError):
    """Raised when benchmark execution is interrupted after the run has started."""

    exit_code = 130

    def __init__(self, *, details: Any | None = None) -> None:
        super().__init__("Benchmark execution was interrupted.", details=details)


@dataclass(slots=True, frozen=True)
class ResolvedBenchmarkExecutionContext:
    """Resolved repository/build context shared across all benchmark cases."""

    repository: RepositoryRecord
    snapshot: SnapshotRecord
    build: (
        LexicalRetrievalBuildContext | SemanticRetrievalBuildContext | HybridRetrievalBuildContext
    )
    provenance_context: RunProvenanceWorkflowContext
    indexing_config_fingerprint: str | None = None
    semantic_config_fingerprint: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    model_version: str | None = None


@dataclass(slots=True)
class RunBenchmarkUseCase:
    """Run one benchmark dataset against one currently indexed retrieval baseline."""

    runtime_paths: RuntimePaths
    repository_store: RepositoryMetadataStorePort
    snapshot_store: SnapshotMetadataStorePort
    index_build_store: IndexBuildStorePort
    semantic_index_build_store: SemanticIndexBuildStorePort
    benchmark_run_store: BenchmarkRunStorePort
    artifact_store: ArtifactStorePort
    load_benchmark_dataset: LoadBenchmarkDatasetUseCase
    run_lexical_query: RunLexicalQueryUseCase
    run_semantic_query: RunSemanticQueryUseCase
    run_hybrid_query: RunHybridQueryUseCase
    indexing_config: IndexingConfig
    semantic_indexing_config: SemanticIndexingConfig
    embedding_providers_config: EmbeddingProvidersConfig
    record_run_provenance: RecordRunConfigurationProvenanceUseCase | None = None

    def execute(
        self,
        request: RunBenchmarkRequest,
        *,
        progress: ProgressReporter | None = None,
    ) -> RunBenchmarkResult:
        """Execute the benchmark dataset in deterministic case order."""

        self._report(progress, f"Loading benchmark dataset: {request.dataset_path}")
        dataset_result = self.load_benchmark_dataset.execute(
            LoadBenchmarkDatasetRequest(dataset_path=request.dataset_path)
        )

        self._initialize_runtime()
        self._report(
            progress,
            (
                "Resolving benchmark baseline for repository: "
                f"{request.repository_id} ({request.retrieval_mode})"
            ),
        )
        context = self._resolve_execution_context(request)

        run_id = uuid4().hex
        started_at = datetime.now(UTC)
        running_record = BenchmarkRunRecord(
            run_id=run_id,
            repository_id=context.repository.repository_id,
            snapshot_id=context.snapshot.snapshot_id,
            retrieval_mode=request.retrieval_mode,
            dataset_id=dataset_result.summary.dataset_id,
            dataset_version=dataset_result.summary.dataset_version,
            dataset_fingerprint=dataset_result.summary.dataset_fingerprint,
            case_count=dataset_result.summary.case_count,
            completed_case_count=0,
            status=BenchmarkRunStatus.RUNNING,
            started_at=started_at,
        )
        executed_cases: list[BenchmarkCaseExecutionArtifact] = []
        with _trap_execution_interrupts():
            try:
                self.benchmark_run_store.create_run(running_record)

                total_cases = len(dataset_result.dataset.cases)
                for index, case in enumerate(dataset_result.dataset.cases, start=1):
                    self._report(
                        progress,
                        f"Running benchmark case {index}/{total_cases}: {case.query_id}",
                    )
                    executed_cases.append(
                        BenchmarkCaseExecutionArtifact(
                            query_id=case.query_id,
                            source_kind=case.source_kind,
                            judgments=list(case.judgments),
                            result=self._execute_case(
                                case_query_id=case.query_id,
                                query_text=case.query_text,
                                context=context,
                                retrieval_mode=request.retrieval_mode,
                                max_results=request.max_results,
                            ),
                        )
                    )
                    running_record = running_record.model_copy(
                        update={"completed_case_count": len(executed_cases)}
                    )
                    self.benchmark_run_store.update_run(running_record)

                self._report(progress, f"Writing benchmark artifact for run: {run_id}")
                succeeded_record = running_record.model_copy(
                    update={
                        "status": BenchmarkRunStatus.SUCCEEDED,
                        "completed_case_count": len(executed_cases),
                        "completed_at": datetime.now(UTC),
                    }
                )
                succeeded_record = self._persist_artifact_and_finalize(
                    record=succeeded_record,
                    context=context,
                    dataset_result=dataset_result,
                    max_results=request.max_results,
                    cases=executed_cases,
                    failure=None,
                )
                self._record_provenance(
                    record=succeeded_record,
                    context=context,
                    dataset_id=dataset_result.summary.dataset_id,
                    dataset_version=dataset_result.summary.dataset_version,
                    dataset_fingerprint=dataset_result.summary.dataset_fingerprint,
                    case_count=dataset_result.summary.case_count,
                    retrieval_mode=request.retrieval_mode,
                    max_results=request.max_results,
                    progress=progress,
                )
                return self._build_result(
                    record=succeeded_record,
                    context=context,
                    dataset_summary=dataset_result.summary,
                )
            except BenchmarkRunError as error:
                self._finalize_failed_run_if_started(
                    record=running_record,
                    context=context,
                    dataset_result=dataset_result,
                    max_results=request.max_results,
                    cases=executed_cases,
                    error=error,
                )
                raise error from None
            except KeyboardInterrupt as exc:
                error = BenchmarkRunInterruptedError(details={"reason": type(exc).__name__})
                self._finalize_failed_run_if_started(
                    record=running_record,
                    context=context,
                    dataset_result=dataset_result,
                    max_results=request.max_results,
                    cases=executed_cases,
                    error=error,
                )
                raise error from None
            except SystemExit as exc:
                if exc.code in (None, 0):
                    raise
                error = BenchmarkRunInterruptedError(
                    details={
                        "reason": type(exc).__name__,
                        "exit_code": exc.code,
                    }
                )
                self._finalize_failed_run_if_started(
                    record=running_record,
                    context=context,
                    dataset_result=dataset_result,
                    max_results=request.max_results,
                    cases=executed_cases,
                    error=error,
                )
                raise error from None
            except Exception as exc:
                error = BenchmarkRunError(
                    "Benchmark execution failed unexpectedly.",
                    details={"reason": str(exc)},
                )
                self._finalize_failed_run_if_started(
                    record=running_record,
                    context=context,
                    dataset_result=dataset_result,
                    max_results=request.max_results,
                    cases=executed_cases,
                    error=error,
                )
                raise error from exc

    def _initialize_runtime(self) -> None:
        provision_runtime_paths(self.runtime_paths)
        self.repository_store.initialize()
        self.snapshot_store.initialize()
        self.index_build_store.initialize()
        self.semantic_index_build_store.initialize()
        self.benchmark_run_store.initialize()

    def _resolve_execution_context(
        self,
        request: RunBenchmarkRequest,
    ) -> ResolvedBenchmarkExecutionContext:
        repository = self.repository_store.get_by_repository_id(request.repository_id)
        if repository is None:
            raise BenchmarkRunRepositoryNotRegisteredError(
                f"Repository is not registered: {request.repository_id}",
            )

        if request.retrieval_mode == "lexical":
            return self._resolve_lexical_context(
                repository=repository,
                max_results=request.max_results,
            )
        if request.retrieval_mode == "semantic":
            return self._resolve_semantic_context(
                repository=repository,
                max_results=request.max_results,
            )
        return self._resolve_hybrid_context(
            repository=repository,
            max_results=request.max_results,
        )

    def _resolve_lexical_context(
        self,
        *,
        repository: RepositoryRecord,
        max_results: int,
    ) -> ResolvedBenchmarkExecutionContext:
        indexing_fingerprint = build_indexing_fingerprint(self.indexing_config)
        build = self.index_build_store.get_latest_build_for_repository(
            repository.repository_id,
            indexing_fingerprint,
        )
        if build is None:
            raise BenchmarkRunBaselineMissingError(
                "Benchmark cannot run because the lexical retrieval baseline is unavailable.",
                details={
                    "retrieval_mode": "lexical",
                    "component": "lexical",
                    "repository_id": repository.repository_id,
                    "indexing_config_fingerprint": indexing_fingerprint,
                },
            )
        if not build.index_path.exists():
            raise BenchmarkRunModeUnavailableError(
                "Benchmark cannot run because the lexical retrieval artifact is missing.",
                details={
                    "retrieval_mode": "lexical",
                    "component": "lexical",
                    "build_id": build.build_id,
                    "artifact_path": str(build.index_path),
                },
            )

        snapshot = self._resolve_snapshot(
            snapshot_id=build.snapshot_id,
            retrieval_mode="lexical",
            build_id=build.build_id,
        )
        return ResolvedBenchmarkExecutionContext(
            repository=repository,
            snapshot=snapshot,
            build=_lexical_build_context(build),
            indexing_config_fingerprint=build.indexing_config_fingerprint,
            provenance_context=RunProvenanceWorkflowContext(
                lexical_build_id=build.build_id,
                max_results=max_results,
            ),
        )

    def _resolve_semantic_context(
        self,
        *,
        repository: RepositoryRecord,
        max_results: int,
    ) -> ResolvedBenchmarkExecutionContext:
        try:
            semantic_config_fingerprint = build_semantic_indexing_fingerprint(
                self.semantic_indexing_config,
                self.embedding_providers_config,
            )
            vector_dimension = self.semantic_indexing_config.resolved_vector_dimension()
        except ValueError as exc:
            raise BenchmarkRunModeUnavailableError(
                f"Benchmark cannot run because the semantic query configuration is invalid: {exc}",
                details={
                    "retrieval_mode": "semantic",
                    "component": "semantic",
                },
            ) from exc

        build = self.semantic_index_build_store.get_latest_build_for_repository(
            repository.repository_id,
            semantic_config_fingerprint,
        )
        if build is None:
            raise BenchmarkRunBaselineMissingError(
                "Benchmark cannot run because the semantic retrieval baseline is unavailable.",
                details={
                    "retrieval_mode": "semantic",
                    "component": "semantic",
                    "repository_id": repository.repository_id,
                    "semantic_config_fingerprint": semantic_config_fingerprint,
                },
            )
        if not build.artifact_path.exists():
            raise BenchmarkRunModeUnavailableError(
                "Benchmark cannot run because the semantic retrieval artifact is missing.",
                details={
                    "retrieval_mode": "semantic",
                    "component": "semantic",
                    "build_id": build.build_id,
                    "artifact_path": str(build.artifact_path),
                },
            )

        snapshot = self._resolve_snapshot(
            snapshot_id=build.snapshot_id,
            retrieval_mode="semantic",
            build_id=build.build_id,
        )
        try:
            provider = resolve_local_embedding_provider(
                self.semantic_indexing_config,
                self.embedding_providers_config,
            )
        except EmbeddingProviderUnavailableError as exc:
            raise BenchmarkRunModeUnavailableError(
                "Benchmark cannot run because the semantic retrieval mode is unavailable.",
                details={
                    "retrieval_mode": "semantic",
                    "component": "semantic",
                    "component_error_code": ErrorCode.EMBEDDING_PROVIDER_UNAVAILABLE,
                    "component_details": exc.details,
                },
            ) from exc

        if not _semantic_build_matches_provider(
            build=build,
            provider_id=provider.provider_id,
            model_id=provider.model_id,
            model_version=provider.model_version,
            vector_dimension=vector_dimension,
        ):
            raise BenchmarkRunBaselineMissingError(
                (
                    "Benchmark cannot run because the semantic retrieval baseline does "
                    "not match the current effective configuration."
                ),
                details={
                    "retrieval_mode": "semantic",
                    "component": "semantic",
                    "build_id": build.build_id,
                    "semantic_config_fingerprint": semantic_config_fingerprint,
                },
            )

        return ResolvedBenchmarkExecutionContext(
            repository=repository,
            snapshot=snapshot,
            build=_semantic_build_context(build),
            semantic_config_fingerprint=build.semantic_config_fingerprint,
            provider_id=build.provider_id,
            model_id=build.model_id,
            model_version=build.model_version,
            provenance_context=RunProvenanceWorkflowContext(
                semantic_build_id=build.build_id,
                max_results=max_results,
            ),
        )

    def _resolve_hybrid_context(
        self,
        *,
        repository: RepositoryRecord,
        max_results: int,
    ) -> ResolvedBenchmarkExecutionContext:
        lexical_context = self._resolve_lexical_context(
            repository=repository,
            max_results=max_results,
        )
        semantic_context = self._resolve_semantic_context(
            repository=repository,
            max_results=max_results,
        )
        self._validate_hybrid_alignment(
            lexical_snapshot=lexical_context.snapshot,
            semantic_snapshot=semantic_context.snapshot,
            lexical_build_id=lexical_context.build.build_id,
            semantic_build_id=semantic_context.build.build_id,
            repository_id=repository.repository_id,
        )

        rank_window_size = max(max_results, self.run_hybrid_query.candidate_window_size)
        build = HybridRetrievalBuildContext(
            build_id=_build_hybrid_context_id(
                lexical_build_id=lexical_context.build.build_id,
                semantic_build_id=semantic_context.build.build_id,
            ),
            rank_constant=self.run_hybrid_query.rank_constant,
            rank_window_size=rank_window_size,
            lexical_build=lexical_context.build,
            semantic_build=semantic_context.build,
        )
        return ResolvedBenchmarkExecutionContext(
            repository=repository,
            snapshot=lexical_context.snapshot,
            build=build,
            indexing_config_fingerprint=lexical_context.indexing_config_fingerprint,
            semantic_config_fingerprint=semantic_context.semantic_config_fingerprint,
            provider_id=semantic_context.provider_id,
            model_id=semantic_context.model_id,
            model_version=semantic_context.model_version,
            provenance_context=RunProvenanceWorkflowContext(
                lexical_build_id=lexical_context.build.build_id,
                semantic_build_id=semantic_context.build.build_id,
                retrieval_mode="hybrid",
                max_results=max_results,
                rank_constant=self.run_hybrid_query.rank_constant,
                rank_window_size=rank_window_size,
            ),
        )

    def _resolve_snapshot(
        self,
        *,
        snapshot_id: str,
        retrieval_mode: RetrievalMode,
        build_id: str,
    ) -> SnapshotRecord:
        snapshot = self.snapshot_store.get_by_snapshot_id(snapshot_id)
        if snapshot is None:
            raise BenchmarkRunModeUnavailableError(
                (
                    "Benchmark cannot run because the selected retrieval build points "
                    "to an unknown snapshot."
                ),
                details={
                    "retrieval_mode": retrieval_mode,
                    "snapshot_id": snapshot_id,
                    "build_id": build_id,
                },
            )
        return snapshot

    def _execute_case(
        self,
        *,
        case_query_id: str,
        query_text: str,
        context: ResolvedBenchmarkExecutionContext,
        retrieval_mode: RetrievalMode,
        max_results: int,
    ) -> BenchmarkCaseRetrievalResult:
        try:
            if retrieval_mode == "lexical":
                return self.run_lexical_query.execute(
                    RunLexicalQueryRequest(
                        repository_id=context.repository.repository_id,
                        query_text=query_text,
                        max_results=max_results,
                        build_id=context.build.build_id,
                        record_provenance=False,
                    )
                )
            if retrieval_mode == "semantic":
                return self.run_semantic_query.execute(
                    RunSemanticQueryRequest(
                        repository_id=context.repository.repository_id,
                        query_text=query_text,
                        max_results=max_results,
                        build_id=context.build.build_id,
                        record_provenance=False,
                    )
                )
            return self.run_hybrid_query.execute(
                RunHybridQueryRequest(
                    repository_id=context.repository.repository_id,
                    query_text=query_text,
                    max_results=max_results,
                    lexical_build_id=context.build.lexical_build.build_id,
                    semantic_build_id=context.build.semantic_build.build_id,
                    record_provenance=False,
                )
            )
        except (
            LexicalQueryRepositoryNotRegisteredError,
            SemanticQueryRepositoryNotRegisteredError,
            HybridQueryRepositoryNotRegisteredError,
        ) as exc:
            raise BenchmarkRunRepositoryNotRegisteredError(exc.message) from exc
        except (
            LexicalBuildBaselineMissingError,
            SemanticBuildBaselineMissingError,
            HybridComponentBaselineMissingError,
        ) as exc:
            raise BenchmarkRunBaselineMissingError(
                (
                    "Benchmark cannot continue because the selected retrieval baseline "
                    "became unavailable during execution."
                ),
                details=_case_error_details(
                    query_id=case_query_id,
                    retrieval_mode=retrieval_mode,
                    error=exc,
                ),
            ) from exc
        except (
            LexicalArtifactMissingError,
            SemanticArtifactMissingError,
            SemanticArtifactCorruptError,
            SemanticQueryProviderUnavailableError,
            HybridComponentUnavailableError,
            HybridSnapshotMismatchError,
            LexicalQueryError,
            SemanticQueryError,
            HybridQueryError,
        ) as exc:
            raise BenchmarkRunModeUnavailableError(
                (
                    "Benchmark cannot continue because the selected retrieval mode is "
                    "unavailable during execution."
                ),
                details=_case_error_details(
                    query_id=case_query_id,
                    retrieval_mode=retrieval_mode,
                    error=exc,
                ),
            ) from exc

    def _persist_artifact_and_finalize(
        self,
        *,
        record: BenchmarkRunRecord,
        context: ResolvedBenchmarkExecutionContext,
        dataset_result: Any,
        max_results: int,
        cases: list[BenchmarkCaseExecutionArtifact],
        failure: BenchmarkRunFailure | None,
    ) -> BenchmarkRunRecord:
        artifact_document = BenchmarkRunArtifactDocument(
            run=record,
            repository=_repository_context(context.repository),
            snapshot=_snapshot_context(context.snapshot),
            build=context.build,
            dataset=dataset_result.dataset,
            dataset_summary=dataset_result.summary,
            max_results=max_results,
            cases=cases,
            failure=failure,
        )
        artifact_path = self.artifact_store.write_benchmark_run_artifact(
            artifact_document,
            run_id=record.run_id,
        )
        finalized_record = record.model_copy(update={"artifact_path": artifact_path})
        artifact_document = artifact_document.model_copy(update={"run": finalized_record})
        self.artifact_store.write_benchmark_run_artifact(
            artifact_document,
            run_id=record.run_id,
        )
        self.benchmark_run_store.update_run(finalized_record)
        return finalized_record

    def _finalize_failed_run(
        self,
        *,
        record: BenchmarkRunRecord,
        context: ResolvedBenchmarkExecutionContext,
        dataset_result: Any,
        max_results: int,
        cases: list[BenchmarkCaseExecutionArtifact],
        error: BenchmarkRunError,
    ) -> BenchmarkRunRecord:
        failed_record = record.model_copy(
            update={
                "completed_case_count": len(cases),
                "status": BenchmarkRunStatus.FAILED,
                "error_code": error.error_code,
                "error_message": error.message,
                "completed_at": datetime.now(UTC),
            }
        )
        failure = BenchmarkRunFailure(
            error_code=error.error_code,
            message=error.message,
            phase="execution",
            failed_case_query_id=_extract_failed_case_query_id(error.details),
            details=_normalize_failure_details(error.details),
        )
        try:
            return self._persist_artifact_and_finalize(
                record=failed_record,
                context=context,
                dataset_result=dataset_result,
                max_results=max_results,
                cases=cases,
                failure=failure,
            )
        except Exception:
            self.benchmark_run_store.update_run(failed_record)
            return failed_record

    def _finalize_failed_run_if_started(
        self,
        *,
        record: BenchmarkRunRecord,
        context: ResolvedBenchmarkExecutionContext,
        dataset_result: Any,
        max_results: int,
        cases: list[BenchmarkCaseExecutionArtifact],
        error: BenchmarkRunError,
    ) -> BenchmarkRunRecord | None:
        if self.benchmark_run_store.get_by_run_id(record.run_id) is None:
            return None
        return self._finalize_failed_run(
            record=record,
            context=context,
            dataset_result=dataset_result,
            max_results=max_results,
            cases=cases,
            error=error,
        )

    def _record_provenance(
        self,
        *,
        record: BenchmarkRunRecord,
        context: ResolvedBenchmarkExecutionContext,
        dataset_id: str,
        dataset_version: str,
        dataset_fingerprint: str,
        case_count: int,
        retrieval_mode: RetrievalMode,
        max_results: int,
        progress: ProgressReporter | None,
    ) -> None:
        if self.record_run_provenance is None:
            return

        workflow_context = context.provenance_context.model_copy(
            update={
                "benchmark_dataset_id": dataset_id,
                "benchmark_dataset_version": dataset_version,
                "benchmark_dataset_fingerprint": dataset_fingerprint,
                "retrieval_mode": retrieval_mode,
                "benchmark_case_count": case_count,
                "max_results": max_results,
            }
        )
        self._report(progress, f"Recording benchmark provenance for run: {record.run_id}")
        self.record_run_provenance.execute(
            RecordRunConfigurationProvenanceRequest(
                run_id=record.run_id,
                workflow_type="eval.benchmark",
                repository_id=record.repository_id,
                snapshot_id=record.snapshot_id,
                indexing_config_fingerprint=context.indexing_config_fingerprint,
                semantic_config_fingerprint=context.semantic_config_fingerprint,
                provider_id=context.provider_id,
                model_id=context.model_id,
                model_version=context.model_version,
                workflow_context=workflow_context,
            )
        )

    def _build_result(
        self,
        *,
        record: BenchmarkRunRecord,
        context: ResolvedBenchmarkExecutionContext,
        dataset_summary: Any,
    ) -> RunBenchmarkResult:
        return RunBenchmarkResult(
            run=record,
            repository=_repository_context(context.repository),
            snapshot=_snapshot_context(context.snapshot),
            build=context.build,
            dataset=dataset_summary,
        )

    def _validate_hybrid_alignment(
        self,
        *,
        lexical_snapshot: SnapshotRecord,
        semantic_snapshot: SnapshotRecord,
        lexical_build_id: str,
        semantic_build_id: str,
        repository_id: str,
    ) -> None:
        if (
            lexical_snapshot.snapshot_id != semantic_snapshot.snapshot_id
            or lexical_snapshot.revision_identity != semantic_snapshot.revision_identity
            or lexical_snapshot.revision_source != semantic_snapshot.revision_source
        ):
            raise BenchmarkRunModeUnavailableError(
                (
                    "Benchmark cannot run because the hybrid retrieval mode resolved "
                    "different component snapshots."
                ),
                details={
                    "retrieval_mode": "hybrid",
                    "repository_id": repository_id,
                    "lexical_snapshot_id": lexical_snapshot.snapshot_id,
                    "semantic_snapshot_id": semantic_snapshot.snapshot_id,
                    "lexical_revision_identity": lexical_snapshot.revision_identity,
                    "semantic_revision_identity": semantic_snapshot.revision_identity,
                    "lexical_build_id": lexical_build_id,
                    "semantic_build_id": semantic_build_id,
                },
            )

    @staticmethod
    def _report(progress: ProgressReporter | None, message: str) -> None:
        if progress is not None:
            progress(message)


def _repository_context(repository: RepositoryRecord) -> RetrievalRepositoryContext:
    return RetrievalRepositoryContext(
        repository_id=repository.repository_id,
        repository_name=repository.repository_name,
    )


def _snapshot_context(snapshot: SnapshotRecord) -> RetrievalSnapshotContext:
    return RetrievalSnapshotContext(
        snapshot_id=snapshot.snapshot_id,
        revision_identity=snapshot.revision_identity,
        revision_source=snapshot.revision_source,
    )


def _lexical_build_context(build: LexicalIndexBuildRecord) -> LexicalRetrievalBuildContext:
    return LexicalRetrievalBuildContext(
        build_id=build.build_id,
        indexing_config_fingerprint=build.indexing_config_fingerprint,
        lexical_engine=build.lexical_engine,
        tokenizer_spec=build.tokenizer_spec,
        indexed_fields=list(build.indexed_fields),
    )


def _semantic_build_context(build: SemanticIndexBuildRecord) -> SemanticRetrievalBuildContext:
    return SemanticRetrievalBuildContext(
        build_id=build.build_id,
        provider_id=build.provider_id,
        model_id=build.model_id,
        model_version=build.model_version,
        vector_engine=build.vector_engine,
        semantic_config_fingerprint=build.semantic_config_fingerprint,
    )


def _semantic_build_matches_provider(
    *,
    build: SemanticIndexBuildRecord,
    provider_id: str,
    model_id: str,
    model_version: str,
    vector_dimension: int,
) -> bool:
    return (
        build.provider_id == provider_id
        and build.model_id == model_id
        and build.model_version == model_version
        and build.embedding_dimension == vector_dimension
    )


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


@contextmanager
def _trap_execution_interrupts() -> Any:
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    signals = [
        getattr(signal, signal_name)
        for signal_name in ("SIGINT", "SIGTERM")
        if hasattr(signal, signal_name)
    ]
    previous_handlers = {
        handled_signal: signal.getsignal(handled_signal) for handled_signal in signals
    }

    def _handle_interrupt(signum: int, frame: FrameType | None) -> None:
        del frame
        raise BenchmarkRunInterruptedError(details={"reason": signal.Signals(signum).name})

    try:
        for handled_signal in signals:
            signal.signal(handled_signal, _handle_interrupt)
        yield
    finally:
        for handled_signal, previous_handler in previous_handlers.items():
            signal.signal(handled_signal, previous_handler)


def _case_error_details(
    *,
    query_id: str,
    retrieval_mode: RetrievalMode,
    error: Exception,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "query_id": query_id,
        "retrieval_mode": retrieval_mode,
        "component_error_code": getattr(error, "error_code", ErrorCode.BENCHMARK_EXECUTION_FAILED),
    }
    nested_details = getattr(error, "details", None)
    if nested_details is not None:
        details["component_details"] = nested_details
    return details


def _extract_failed_case_query_id(details: Any) -> str | None:
    if not isinstance(details, dict):
        return None
    query_id = details.get("query_id")
    return query_id if isinstance(query_id, str) else None


def _normalize_failure_details(details: Any) -> dict[str, Any] | None:
    if isinstance(details, dict):
        return details
    return None

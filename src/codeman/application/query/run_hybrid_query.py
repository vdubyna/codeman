"""Run hybrid retrieval queries by composing lexical and semantic paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha1
from time import perf_counter
from typing import Any

from codeman.application.provenance.record_run_provenance import (
    RecordRunConfigurationProvenanceUseCase,
)
from codeman.application.query.format_results import RetrievalResultFormatter
from codeman.application.query.hybrid_fusion import (
    DEFAULT_HYBRID_RANK_CONSTANT,
    FusedHybridResult,
    fuse_hybrid_results,
)
from codeman.application.query.run_lexical_query import (
    LexicalBuildBaselineMissingError,
    LexicalQueryError,
    LexicalQueryRepositoryNotRegisteredError,
    RunLexicalQueryUseCase,
)
from codeman.application.query.run_semantic_query import (
    RunSemanticQueryUseCase,
    SemanticBuildBaselineMissingError,
    SemanticQueryError,
    SemanticQueryRepositoryNotRegisteredError,
)
from codeman.contracts.configuration import (
    RecordRunConfigurationProvenanceRequest,
    RunProvenanceWorkflowContext,
)
from codeman.contracts.errors import ErrorCode
from codeman.contracts.retrieval import (
    HybridComponentQueryDiagnostics,
    HybridQueryDiagnostics,
    HybridRetrievalBuildContext,
    RunHybridQueryRequest,
    RunHybridQueryResult,
    RunLexicalQueryRequest,
    RunLexicalQueryResult,
    RunSemanticQueryRequest,
    RunSemanticQueryResult,
)

DEFAULT_HYBRID_CANDIDATE_WINDOW = 50

__all__ = [
    "DEFAULT_HYBRID_CANDIDATE_WINDOW",
    "HybridComponentBaselineMissingError",
    "HybridQueryComposition",
    "HybridComponentUnavailableError",
    "HybridQueryError",
    "HybridQueryRepositoryNotRegisteredError",
    "HybridSnapshotMismatchError",
    "RunHybridQueryUseCase",
    "compose_hybrid_result_from_components",
]


class HybridQueryError(Exception):
    """Base exception for hybrid-query failures."""

    exit_code = 47
    error_code = ErrorCode.HYBRID_QUERY_FAILED

    def __init__(
        self,
        message: str,
        *,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class HybridQueryRepositoryNotRegisteredError(HybridQueryError):
    """Raised when querying an unknown repository."""

    exit_code = 24
    error_code = ErrorCode.REPOSITORY_NOT_REGISTERED


class HybridComponentBaselineMissingError(HybridQueryError):
    """Raised when one hybrid component has no usable baseline."""

    exit_code = 48
    error_code = ErrorCode.HYBRID_COMPONENT_BASELINE_MISSING


class HybridComponentUnavailableError(HybridQueryError):
    """Raised when one hybrid component is unavailable or corrupt."""

    exit_code = 49
    error_code = ErrorCode.HYBRID_COMPONENT_UNAVAILABLE


class HybridSnapshotMismatchError(HybridQueryError):
    """Raised when lexical and semantic query paths resolve different snapshots."""

    exit_code = 50
    error_code = ErrorCode.HYBRID_SNAPSHOT_MISMATCH


@dataclass(slots=True, frozen=True)
class HybridQueryComposition:
    """Reusable hybrid package assembled from pre-resolved lexical and semantic results."""

    result: RunHybridQueryResult
    fused_results: tuple[FusedHybridResult, ...]


@dataclass(slots=True)
class RunHybridQueryUseCase:
    """Compose lexical and semantic retrieval into one fused hybrid result package."""

    run_lexical_query: RunLexicalQueryUseCase
    run_semantic_query: RunSemanticQueryUseCase
    record_run_provenance: RecordRunConfigurationProvenanceUseCase | None = None
    formatter: RetrievalResultFormatter = field(default_factory=RetrievalResultFormatter)
    candidate_window_size: int = DEFAULT_HYBRID_CANDIDATE_WINDOW
    rank_constant: int = DEFAULT_HYBRID_RANK_CONSTANT

    def execute(self, request: RunHybridQueryRequest) -> RunHybridQueryResult:
        """Run one hybrid query against the current repository build state."""

        started_at = perf_counter()
        candidate_window = max(request.max_results, self.candidate_window_size)
        lexical_result = self._run_lexical(request, candidate_window=candidate_window)
        semantic_result = self._run_semantic(request, candidate_window=candidate_window)
        self._validate_component_alignment(
            lexical_result=lexical_result,
            semantic_result=semantic_result,
        )
        composition = compose_hybrid_result_from_components(
            formatter=self.formatter,
            lexical_result=lexical_result,
            semantic_result=semantic_result,
            query_text=request.query_text,
            max_results=request.max_results,
            rank_window_size=candidate_window,
            rank_constant=self.rank_constant,
            latency_ms=int((perf_counter() - started_at) * 1000),
        )
        if not request.record_provenance or self.record_run_provenance is None:
            return composition.result

        provenance = self.record_run_provenance.execute(
            RecordRunConfigurationProvenanceRequest(
                workflow_type="query.hybrid",
                repository_id=composition.result.repository.repository_id,
                snapshot_id=composition.result.snapshot.snapshot_id,
                indexing_config_fingerprint=lexical_result.build.indexing_config_fingerprint,
                semantic_config_fingerprint=semantic_result.build.semantic_config_fingerprint,
                provider_id=semantic_result.build.provider_id,
                model_id=semantic_result.build.model_id,
                model_version=semantic_result.build.model_version,
                workflow_context=RunProvenanceWorkflowContext(
                    lexical_build_id=lexical_result.build.build_id,
                    semantic_build_id=semantic_result.build.build_id,
                    max_results=request.max_results,
                    rank_constant=self.rank_constant,
                    rank_window_size=candidate_window,
                ),
            )
        )
        return composition.result.model_copy(update={"run_id": provenance.run_id})

    def _run_lexical(
        self,
        request: RunHybridQueryRequest,
        *,
        candidate_window: int,
    ) -> RunLexicalQueryResult:
        try:
            return self.run_lexical_query.execute(
                RunLexicalQueryRequest(
                    repository_id=request.repository_id,
                    query_text=request.query_text,
                    max_results=candidate_window,
                    build_id=request.lexical_build_id,
                    record_provenance=False,
                )
            )
        except LexicalQueryRepositoryNotRegisteredError as exc:
            raise HybridQueryRepositoryNotRegisteredError(exc.message) from exc
        except LexicalBuildBaselineMissingError as exc:
            raise HybridComponentBaselineMissingError(
                "Hybrid query cannot run because the lexical baseline is unavailable.",
                details=self._component_details(component="lexical", error=exc),
            ) from exc
        except LexicalQueryError as exc:
            raise HybridComponentUnavailableError(
                f"Hybrid query cannot run because the lexical retrieval path is unavailable: "
                f"{exc.message}",
                details=self._component_details(component="lexical", error=exc),
            ) from exc

    def _run_semantic(
        self,
        request: RunHybridQueryRequest,
        *,
        candidate_window: int,
    ) -> RunSemanticQueryResult:
        try:
            return self.run_semantic_query.execute(
                RunSemanticQueryRequest(
                    repository_id=request.repository_id,
                    query_text=request.query_text,
                    max_results=candidate_window,
                    build_id=request.semantic_build_id,
                    record_provenance=False,
                )
            )
        except SemanticQueryRepositoryNotRegisteredError as exc:
            raise HybridQueryRepositoryNotRegisteredError(exc.message) from exc
        except SemanticBuildBaselineMissingError as exc:
            raise HybridComponentBaselineMissingError(
                "Hybrid query cannot run because the semantic baseline is unavailable.",
                details=self._component_details(component="semantic", error=exc),
            ) from exc
        except SemanticQueryError as exc:
            raise HybridComponentUnavailableError(
                f"Hybrid query cannot run because the semantic retrieval path is unavailable: "
                f"{exc.message}",
                details=self._component_details(component="semantic", error=exc),
            ) from exc

    def _validate_component_alignment(
        self,
        *,
        lexical_result: RunLexicalQueryResult,
        semantic_result: RunSemanticQueryResult,
    ) -> None:
        lexical_snapshot = lexical_result.snapshot
        semantic_snapshot = semantic_result.snapshot
        if (
            lexical_result.repository.repository_id != semantic_result.repository.repository_id
            or lexical_snapshot.snapshot_id != semantic_snapshot.snapshot_id
            or lexical_snapshot.revision_identity != semantic_snapshot.revision_identity
            or lexical_snapshot.revision_source != semantic_snapshot.revision_source
        ):
            raise HybridSnapshotMismatchError(
                "Hybrid query cannot fuse lexical and semantic results from different "
                "repository snapshots.",
                details={
                    "lexical_snapshot_id": lexical_snapshot.snapshot_id,
                    "semantic_snapshot_id": semantic_snapshot.snapshot_id,
                    "lexical_revision_identity": lexical_snapshot.revision_identity,
                    "semantic_revision_identity": semantic_snapshot.revision_identity,
                    "lexical_build_id": lexical_result.build.build_id,
                    "semantic_build_id": semantic_result.build.build_id,
                },
            )

    def _build_diagnostics(
        self,
        *,
        lexical_result: RunLexicalQueryResult,
        semantic_result: RunSemanticQueryResult,
        fused_results: list[FusedHybridResult],
        total_fused_results: int,
        latency_ms: int,
        rank_window_size: int,
    ) -> HybridQueryDiagnostics:
        lexical_contribution_count = sum(
            1 for result in fused_results if result.lexical_rank is not None
        )
        semantic_contribution_count = sum(
            1 for result in fused_results if result.semantic_rank is not None
        )
        component_truncated = (
            lexical_result.diagnostics.truncated or semantic_result.diagnostics.truncated
        )
        total_match_count = total_fused_results
        if component_truncated:
            total_match_count = max(
                total_fused_results,
                lexical_result.diagnostics.total_match_count,
                semantic_result.diagnostics.total_match_count,
            )
        return HybridQueryDiagnostics(
            match_count=len(fused_results),
            total_match_count=total_match_count,
            truncated=component_truncated or total_fused_results > len(fused_results),
            query_latency_ms=latency_ms,
            rank_constant=self.rank_constant,
            rank_window_size=rank_window_size,
            total_match_count_is_lower_bound=component_truncated,
            lexical=HybridComponentQueryDiagnostics(
                match_count=lexical_result.diagnostics.match_count,
                total_match_count=lexical_result.diagnostics.total_match_count,
                truncated=lexical_result.diagnostics.truncated,
                query_latency_ms=lexical_result.diagnostics.query_latency_ms,
                contributed_result_count=lexical_contribution_count,
            ),
            semantic=HybridComponentQueryDiagnostics(
                match_count=semantic_result.diagnostics.match_count,
                total_match_count=semantic_result.diagnostics.total_match_count,
                truncated=semantic_result.diagnostics.truncated,
                query_latency_ms=semantic_result.diagnostics.query_latency_ms,
                contributed_result_count=semantic_contribution_count,
            ),
        )

    @staticmethod
    def _component_details(
        *,
        component: str,
        error: LexicalQueryError | SemanticQueryError,
    ) -> dict[str, Any]:
        details: dict[str, Any] = {
            "component": component,
            "component_error_code": error.error_code,
        }
        component_details = getattr(error, "details", None)
        if component_details is not None:
            details["component_details"] = component_details
        return details

    @staticmethod
    def _build_hybrid_context_id(
        *,
        lexical_build_id: str,
        semantic_build_id: str,
    ) -> str:
        return _build_hybrid_context_id(
            lexical_build_id=lexical_build_id,
            semantic_build_id=semantic_build_id,
        )


def compose_hybrid_result_from_components(
    *,
    lexical_result: RunLexicalQueryResult,
    semantic_result: RunSemanticQueryResult,
    query_text: str,
    max_results: int,
    rank_window_size: int,
    rank_constant: int = DEFAULT_HYBRID_RANK_CONSTANT,
    latency_ms: int = 0,
    formatter: RetrievalResultFormatter | None = None,
) -> HybridQueryComposition:
    """Assemble a hybrid result package from already resolved lexical and semantic packages."""

    resolved_formatter = formatter or RetrievalResultFormatter()
    _validate_component_alignment(
        lexical_result=lexical_result,
        semantic_result=semantic_result,
    )
    all_fused_results = fuse_hybrid_results(
        lexical_results=lexical_result.results,
        semantic_results=semantic_result.results,
        max_results=rank_window_size * 2,
        rank_window_size=rank_window_size,
        rank_constant=rank_constant,
    )
    final_results = all_fused_results[:max_results]
    diagnostics = _build_diagnostics(
        lexical_result=lexical_result,
        semantic_result=semantic_result,
        fused_results=final_results,
        total_fused_results=len(all_fused_results),
        latency_ms=latency_ms,
        rank_window_size=rank_window_size,
        rank_constant=rank_constant,
    )
    build = HybridRetrievalBuildContext(
        build_id=_build_hybrid_context_id(
            lexical_build_id=lexical_result.build.build_id,
            semantic_build_id=semantic_result.build.build_id,
        ),
        rank_constant=rank_constant,
        rank_window_size=rank_window_size,
        lexical_build=lexical_result.build,
        semantic_build=semantic_result.build,
    )
    result = resolved_formatter.format_hybrid_results(
        repository=lexical_result.repository,
        snapshot=lexical_result.snapshot,
        build=build,
        query_text=query_text,
        diagnostics=diagnostics,
        matches=final_results,
    )
    return HybridQueryComposition(
        result=result,
        fused_results=tuple(all_fused_results),
    )


def _validate_component_alignment(
    *,
    lexical_result: RunLexicalQueryResult,
    semantic_result: RunSemanticQueryResult,
) -> None:
    lexical_snapshot = lexical_result.snapshot
    semantic_snapshot = semantic_result.snapshot
    if (
        lexical_result.repository.repository_id != semantic_result.repository.repository_id
        or lexical_snapshot.snapshot_id != semantic_snapshot.snapshot_id
        or lexical_snapshot.revision_identity != semantic_snapshot.revision_identity
        or lexical_snapshot.revision_source != semantic_snapshot.revision_source
    ):
        raise HybridSnapshotMismatchError(
            "Hybrid query cannot fuse lexical and semantic results from different "
            "repository snapshots.",
            details={
                "lexical_snapshot_id": lexical_snapshot.snapshot_id,
                "semantic_snapshot_id": semantic_snapshot.snapshot_id,
                "lexical_revision_identity": lexical_snapshot.revision_identity,
                "semantic_revision_identity": semantic_snapshot.revision_identity,
                "lexical_build_id": lexical_result.build.build_id,
                "semantic_build_id": semantic_result.build.build_id,
            },
        )


def _build_diagnostics(
    *,
    lexical_result: RunLexicalQueryResult,
    semantic_result: RunSemanticQueryResult,
    fused_results: list[FusedHybridResult],
    total_fused_results: int,
    latency_ms: int,
    rank_window_size: int,
    rank_constant: int,
) -> HybridQueryDiagnostics:
    lexical_contribution_count = sum(
        1 for result in fused_results if result.lexical_rank is not None
    )
    semantic_contribution_count = sum(
        1 for result in fused_results if result.semantic_rank is not None
    )
    component_truncated = (
        lexical_result.diagnostics.truncated or semantic_result.diagnostics.truncated
    )
    total_match_count = total_fused_results
    if component_truncated:
        total_match_count = max(
            total_fused_results,
            lexical_result.diagnostics.total_match_count,
            semantic_result.diagnostics.total_match_count,
        )
    return HybridQueryDiagnostics(
        match_count=len(fused_results),
        total_match_count=total_match_count,
        truncated=component_truncated or total_fused_results > len(fused_results),
        query_latency_ms=latency_ms,
        rank_constant=rank_constant,
        rank_window_size=rank_window_size,
        total_match_count_is_lower_bound=component_truncated,
        lexical=HybridComponentQueryDiagnostics(
            match_count=lexical_result.diagnostics.match_count,
            total_match_count=lexical_result.diagnostics.total_match_count,
            truncated=lexical_result.diagnostics.truncated,
            query_latency_ms=lexical_result.diagnostics.query_latency_ms,
            contributed_result_count=lexical_contribution_count,
        ),
        semantic=HybridComponentQueryDiagnostics(
            match_count=semantic_result.diagnostics.match_count,
            total_match_count=semantic_result.diagnostics.total_match_count,
            truncated=semantic_result.diagnostics.truncated,
            query_latency_ms=semantic_result.diagnostics.query_latency_ms,
            contributed_result_count=semantic_contribution_count,
        ),
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

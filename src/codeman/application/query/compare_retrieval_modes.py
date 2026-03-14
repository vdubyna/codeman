"""Compare lexical, semantic, and hybrid retrieval results for the same query."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from codeman.application.query.format_results import RetrievalResultFormatter
from codeman.application.query.hybrid_fusion import FusedHybridResult
from codeman.application.query.run_hybrid_query import (
    DEFAULT_HYBRID_CANDIDATE_WINDOW,
    DEFAULT_HYBRID_RANK_CONSTANT,
    HybridSnapshotMismatchError,
    compose_hybrid_result_from_components,
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
from codeman.contracts.errors import ErrorCode
from codeman.contracts.retrieval import (
    CompareRetrievalModesDiagnostics,
    CompareRetrievalModesRequest,
    CompareRetrievalModesResult,
    RetrievalModeComparisonEntry,
    RetrievalModeRankAlignment,
    RunLexicalQueryRequest,
    RunLexicalQueryResult,
    RunSemanticQueryRequest,
    RunSemanticQueryResult,
)

__all__ = [
    "CompareRetrievalModesBaselineMissingError",
    "CompareRetrievalModesError",
    "CompareRetrievalModesModeUnavailableError",
    "CompareRetrievalModesRepositoryNotRegisteredError",
    "CompareRetrievalModesSnapshotMismatchError",
    "CompareRetrievalModesUseCase",
]


class CompareRetrievalModesError(Exception):
    """Base exception for retrieval-mode comparison failures."""

    exit_code = 51
    error_code = ErrorCode.COMPARE_RETRIEVAL_MODES_FAILED

    def __init__(
        self,
        message: str,
        *,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class CompareRetrievalModesRepositoryNotRegisteredError(CompareRetrievalModesError):
    """Raised when comparing results for an unknown repository."""

    exit_code = 24
    error_code = ErrorCode.REPOSITORY_NOT_REGISTERED


class CompareRetrievalModesBaselineMissingError(CompareRetrievalModesError):
    """Raised when one required retrieval baseline is unavailable."""

    exit_code = 52
    error_code = ErrorCode.COMPARE_RETRIEVAL_MODE_BASELINE_MISSING


class CompareRetrievalModesModeUnavailableError(CompareRetrievalModesError):
    """Raised when one compared retrieval mode cannot be executed truthfully."""

    exit_code = 53
    error_code = ErrorCode.COMPARE_RETRIEVAL_MODE_UNAVAILABLE


class CompareRetrievalModesSnapshotMismatchError(CompareRetrievalModesError):
    """Raised when compared modes resolve different repository snapshots."""

    exit_code = 54
    error_code = ErrorCode.COMPARE_RETRIEVAL_MODE_SNAPSHOT_MISMATCH


@dataclass(slots=True)
class CompareRetrievalModesUseCase:
    """Compose lexical, semantic, and hybrid retrieval into one comparable package."""

    run_lexical_query: RunLexicalQueryUseCase
    run_semantic_query: RunSemanticQueryUseCase
    formatter: RetrievalResultFormatter = field(default_factory=RetrievalResultFormatter)
    candidate_window_size: int = DEFAULT_HYBRID_CANDIDATE_WINDOW
    rank_constant: int = DEFAULT_HYBRID_RANK_CONSTANT

    def execute(self, request: CompareRetrievalModesRequest) -> CompareRetrievalModesResult:
        """Compare the current lexical, semantic, and hybrid results for one query."""

        started_at = perf_counter()
        candidate_window = max(request.max_results, self.candidate_window_size)
        lexical_result = self._run_lexical(request, candidate_window=candidate_window)
        semantic_result = self._run_semantic(request, candidate_window=candidate_window)

        try:
            hybrid_composition = compose_hybrid_result_from_components(
                formatter=self.formatter,
                lexical_result=lexical_result,
                semantic_result=semantic_result,
                query_text=request.query_text,
                max_results=request.max_results,
                rank_window_size=candidate_window,
                rank_constant=self.rank_constant,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )
        except HybridSnapshotMismatchError as exc:
            raise CompareRetrievalModesSnapshotMismatchError(
                "Comparison cannot run because the compared retrieval modes resolved "
                "different repository snapshots.",
                details=exc.details,
            ) from exc

        lexical_entry_result = self._limit_result_package(
            result=lexical_result,
            max_results=request.max_results,
        )
        semantic_entry_result = self._limit_result_package(
            result=semantic_result,
            max_results=request.max_results,
        )
        hybrid_result = hybrid_composition.result
        alignment = self._build_alignment(
            lexical_result=lexical_result,
            semantic_result=semantic_result,
            hybrid_result=hybrid_result,
            hybrid_fused_results=hybrid_composition.fused_results,
            lexical_entry_result=lexical_entry_result,
            semantic_entry_result=semantic_entry_result,
        )
        overlap_count = sum(
            1
            for entry in alignment
            if sum(
                rank is not None
                for rank in (entry.lexical_rank, entry.semantic_rank, entry.hybrid_rank)
            )
            >= 2
        )
        return CompareRetrievalModesResult(
            query=hybrid_result.query,
            repository=hybrid_result.repository,
            snapshot=hybrid_result.snapshot,
            entries=[
                self._build_entry(lexical_entry_result),
                self._build_entry(semantic_entry_result),
                self._build_entry(hybrid_result),
            ],
            alignment=alignment,
            diagnostics=CompareRetrievalModesDiagnostics(
                alignment_count=len(alignment),
                overlap_count=overlap_count,
                query_latency_ms=int((perf_counter() - started_at) * 1000),
            ),
        )

    def _run_lexical(
        self,
        request: CompareRetrievalModesRequest,
        *,
        candidate_window: int,
    ) -> RunLexicalQueryResult:
        try:
            return self.run_lexical_query.execute(
                RunLexicalQueryRequest(
                    repository_id=request.repository_id,
                    query_text=request.query_text,
                    max_results=candidate_window,
                )
            )
        except LexicalQueryRepositoryNotRegisteredError as exc:
            raise CompareRetrievalModesRepositoryNotRegisteredError(exc.message) from exc
        except LexicalBuildBaselineMissingError as exc:
            raise CompareRetrievalModesBaselineMissingError(
                "Comparison cannot run because the lexical retrieval baseline is unavailable.",
                details=self._mode_details(mode="lexical", error=exc),
            ) from exc
        except LexicalQueryError as exc:
            raise CompareRetrievalModesModeUnavailableError(
                "Comparison cannot run because the lexical retrieval mode is unavailable: "
                f"{exc.message}",
                details=self._mode_details(mode="lexical", error=exc),
            ) from exc

    def _run_semantic(
        self,
        request: CompareRetrievalModesRequest,
        *,
        candidate_window: int,
    ) -> RunSemanticQueryResult:
        try:
            return self.run_semantic_query.execute(
                RunSemanticQueryRequest(
                    repository_id=request.repository_id,
                    query_text=request.query_text,
                    max_results=candidate_window,
                )
            )
        except SemanticQueryRepositoryNotRegisteredError as exc:
            raise CompareRetrievalModesRepositoryNotRegisteredError(exc.message) from exc
        except SemanticBuildBaselineMissingError as exc:
            raise CompareRetrievalModesBaselineMissingError(
                "Comparison cannot run because the semantic retrieval baseline is unavailable.",
                details=self._mode_details(mode="semantic", error=exc),
            ) from exc
        except SemanticQueryError as exc:
            raise CompareRetrievalModesModeUnavailableError(
                "Comparison cannot run because the semantic retrieval mode is unavailable: "
                f"{exc.message}",
                details=self._mode_details(mode="semantic", error=exc),
            ) from exc

    @staticmethod
    def _limit_result_package(
        *,
        result: RunLexicalQueryResult | RunSemanticQueryResult,
        max_results: int,
    ) -> RunLexicalQueryResult | RunSemanticQueryResult:
        trimmed_results = list(result.results[:max_results])
        diagnostics = result.diagnostics.model_copy(
            update={
                "match_count": len(trimmed_results),
                "truncated": (
                    result.diagnostics.truncated
                    or len(result.results) > len(trimmed_results)
                    or result.diagnostics.total_match_count > len(trimmed_results)
                ),
            }
        )
        return result.model_copy(
            update={
                "results": trimmed_results,
                "diagnostics": diagnostics,
            }
        )

    @staticmethod
    def _build_entry(
        result: RunLexicalQueryResult | RunSemanticQueryResult | Any,
    ) -> RetrievalModeComparisonEntry:
        return RetrievalModeComparisonEntry(
            retrieval_mode=result.retrieval_mode,
            build=result.build,
            diagnostics=result.diagnostics,
            results=list(result.results),
        )

    def _build_alignment(
        self,
        *,
        lexical_result: RunLexicalQueryResult,
        semantic_result: RunSemanticQueryResult,
        hybrid_result: Any,
        hybrid_fused_results: tuple[FusedHybridResult, ...],
        lexical_entry_result: RunLexicalQueryResult,
        semantic_entry_result: RunSemanticQueryResult,
    ) -> list[RetrievalModeRankAlignment]:
        lexical_items = {item.chunk_id: item for item in lexical_result.results}
        semantic_items = {item.chunk_id: item for item in semantic_result.results}
        hybrid_items = {item.chunk_id: item for item in hybrid_result.results}
        hybrid_alignment_items = {
            fused_result.chunk_id: (index, fused_result)
            for index, fused_result in enumerate(hybrid_fused_results, start=1)
        }

        chunk_ids = {
            item.chunk_id
            for item in lexical_entry_result.results
            + semantic_entry_result.results
            + hybrid_result.results
        }

        alignment: list[RetrievalModeRankAlignment] = []
        for chunk_id in chunk_ids:
            canonical_item = (
                hybrid_items.get(chunk_id)
                or lexical_items.get(chunk_id)
                or semantic_items.get(chunk_id)
            )
            if canonical_item is None:
                continue

            lexical_item = lexical_items.get(chunk_id)
            semantic_item = semantic_items.get(chunk_id)
            hybrid_alignment = hybrid_alignment_items.get(chunk_id)
            alignment.append(
                RetrievalModeRankAlignment(
                    chunk_id=chunk_id,
                    relative_path=canonical_item.relative_path,
                    language=canonical_item.language,
                    strategy=canonical_item.strategy,
                    lexical_rank=lexical_item.rank if lexical_item is not None else None,
                    semantic_rank=semantic_item.rank if semantic_item is not None else None,
                    hybrid_rank=hybrid_alignment[0] if hybrid_alignment is not None else None,
                    lexical_score=lexical_item.score if lexical_item is not None else None,
                    semantic_score=semantic_item.score if semantic_item is not None else None,
                    hybrid_score=(
                        hybrid_alignment[1].fused_score if hybrid_alignment is not None else None
                    ),
                )
            )

        alignment.sort(
            key=lambda entry: (
                self._rank_sort_value(entry.hybrid_rank),
                self._rank_sort_value(entry.lexical_rank),
                self._rank_sort_value(entry.semantic_rank),
                entry.relative_path,
                entry.chunk_id,
            )
        )
        return alignment

    @staticmethod
    def _rank_sort_value(rank: int | None) -> int:
        return rank if rank is not None else 10_000

    @staticmethod
    def _mode_details(
        *,
        mode: str,
        error: LexicalQueryError | SemanticQueryError,
    ) -> dict[str, Any]:
        details: dict[str, Any] = {
            "mode": mode,
            "mode_error_code": error.error_code,
        }
        mode_details = getattr(error, "details", None)
        if mode_details is not None:
            details["mode_details"] = mode_details
        return details

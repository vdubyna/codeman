"""Deterministic rank fusion for hybrid retrieval results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from codeman.contracts.retrieval import RetrievalResultItem

DEFAULT_HYBRID_RANK_CONSTANT = 60

SourceMode = Literal["lexical", "semantic"]


@dataclass(slots=True, frozen=True)
class FusedHybridResult:
    """One fused hybrid result with attributable component participation."""

    item: RetrievalResultItem
    fused_score: float
    lexical_rank: int | None
    semantic_rank: int | None

    @property
    def chunk_id(self) -> str:
        return self.item.chunk_id

    @property
    def source_modes(self) -> tuple[SourceMode, ...]:
        modes: list[SourceMode] = []
        if self.lexical_rank is not None:
            modes.append("lexical")
        if self.semantic_rank is not None:
            modes.append("semantic")
        return tuple(modes)


@dataclass(slots=True)
class _MutableFusedHybridResult:
    item: RetrievalResultItem
    fused_score: float = 0.0
    lexical_rank: int | None = None
    semantic_rank: int | None = None

    def freeze(self) -> FusedHybridResult:
        return FusedHybridResult(
            item=self.item,
            fused_score=self.fused_score,
            lexical_rank=self.lexical_rank,
            semantic_rank=self.semantic_rank,
        )


def fuse_hybrid_results(
    *,
    lexical_results: Sequence[RetrievalResultItem],
    semantic_results: Sequence[RetrievalResultItem],
    max_results: int,
    rank_window_size: int = 50,
    rank_constant: int = DEFAULT_HYBRID_RANK_CONSTANT,
) -> list[FusedHybridResult]:
    """Fuse lexical and semantic ranked results with reciprocal rank fusion."""

    if max_results <= 0:
        return []

    fused_by_chunk_id: dict[str, _MutableFusedHybridResult] = {}
    _add_mode_results(
        fused_by_chunk_id=fused_by_chunk_id,
        mode="lexical",
        results=lexical_results[:rank_window_size],
        rank_constant=rank_constant,
    )
    _add_mode_results(
        fused_by_chunk_id=fused_by_chunk_id,
        mode="semantic",
        results=semantic_results[:rank_window_size],
        rank_constant=rank_constant,
    )

    fused = [candidate.freeze() for candidate in fused_by_chunk_id.values()]
    fused.sort(
        key=lambda candidate: (
            -candidate.fused_score,
            _best_rank(candidate),
            candidate.item.relative_path,
            candidate.item.start_line,
            candidate.item.start_byte,
            candidate.item.chunk_id,
        ),
    )
    return fused[:max_results]


def _add_mode_results(
    *,
    fused_by_chunk_id: dict[str, _MutableFusedHybridResult],
    mode: SourceMode,
    results: Sequence[RetrievalResultItem],
    rank_constant: int,
) -> None:
    for item in results:
        fused = fused_by_chunk_id.get(item.chunk_id)
        if fused is None:
            fused = _MutableFusedHybridResult(item=item)
            fused_by_chunk_id[item.chunk_id] = fused

        fused.fused_score += 1.0 / (rank_constant + item.rank)
        if mode == "lexical":
            fused.lexical_rank = item.rank
        else:
            fused.semantic_rank = item.rank


def _best_rank(candidate: FusedHybridResult) -> int:
    ranks = [rank for rank in (candidate.lexical_rank, candidate.semantic_rank) if rank is not None]
    return min(ranks) if ranks else 0

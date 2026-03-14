from __future__ import annotations

from codeman.application.query.hybrid_fusion import (
    DEFAULT_HYBRID_RANK_CONSTANT,
    fuse_hybrid_results,
)
from codeman.contracts.retrieval import RetrievalResultItem


def build_result_item(
    *,
    chunk_id: str,
    relative_path: str,
    rank: int,
    score: float,
) -> RetrievalResultItem:
    return RetrievalResultItem(
        chunk_id=chunk_id,
        relative_path=relative_path,
        language="php",
        strategy="php_structure",
        rank=rank,
        score=score,
        start_line=1,
        end_line=5,
        start_byte=0,
        end_byte=50,
        content_preview=f"preview for {chunk_id}",
        explanation=f"base explanation for {chunk_id}",
    )


def test_fuse_hybrid_results_merges_duplicate_chunks_and_tracks_sources() -> None:
    lexical_results = [
        build_result_item(
            chunk_id="chunk-shared",
            relative_path="src/Controller/HomeController.php",
            rank=1,
            score=-1.0,
        ),
        build_result_item(
            chunk_id="chunk-lexical",
            relative_path="assets/app.js",
            rank=2,
            score=-0.5,
        ),
    ]
    semantic_results = [
        build_result_item(
            chunk_id="chunk-shared",
            relative_path="src/Controller/HomeController.php",
            rank=3,
            score=0.85,
        ),
        build_result_item(
            chunk_id="chunk-semantic",
            relative_path="templates/home.html.twig",
            rank=1,
            score=0.8,
        ),
    ]

    fused = fuse_hybrid_results(
        lexical_results=lexical_results,
        semantic_results=semantic_results,
        max_results=10,
    )

    assert [item.chunk_id for item in fused] == [
        "chunk-shared",
        "chunk-semantic",
        "chunk-lexical",
    ]
    assert fused[0].lexical_rank == 1
    assert fused[0].semantic_rank == 3
    assert fused[0].source_modes == ("lexical", "semantic")
    expected_shared_score = 1 / (DEFAULT_HYBRID_RANK_CONSTANT + 1) + 1 / (
        DEFAULT_HYBRID_RANK_CONSTANT + 3
    )
    assert fused[0].fused_score == expected_shared_score


def test_fuse_hybrid_results_uses_deterministic_tiebreakers() -> None:
    lexical_results = [
        build_result_item(
            chunk_id="chunk-b",
            relative_path="src/Beta.php",
            rank=1,
            score=-1.0,
        ),
        build_result_item(
            chunk_id="chunk-a",
            relative_path="src/Alpha.php",
            rank=2,
            score=-0.5,
        ),
    ]
    semantic_results = [
        build_result_item(
            chunk_id="chunk-a",
            relative_path="src/Alpha.php",
            rank=1,
            score=0.9,
        ),
        build_result_item(
            chunk_id="chunk-b",
            relative_path="src/Beta.php",
            rank=2,
            score=0.8,
        ),
    ]

    fused = fuse_hybrid_results(
        lexical_results=lexical_results,
        semantic_results=semantic_results,
        max_results=10,
    )

    assert [item.chunk_id for item in fused] == ["chunk-a", "chunk-b"]
    assert fused[0].fused_score == fused[1].fused_score


def test_fuse_hybrid_results_respects_rank_window_and_one_path_empty_case() -> None:
    lexical_results = []
    semantic_results = [
        build_result_item(
            chunk_id=f"chunk-{index}",
            relative_path=f"src/Chunk{index}.php",
            rank=index,
            score=1.0 / index,
        )
        for index in range(1, 6)
    ]

    fused = fuse_hybrid_results(
        lexical_results=lexical_results,
        semantic_results=semantic_results,
        max_results=2,
        rank_window_size=3,
    )

    assert [item.chunk_id for item in fused] == ["chunk-1", "chunk-2"]
    assert all(item.lexical_rank is None for item in fused)
    assert all(item.semantic_rank is not None for item in fused)

from __future__ import annotations

import pytest

from codeman.contracts.evaluation import (
    BenchmarkCaseExecutionArtifact,
    BenchmarkQuerySourceKind,
    BenchmarkRelevanceJudgment,
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
from codeman.domain.evaluation.metrics import (
    BenchmarkMetricsInputShapeError,
    aggregate_benchmark_metrics,
    calculate_benchmark_case_metrics,
    summarize_query_latencies,
)


def build_case(
    *,
    judgments: list[BenchmarkRelevanceJudgment],
    results: list[RetrievalResultItem],
) -> BenchmarkCaseExecutionArtifact:
    return BenchmarkCaseExecutionArtifact(
        query_id="case-1",
        source_kind=BenchmarkQuerySourceKind.HUMAN_AUTHORED,
        judgments=judgments,
        result=RunLexicalQueryResult(
            repository=RetrievalRepositoryContext(
                repository_id="repo-123",
                repository_name="registered-repo",
            ),
            snapshot=RetrievalSnapshotContext(
                snapshot_id="snapshot-123",
                revision_identity="revision-abc",
                revision_source="filesystem_fingerprint",
            ),
            build=LexicalRetrievalBuildContext(
                build_id="lexical-build-123",
                indexing_config_fingerprint="index-fingerprint-123",
                lexical_engine="sqlite-fts5",
                tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
                indexed_fields=["content", "relative_path"],
            ),
            query=RetrievalQueryMetadata(text="home controller"),
            results=results,
            diagnostics=RetrievalQueryDiagnostics(
                match_count=len(results),
                total_match_count=len(results),
                truncated=False,
                query_latency_ms=7,
            ),
        ),
    )


def build_result(
    *,
    rank: int,
    relative_path: str = "src/Controller/HomeController.php",
    language: str = "php",
    start_line: int = 10,
    end_line: int = 12,
) -> RetrievalResultItem:
    return RetrievalResultItem(
        chunk_id=f"chunk-{rank}",
        relative_path=relative_path,
        language=language,
        strategy="php_structure",
        rank=rank,
        score=1.0 / rank,
        start_line=start_line,
        end_line=end_line,
        start_byte=0,
        end_byte=42,
        content_preview="final class HomeController {}",
        explanation="fixture",
    )


def test_calculate_benchmark_case_metrics_matches_by_path_line_overlap_and_language() -> None:
    case = build_case(
        judgments=[
            BenchmarkRelevanceJudgment(
                relative_path="src/Controller/HomeController.php",
                language="php",
                start_line=11,
                end_line=14,
                relevance_grade=2,
            ),
            BenchmarkRelevanceJudgment(
                relative_path="src/Controller/HomeController.php",
                language="javascript",
                relevance_grade=1,
            ),
        ],
        results=[build_result(rank=1, start_line=10, end_line=12)],
    )

    metrics = calculate_benchmark_case_metrics(case, k=5)

    assert metrics.matched_judgment_count == 1
    assert metrics.first_relevant_rank == 1
    assert metrics.recall_at_k == 0.5
    assert metrics.reciprocal_rank == 1.0
    assert metrics.judgments[0].matched_result_ranks == [1]
    assert metrics.judgments[1].matched_result_ranks == []


def test_calculate_benchmark_case_metrics_does_not_inflate_duplicate_result_hits() -> None:
    case = build_case(
        judgments=[
            BenchmarkRelevanceJudgment(
                relative_path="src/Controller/HomeController.php",
                language="php",
                relevance_grade=3,
            )
        ],
        results=[build_result(rank=1), build_result(rank=2)],
    )

    metrics = calculate_benchmark_case_metrics(case, k=5)

    assert metrics.matched_judgment_count == 1
    assert metrics.recall_at_k == 1.0
    assert metrics.reciprocal_rank == 1.0
    assert metrics.ndcg_at_k == 1.0
    assert metrics.judgments[0].matched_result_ranks == [1, 2]
    assert metrics.judgments[0].gain_rank == 1


def test_calculate_benchmark_case_metrics_returns_zero_scores_for_no_hits() -> None:
    case = build_case(
        judgments=[
            BenchmarkRelevanceJudgment(
                relative_path="src/Controller/HomeController.php",
                language="php",
                relevance_grade=2,
            )
        ],
        results=[build_result(rank=1, relative_path="src/OtherController.php")],
    )

    metrics = calculate_benchmark_case_metrics(case, k=5)

    assert metrics.matched_judgment_count == 0
    assert metrics.recall_at_k == 0.0
    assert metrics.reciprocal_rank == 0.0
    assert metrics.ndcg_at_k == 0.0


def test_calculate_benchmark_case_metrics_uses_graded_ndcg_and_k_truncation() -> None:
    case = build_case(
        judgments=[
            BenchmarkRelevanceJudgment(
                relative_path="src/Controller/HomeController.php",
                language="php",
                relevance_grade=3,
            ),
            BenchmarkRelevanceJudgment(
                relative_path="src/Controller/SettingsController.php",
                language="php",
                relevance_grade=1,
            ),
        ],
        results=[
            build_result(
                rank=1,
                relative_path="src/Controller/SettingsController.php",
            ),
            build_result(rank=2),
        ],
    )

    metrics = calculate_benchmark_case_metrics(case, k=2)

    assert metrics.recall_at_k == 1.0
    assert metrics.reciprocal_rank == 1.0
    assert metrics.ndcg_at_k == pytest.approx(0.7098, rel=1e-4)


def test_calculate_benchmark_case_metrics_rejects_non_sequential_ranks() -> None:
    case = build_case(
        judgments=[
            BenchmarkRelevanceJudgment(
                relative_path="src/Controller/HomeController.php",
                relevance_grade=2,
            )
        ],
        results=[build_result(rank=2)],
    )

    with pytest.raises(BenchmarkMetricsInputShapeError):
        calculate_benchmark_case_metrics(case, k=5)


def test_aggregate_benchmark_metrics_and_latency_summary_are_deterministic() -> None:
    hit_metrics = calculate_benchmark_case_metrics(
        build_case(
            judgments=[
                BenchmarkRelevanceJudgment(
                    relative_path="src/Controller/HomeController.php",
                    relevance_grade=2,
                )
            ],
            results=[build_result(rank=1)],
        ),
        k=5,
    )
    miss_metrics = calculate_benchmark_case_metrics(
        build_case(
            judgments=[
                BenchmarkRelevanceJudgment(
                    relative_path="src/Controller/HomeController.php",
                    relevance_grade=2,
                )
            ],
            results=[build_result(rank=1, relative_path="src/Miss.php")],
        ),
        k=5,
    )

    aggregate = aggregate_benchmark_metrics([hit_metrics, miss_metrics])
    latency = summarize_query_latencies([5, 7, 9, 11])

    assert aggregate.recall_at_k == 0.5
    assert aggregate.mrr == 0.5
    assert aggregate.ndcg_at_k == 0.5
    assert latency.mean_ms == 8.0
    assert latency.median_ms == 8.0
    assert latency.p95_ms == 11

"""Pure benchmark-metrics calculation policies."""

from __future__ import annotations

from math import ceil, log2
from statistics import median

from codeman.contracts.evaluation import (
    BenchmarkAggregateMetrics,
    BenchmarkCaseExecutionArtifact,
    BenchmarkCaseMetricResult,
    BenchmarkJudgmentMetricResult,
    BenchmarkQueryLatencySummary,
    BenchmarkRelevanceJudgment,
)
from codeman.contracts.retrieval import RetrievalResultItem

__all__ = [
    "BenchmarkMetricsInputShapeError",
    "aggregate_benchmark_metrics",
    "calculate_benchmark_case_metrics",
    "summarize_query_latencies",
]


class BenchmarkMetricsInputShapeError(ValueError):
    """Raised when persisted benchmark inputs cannot be evaluated deterministically."""


def calculate_benchmark_case_metrics(
    case: BenchmarkCaseExecutionArtifact,
    *,
    k: int,
) -> BenchmarkCaseMetricResult:
    """Calculate one case's retrieval metrics from the persisted ranking window."""

    ranked_results = _validated_ranked_results(case.result.results, k=k)
    judgments = list(case.judgments)
    matched_ranks_by_judgment = {index: [] for index in range(len(judgments))}
    gain_rank_by_judgment: dict[int, int] = {}
    recall_matched_judgments: set[int] = set()
    available_gain_judgments = set(range(len(judgments)))
    ranked_gains: list[int] = []
    first_relevant_rank: int | None = None

    for result in ranked_results:
        matching_judgment_indexes = [
            index
            for index, judgment in enumerate(judgments)
            if _result_matches_judgment(result=result, judgment=judgment)
        ]
        if matching_judgment_indexes and first_relevant_rank is None:
            first_relevant_rank = result.rank

        for judgment_index in matching_judgment_indexes:
            matched_ranks_by_judgment[judgment_index].append(result.rank)
        recall_matched_judgments.update(matching_judgment_indexes)

        gain_judgment_candidates = [
            judgment_index
            for judgment_index in matching_judgment_indexes
            if judgment_index in available_gain_judgments
        ]
        if not gain_judgment_candidates:
            ranked_gains.append(0)
            continue

        selected_judgment_index = max(
            gain_judgment_candidates,
            key=lambda judgment_index: (
                judgments[judgment_index].relevance_grade,
                -judgment_index,
            ),
        )
        available_gain_judgments.remove(selected_judgment_index)
        gain_rank_by_judgment[selected_judgment_index] = result.rank
        ranked_gains.append(judgments[selected_judgment_index].relevance_grade)

    relevant_judgment_count = len(judgments)
    recall_at_k = (
        len(recall_matched_judgments) / relevant_judgment_count if relevant_judgment_count else 0.0
    )
    reciprocal_rank = 0.0 if first_relevant_rank is None else 1.0 / first_relevant_rank
    ndcg_at_k = _normalized_discounted_cumulative_gain(ranked_gains, judgments=judgments, k=k)

    return BenchmarkCaseMetricResult(
        query_id=case.query_id,
        source_kind=case.source_kind,
        evaluated_at_k=k,
        relevant_judgment_count=relevant_judgment_count,
        matched_judgment_count=len(recall_matched_judgments),
        first_relevant_rank=first_relevant_rank,
        recall_at_k=recall_at_k,
        reciprocal_rank=reciprocal_rank,
        ndcg_at_k=ndcg_at_k,
        query_latency_ms=case.result.diagnostics.query_latency_ms,
        judgments=[
            BenchmarkJudgmentMetricResult(
                judgment_index=index,
                relative_path=judgment.relative_path,
                language=judgment.language,
                start_line=judgment.start_line,
                end_line=judgment.end_line,
                relevance_grade=judgment.relevance_grade,
                matched_result_ranks=list(matched_ranks_by_judgment[index]),
                first_matched_rank=(
                    matched_ranks_by_judgment[index][0]
                    if matched_ranks_by_judgment[index]
                    else None
                ),
                gain_rank=gain_rank_by_judgment.get(index),
            )
            for index, judgment in enumerate(judgments)
        ],
    )


def aggregate_benchmark_metrics(
    case_metrics: list[BenchmarkCaseMetricResult],
) -> BenchmarkAggregateMetrics:
    """Aggregate benchmark metrics across evaluated benchmark cases."""

    if not case_metrics:
        return BenchmarkAggregateMetrics(
            recall_at_k=0.0,
            mrr=0.0,
            ndcg_at_k=0.0,
        )

    case_count = len(case_metrics)
    return BenchmarkAggregateMetrics(
        recall_at_k=sum(case.recall_at_k for case in case_metrics) / case_count,
        mrr=sum(case.reciprocal_rank for case in case_metrics) / case_count,
        ndcg_at_k=sum(case.ndcg_at_k for case in case_metrics) / case_count,
    )


def summarize_query_latencies(latencies_ms: list[int]) -> BenchmarkQueryLatencySummary:
    """Summarize query latencies from persisted per-case diagnostics."""

    if not latencies_ms:
        return BenchmarkQueryLatencySummary(sample_count=0)

    ordered_latencies = sorted(latencies_ms)
    sample_count = len(ordered_latencies)
    p95_index = max(0, ceil(sample_count * 0.95) - 1)
    return BenchmarkQueryLatencySummary(
        sample_count=sample_count,
        min_ms=ordered_latencies[0],
        mean_ms=sum(ordered_latencies) / sample_count,
        median_ms=float(median(ordered_latencies)),
        p95_ms=ordered_latencies[p95_index],
        max_ms=ordered_latencies[-1],
    )


def _validated_ranked_results(
    results: list[RetrievalResultItem],
    *,
    k: int,
) -> list[RetrievalResultItem]:
    ordered_results = sorted(results, key=lambda result: result.rank)
    limited_results = ordered_results[:k]
    for expected_rank, result in enumerate(limited_results, start=1):
        if result.rank != expected_rank:
            raise BenchmarkMetricsInputShapeError(
                "Benchmark metrics require sequential result ranks starting at 1."
            )
    return limited_results


def _result_matches_judgment(
    *,
    result: RetrievalResultItem,
    judgment: BenchmarkRelevanceJudgment,
) -> bool:
    if result.relative_path != judgment.relative_path:
        return False
    if judgment.language is not None and result.language != judgment.language:
        return False
    if judgment.start_line is None or judgment.end_line is None:
        return True
    return not (
        result.end_line < judgment.start_line or result.start_line > judgment.end_line
    )


def _normalized_discounted_cumulative_gain(
    ranked_gains: list[int],
    *,
    judgments: list[BenchmarkRelevanceJudgment],
    k: int,
) -> float:
    actual_dcg = _discounted_cumulative_gain(ranked_gains[:k])
    ideal_gains = sorted(
        (judgment.relevance_grade for judgment in judgments),
        reverse=True,
    )[:k]
    ideal_dcg = _discounted_cumulative_gain(ideal_gains)
    if ideal_dcg == 0.0:
        return 0.0
    return actual_dcg / ideal_dcg


def _discounted_cumulative_gain(gains: list[int]) -> float:
    return sum(
        ((2**gain) - 1) / log2(position + 1)
        for position, gain in enumerate(gains, start=1)
        if gain > 0
    )

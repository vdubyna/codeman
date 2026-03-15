"""Comparison commands."""

from __future__ import annotations

from typing import Any

import typer
from pydantic import ValidationError

from codeman.application.evaluation.compare_runs import CompareBenchmarkRunsError
from codeman.application.query.compare_retrieval_modes import CompareRetrievalModesError
from codeman.bootstrap import BootstrapContainer
from codeman.cli.common import (
    OutputFormat,
    build_command_meta,
    build_retrieval_summary_line,
    emit_failure_response,
    emit_json_response,
    render_retrieval_result_blocks,
    resolve_query_text,
)
from codeman.contracts.common import SuccessEnvelope
from codeman.contracts.errors import ErrorCode
from codeman.contracts.evaluation import (
    BenchmarkMetricComparison,
    BenchmarkRunComparisonEntry,
    CompareBenchmarkRunsRequest,
    CompareBenchmarkRunsResult,
)
from codeman.contracts.retrieval import (
    CompareRetrievalModesRequest,
    CompareRetrievalModesResult,
    RetrievalModeComparisonEntry,
    RetrievalModeRankAlignment,
)

app = typer.Typer(help="Experiment comparison commands.", no_args_is_help=True)

ALIGNMENT_TEXT_LIMIT = 10


@app.callback()
def compare_group() -> None:
    """Compare experiment outputs."""


def _entry_title(entry: RetrievalModeComparisonEntry) -> str:
    return f"{entry.retrieval_mode.capitalize()} Results:"


def _entry_summary(entry: RetrievalModeComparisonEntry) -> str:
    return build_retrieval_summary_line(
        result_count=entry.diagnostics.match_count,
        total_count=entry.diagnostics.total_match_count,
        truncated=entry.diagnostics.truncated,
        label=f"{entry.retrieval_mode.capitalize()} retrieval",
    )


def _format_alignment_rank(value: int | None) -> str:
    return "-" if value is None else str(value)


def _format_rank_delta(
    *,
    hybrid_rank: int | None,
    other_rank: int | None,
    label: str,
) -> str | None:
    if hybrid_rank is None or other_rank is None:
        return None
    return f"delta({label})={hybrid_rank - other_rank}"


def _render_alignment_line(index: int, entry: RetrievalModeRankAlignment) -> str:
    delta_parts = [
        value
        for value in (
            _format_rank_delta(
                hybrid_rank=entry.hybrid_rank,
                other_rank=entry.lexical_rank,
                label="h-l",
            ),
            _format_rank_delta(
                hybrid_rank=entry.hybrid_rank,
                other_rank=entry.semantic_rank,
                label="h-s",
            ),
        )
        if value is not None
    ]
    delta_suffix = f" {' '.join(delta_parts)}" if delta_parts else ""
    return (
        f"{index}. {entry.relative_path} [{entry.chunk_id}] "
        f"lexical={_format_alignment_rank(entry.lexical_rank)} "
        f"semantic={_format_alignment_rank(entry.semantic_rank)} "
        f"hybrid={_format_alignment_rank(entry.hybrid_rank)}{delta_suffix}"
    )


def _render_text_output(result: CompareRetrievalModesResult) -> str:
    lines = [
        "Retrieval mode comparison completed.",
        f"Run ID: {result.run_id}",
        f"Compared Modes: {', '.join(result.diagnostics.compared_modes)}",
        f"Repository ID: {result.repository.repository_id}",
        f"Snapshot ID: {result.snapshot.snapshot_id}",
        f"Query: {result.query.text}",
        f"Latency: {result.diagnostics.query_latency_ms} ms",
        f"Alignment Count: {result.diagnostics.alignment_count}",
        f"Overlap Count: {result.diagnostics.overlap_count}",
        "",
        "Mode Summaries:",
    ]
    lines.extend(_entry_summary(entry) for entry in result.entries)
    lines.extend(["", "Rank Alignment:"])

    alignment_slice = result.alignment[:ALIGNMENT_TEXT_LIMIT]
    if alignment_slice:
        lines.extend(
            _render_alignment_line(index, entry)
            for index, entry in enumerate(alignment_slice, start=1)
        )
    else:
        lines.append("No cross-mode overlap to report.")
    if len(result.alignment) > len(alignment_slice):
        lines.append(
            f"... {len(result.alignment) - len(alignment_slice)} more alignment rows not shown"
        )

    for entry in result.entries:
        lines.extend(["", _entry_title(entry)])
        lines.append(f"Build ID: {entry.build.build_id}")
        if entry.retrieval_mode == "semantic":
            lines.append(f"Provider: {entry.build.provider_id}")
            lines.append(f"Model: {entry.build.model_id}")
            lines.append(f"Model Version: {entry.build.model_version}")
            lines.append(f"Vector Engine: {entry.build.vector_engine}")
        elif entry.retrieval_mode == "hybrid":
            lines.append(f"Fusion Strategy: {entry.build.fusion_strategy}")
            lines.append(f"Rank Constant: {entry.build.rank_constant}")
            lines.append(f"Rank Window Size: {entry.build.rank_window_size}")
        if entry.results:
            lines.extend(render_retrieval_result_blocks(entry.results))
        else:
            lines.append(f"No {entry.retrieval_mode} matches found.")

    return "\n".join(lines)


def _format_value(value: object | None) -> str:
    if value in (None, ""):
        return "-"
    return str(value)


def _format_metric_value(metric_key: str, value: float | int | None) -> str:
    if value is None:
        return "-"
    if metric_key in {"recall_at_k", "mrr", "ndcg_at_k"}:
        return f"{float(value):.4f}"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _format_model(entry: BenchmarkRunComparisonEntry) -> str:
    model_id = entry.provenance.model_id
    model_version = entry.provenance.model_version
    if model_id in (None, ""):
        return "-"
    if model_version in (None, ""):
        return str(model_id)
    return f"{model_id}@{model_version}"


def _render_benchmark_run_entry(index: int, entry: BenchmarkRunComparisonEntry) -> list[str]:
    return [
        (
            f"{index}. {entry.run.run_id} | {entry.run.retrieval_mode} | "
            f"snapshot={entry.snapshot.snapshot_id} | "
            f"dataset={entry.dataset.dataset_id}@{entry.dataset.dataset_version} | "
            f"k={entry.metrics.evaluated_at_k}"
        ),
        (
            f"   config={entry.provenance.configuration_id} "
            f"indexing={_format_value(entry.provenance.indexing_config_fingerprint)} "
            f"semantic={_format_value(entry.provenance.semantic_config_fingerprint)} "
            f"provider={_format_value(entry.provenance.provider_id)} "
            f"model={_format_model(entry)}"
        ),
    ]


def _render_metric_comparison_line(comparison: BenchmarkMetricComparison) -> str:
    direction = (
        "higher is better"
        if comparison.direction == "higher_is_better"
        else "lower is better"
    )
    values = ", ".join(
        (
            f"{value.run_id}="
            f"{_format_metric_value(comparison.metric_key, value.value)}"
        )
        for value in comparison.values
    )
    if comparison.outcome == "unavailable":
        outcome = "unavailable across all compared runs"
    elif comparison.outcome == "tie":
        outcome = (
            f"tie: {', '.join(comparison.winner_run_ids)} "
            f"({_format_metric_value(comparison.metric_key, comparison.best_value)})"
        )
    else:
        outcome = (
            f"winner: {comparison.winner_run_ids[0]} "
            f"({_format_metric_value(comparison.metric_key, comparison.best_value)})"
        )
    if comparison.outcome != "unavailable" and comparison.unavailable_run_ids:
        outcome = (
            f"{outcome}; unavailable: {', '.join(comparison.unavailable_run_ids)}"
        )
    return f"- {comparison.label} ({direction}): {outcome}; values: {values}"


def _render_benchmark_comparison_output(result: CompareBenchmarkRunsResult) -> str:
    lines = [
        "Benchmark run comparison completed.",
        f"Repository ID: {result.repository.repository_id}",
        f"Repository Name: {result.repository.repository_name}",
        f"Compared Runs: {', '.join(entry.run.run_id for entry in result.entries)}",
        (
            "Apples-to-Apples: "
            f"{'yes' if result.comparability.is_apples_to_apples else 'no'}"
        ),
        "",
        "Run Summaries:",
    ]
    for index, entry in enumerate(result.entries, start=1):
        lines.extend(_render_benchmark_run_entry(index, entry))

    lines.extend(["", "Metric Winners:"])
    lines.extend(
        _render_metric_comparison_line(comparison)
        for comparison in result.metric_comparisons
    )

    if result.comparability.notes:
        lines.extend(["", "Comparability Notes:"])
        lines.extend(f"- {note}" for note in result.comparability.notes)

    if result.comparability.differences:
        lines.extend(["", "Comparability Details:"])
        for difference in result.comparability.differences:
            values = ", ".join(
                f"{run_id}={_format_value(value)}"
                for run_id, value in difference.values_by_run_id.items()
            )
            lines.append(f"- {difference.label}: {values}")

    return "\n".join(lines)


def _validation_error_details(error: ValidationError) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for item in error.errors(include_url=False):
        normalized_item = dict(item)
        context = normalized_item.get("ctx")
        if isinstance(context, dict):
            normalized_item["ctx"] = {
                key: (
                    value
                    if isinstance(value, str | int | float | bool | type(None))
                    else str(value)
                )
                for key, value in context.items()
            }
        details.append(normalized_item)
    return details


@app.command("query-modes")
def query_modes(
    ctx: typer.Context,
    repository_id: str,
    query_text: str | None = typer.Argument(None, metavar="QUERY"),
    query: str | None = typer.Option(
        None,
        "--query",
        help="Explicit query text. Use this when the query starts with '-'.",
    ),
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--output-format"),
) -> None:
    """Compare lexical, semantic, and hybrid retrieval for the same query."""

    from codeman.cli.app import get_container

    resolved_query = resolve_query_text(query_text=query_text, query=query)

    typer.echo(
        f"Running retrieval mode comparison for repository: {repository_id}",
        err=True,
    )
    container: BootstrapContainer = get_container(ctx)
    try:
        result = container.compare_retrieval_modes.execute(
            CompareRetrievalModesRequest(
                repository_id=repository_id,
                query_text=resolved_query,
            ),
        )
    except CompareRetrievalModesError as error:
        emit_failure_response(
            error_code=error.error_code,
            message=error.message,
            details=error.details,
            exit_code=error.exit_code,
            output_format=output_format,
            command_name="compare.query_modes",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("compare.query_modes", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    typer.echo(_render_text_output(result))


@app.command("benchmark-runs")
def benchmark_runs(
    ctx: typer.Context,
    run_ids: list[str] = typer.Option(
        [],
        "--run-id",
        metavar="RUN_ID",
        help="Benchmark run id to compare. Provide at least two --run-id options.",
    ),
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--output-format"),
) -> None:
    """Compare two or more persisted benchmark runs."""

    from codeman.cli.app import get_container

    container: BootstrapContainer = get_container(ctx)
    try:
        request = CompareBenchmarkRunsRequest(run_ids=run_ids)
        typer.echo(
            f"Running benchmark comparison for runs: {', '.join(request.run_ids)}",
            err=True,
        )
        result = container.compare_benchmark_runs.execute(
            request,
            progress=lambda line: typer.echo(line, err=True),
        )
    except ValidationError as error:
        emit_failure_response(
            error_code=ErrorCode.INPUT_VALIDATION_FAILED,
            message="Benchmark comparison command input is invalid.",
            details=_validation_error_details(error),
            exit_code=2,
            output_format=output_format,
            command_name="compare.benchmark_runs",
        )
    except CompareBenchmarkRunsError as error:
        emit_failure_response(
            error_code=error.error_code,
            message=error.message,
            details=error.details,
            exit_code=error.exit_code,
            output_format=output_format,
            command_name="compare.benchmark_runs",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("compare.benchmark_runs", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    typer.echo(_render_benchmark_comparison_output(result))

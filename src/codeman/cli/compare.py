"""Comparison commands."""

from __future__ import annotations

import typer

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

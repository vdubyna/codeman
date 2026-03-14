"""Query commands."""

from __future__ import annotations

import typer

from codeman.application.query.run_hybrid_query import HybridQueryError
from codeman.application.query.run_lexical_query import LexicalQueryError
from codeman.application.query.run_semantic_query import SemanticQueryError
from codeman.bootstrap import BootstrapContainer
from codeman.cli.common import OutputFormat, build_command_meta, emit_json_response
from codeman.contracts.common import SuccessEnvelope
from codeman.contracts.errors import ErrorDetail, FailureEnvelope
from codeman.contracts.retrieval import (
    HybridComponentQueryDiagnostics,
    RunHybridQueryRequest,
    RunHybridQueryResult,
    RunLexicalQueryRequest,
    RunLexicalQueryResult,
    RunSemanticQueryRequest,
    RunSemanticQueryResult,
)

app = typer.Typer(help="Retrieval query commands.", no_args_is_help=True)


@app.callback()
def query_group() -> None:
    """Run retrieval queries."""


def _handle_query_error(
    *,
    error: LexicalQueryError | SemanticQueryError | HybridQueryError,
    output_format: OutputFormat,
    command_name: str,
) -> None:
    """Render retrieval-query failures in the requested output format."""

    envelope = FailureEnvelope(
        error=ErrorDetail(
            code=error.error_code,
            message=error.message,
            details=getattr(error, "details", None),
        ),
        meta=build_command_meta(command_name, output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
    else:
        typer.secho(error.message, err=True, fg=typer.colors.RED)

    raise typer.Exit(code=error.exit_code)


def _resolve_query_text(
    *,
    query_text: str | None,
    query: str | None,
) -> str:
    if query_text is not None and query is not None:
        typer.secho(
            "Provide either QUERY or --query, not both.",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=2)

    resolved_query = query if query is not None else query_text
    if resolved_query is None:
        typer.secho(
            "Query text is required. Provide QUERY or --query.",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=2)
    return resolved_query


def _result_blocks(
    result: RunLexicalQueryResult | RunSemanticQueryResult | RunHybridQueryResult,
) -> list[str]:
    return [
        "\n".join(
            [
                f"{item.rank}. {item.relative_path} [{item.chunk_id}]",
                (
                    f"   span: lines {item.start_line}-{item.end_line} "
                    f"bytes {item.start_byte}-{item.end_byte}"
                ),
                (f"   language/strategy: {item.language}/{item.strategy} score={item.score:.4f}"),
                f"   preview: {item.content_preview}",
                f"   explanation: {item.explanation}",
            ]
        )
        for item in result.results
    ]


def _summary_line(
    *,
    result_count: int,
    total_count: int,
    truncated: bool,
    label: str,
) -> str:
    if truncated:
        return f"{label} returned {result_count} of {total_count} results (truncated)"
    return f"{label} returned {result_count} results"


def _hybrid_component_line(
    *,
    label: str,
    diagnostics: HybridComponentQueryDiagnostics,
) -> str:
    return (
        f"{label}: matches={diagnostics.match_count} total={diagnostics.total_match_count} "
        f"latency={diagnostics.query_latency_ms} ms "
        f"contributed={diagnostics.contributed_result_count}"
    )


def _hybrid_total_count_note(result: RunHybridQueryResult) -> str | None:
    if not result.diagnostics.total_match_count_is_lower_bound:
        return None
    return (
        "Hybrid total match count is a lower bound because one or more component "
        "result windows were truncated before fusion."
    )


@app.command("lexical")
def lexical(
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
    """Run a lexical retrieval query against the current repository build."""

    from codeman.cli.app import get_container

    resolved_query = _resolve_query_text(query_text=query_text, query=query)

    typer.echo(
        f"Running lexical query for repository: {repository_id}",
        err=True,
    )
    container: BootstrapContainer = get_container(ctx)
    try:
        result = container.run_lexical_query.execute(
            RunLexicalQueryRequest(
                repository_id=repository_id,
                query_text=resolved_query,
            ),
        )
    except LexicalQueryError as error:
        _handle_query_error(
            error=error,
            output_format=output_format,
            command_name="query.lexical",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("query.lexical", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    lines = [
        _summary_line(
            result_count=result.diagnostics.match_count,
            total_count=result.diagnostics.total_match_count,
            truncated=result.diagnostics.truncated,
            label="Lexical retrieval",
        ),
        f"Retrieval Mode: {result.retrieval_mode}",
        f"Repository ID: {result.repository.repository_id}",
        f"Snapshot ID: {result.snapshot.snapshot_id}",
        f"Build ID: {result.build.build_id}",
        f"Query: {result.query.text}",
        f"Latency: {result.diagnostics.query_latency_ms} ms",
    ]
    if result.results:
        lines.extend(_result_blocks(result))
    else:
        lines.append("No lexical matches found.")
    typer.echo("\n".join(lines))


@app.command("semantic")
def semantic(
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
    """Run a semantic retrieval query against the current repository build."""

    from codeman.cli.app import get_container

    resolved_query = _resolve_query_text(query_text=query_text, query=query)

    typer.echo(
        f"Running semantic query for repository: {repository_id}",
        err=True,
    )
    container: BootstrapContainer = get_container(ctx)
    try:
        result = container.run_semantic_query.execute(
            RunSemanticQueryRequest(
                repository_id=repository_id,
                query_text=resolved_query,
            ),
        )
    except SemanticQueryError as error:
        _handle_query_error(
            error=error,
            output_format=output_format,
            command_name="query.semantic",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("query.semantic", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    lines = [
        _summary_line(
            result_count=result.diagnostics.match_count,
            total_count=result.diagnostics.total_match_count,
            truncated=result.diagnostics.truncated,
            label="Semantic retrieval",
        ),
        f"Retrieval Mode: {result.retrieval_mode}",
        f"Repository ID: {result.repository.repository_id}",
        f"Snapshot ID: {result.snapshot.snapshot_id}",
        f"Build ID: {result.build.build_id}",
        f"Provider: {result.build.provider_id}",
        f"Model: {result.build.model_id}",
        f"Model Version: {result.build.model_version}",
        f"Vector Engine: {result.build.vector_engine}",
        f"Semantic Config Fingerprint: {result.build.semantic_config_fingerprint}",
        f"Query: {result.query.text}",
        f"Latency: {result.diagnostics.query_latency_ms} ms",
    ]
    if result.results:
        lines.extend(_result_blocks(result))
    else:
        lines.append("No semantic matches found.")
    typer.echo("\n".join(lines))


@app.command("hybrid")
def hybrid(
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
    """Run a hybrid retrieval query against the current repository build."""

    from codeman.cli.app import get_container

    resolved_query = _resolve_query_text(query_text=query_text, query=query)

    typer.echo(
        f"Running hybrid query for repository: {repository_id}",
        err=True,
    )
    container: BootstrapContainer = get_container(ctx)
    try:
        result = container.run_hybrid_query.execute(
            RunHybridQueryRequest(
                repository_id=repository_id,
                query_text=resolved_query,
            ),
        )
    except HybridQueryError as error:
        _handle_query_error(
            error=error,
            output_format=output_format,
            command_name="query.hybrid",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("query.hybrid", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    lines = [
        _summary_line(
            result_count=result.diagnostics.match_count,
            total_count=result.diagnostics.total_match_count,
            truncated=result.diagnostics.truncated,
            label="Hybrid retrieval",
        ),
        f"Retrieval Mode: {result.retrieval_mode}",
        f"Repository ID: {result.repository.repository_id}",
        f"Snapshot ID: {result.snapshot.snapshot_id}",
        f"Build ID: {result.build.build_id}",
        f"Fusion Strategy: {result.build.fusion_strategy}",
        f"Rank Constant: {result.build.rank_constant}",
        f"Rank Window Size: {result.build.rank_window_size}",
        f"Lexical Build ID: {result.build.lexical_build.build_id}",
        f"Lexical Engine: {result.build.lexical_build.lexical_engine}",
        f"Semantic Build ID: {result.build.semantic_build.build_id}",
        f"Provider: {result.build.semantic_build.provider_id}",
        f"Model: {result.build.semantic_build.model_id}",
        f"Model Version: {result.build.semantic_build.model_version}",
        f"Vector Engine: {result.build.semantic_build.vector_engine}",
        (f"Semantic Config Fingerprint: {result.build.semantic_build.semantic_config_fingerprint}"),
        f"Query: {result.query.text}",
        f"Latency: {result.diagnostics.query_latency_ms} ms",
        _hybrid_component_line(
            label="Lexical Component",
            diagnostics=result.diagnostics.lexical,
        ),
        _hybrid_component_line(
            label="Semantic Component",
            diagnostics=result.diagnostics.semantic,
        ),
    ]
    if result.results:
        lines.extend(_result_blocks(result))
    else:
        lines.append("No hybrid matches found.")
    total_count_note = _hybrid_total_count_note(result)
    if total_count_note is not None:
        lines.append(total_count_note)
    typer.echo("\n".join(lines))

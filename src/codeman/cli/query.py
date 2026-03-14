"""Query commands."""

from __future__ import annotations

import typer

from codeman.application.query.run_lexical_query import LexicalQueryError
from codeman.bootstrap import BootstrapContainer
from codeman.cli.common import OutputFormat, build_command_meta, emit_json_response
from codeman.contracts.common import SuccessEnvelope
from codeman.contracts.errors import ErrorDetail, FailureEnvelope
from codeman.contracts.retrieval import RunLexicalQueryRequest

app = typer.Typer(help="Retrieval query commands.", no_args_is_help=True)


@app.callback()
def query_group() -> None:
    """Run retrieval queries."""


def _handle_query_error(
    *,
    error: LexicalQueryError,
    output_format: OutputFormat,
    command_name: str,
) -> None:
    """Render lexical-query failures in the requested output format."""

    envelope = FailureEnvelope(
        error=ErrorDetail(code=error.error_code, message=error.message),
        meta=build_command_meta(command_name, output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
    else:
        typer.secho(error.message, err=True, fg=typer.colors.RED)

    raise typer.Exit(code=error.exit_code)


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
        f"Lexical query matched {result.diagnostics.match_count} chunks",
        f"Repository ID: {result.repository.repository_id}",
        f"Snapshot ID: {result.snapshot.snapshot_id}",
        f"Build ID: {result.build.build_id}",
        f"Query: {result.query}",
        f"Latency: {result.diagnostics.query_latency_ms} ms",
    ]
    if result.matches:
        lines.extend(
            [
                (
                    f"{match.rank}. {match.relative_path} "
                    f"[{match.chunk_id}] "
                    f"{match.language}/{match.strategy} "
                    f"score={match.score:.4f}"
                )
                for match in result.matches
            ]
        )
    else:
        lines.append("No lexical matches found.")
    typer.echo("\n".join(lines))

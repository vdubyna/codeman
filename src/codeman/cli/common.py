"""Shared CLI helpers."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Sequence

import typer

from codeman.contracts.common import CommandMeta, SuccessEnvelope
from codeman.contracts.errors import ErrorDetail, FailureEnvelope
from codeman.contracts.retrieval import RetrievalResultItem


class OutputFormat(StrEnum):
    """Supported output formats for CLI commands."""

    TEXT = "text"
    JSON = "json"


def build_command_meta(
    command: str, output_format: OutputFormat = OutputFormat.TEXT
) -> CommandMeta:
    """Create command metadata for future JSON output handling."""

    return CommandMeta(command=command, output_format=output_format.value)


def emit_json_response(response: SuccessEnvelope | FailureEnvelope) -> None:
    """Write a JSON envelope to stdout."""

    typer.echo(response.model_dump_json())


def emit_failure_response(
    *,
    error_code: str,
    message: str,
    details: Any,
    exit_code: int,
    output_format: OutputFormat,
    command_name: str,
) -> None:
    """Render a stable CLI failure and stop command execution."""

    envelope = FailureEnvelope(
        error=ErrorDetail(
            code=error_code,
            message=message,
            details=details,
        ),
        meta=build_command_meta(command_name, output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
    else:
        typer.secho(message, err=True, fg=typer.colors.RED)

    raise typer.Exit(code=exit_code)


def resolve_query_text(
    *,
    query_text: str | None,
    query: str | None,
) -> str:
    """Resolve query text from positional or explicit option input."""

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


def build_retrieval_summary_line(
    *,
    result_count: int,
    total_count: int,
    truncated: bool,
    label: str,
) -> str:
    """Build a stable summary line for one retrieval result section."""

    if truncated:
        return f"{label} returned {result_count} of {total_count} results (truncated)"
    return f"{label} returned {result_count} results"


def render_retrieval_result_blocks(items: Sequence[RetrievalResultItem]) -> list[str]:
    """Render result items into stable text blocks for CLI output."""

    return [
        "\n".join(
            [
                f"{item.rank}. {item.relative_path} [{item.chunk_id}]",
                (
                    f"   span: lines {item.start_line}-{item.end_line} "
                    f"bytes {item.start_byte}-{item.end_byte}"
                ),
                f"   language/strategy: {item.language}/{item.strategy} score={item.score:.4f}",
                f"   preview: {item.content_preview}",
                f"   explanation: {item.explanation}",
            ]
        )
        for item in items
    ]

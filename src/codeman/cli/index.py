"""Index commands."""

from __future__ import annotations

import typer

from codeman.application.indexing.extract_source_files import ExtractSourceFilesError
from codeman.bootstrap import BootstrapContainer
from codeman.cli.common import OutputFormat, build_command_meta, emit_json_response
from codeman.contracts.common import SuccessEnvelope
from codeman.contracts.errors import ErrorDetail, FailureEnvelope
from codeman.contracts.repository import ExtractSourceFilesRequest

app = typer.Typer(help="Index build and refresh commands.", no_args_is_help=True)


@app.callback()
def index_group() -> None:
    """Manage index build workflows."""


def _handle_extract_sources_error(
    *,
    error: ExtractSourceFilesError,
    output_format: OutputFormat,
    command_name: str,
) -> None:
    """Render extraction failures in the requested output format."""

    envelope = FailureEnvelope(
        error=ErrorDetail(code=error.error_code, message=error.message),
        meta=build_command_meta(command_name, output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
    else:
        typer.secho(error.message, err=True, fg=typer.colors.RED)

    raise typer.Exit(code=error.exit_code)


@app.command("extract-sources")
def extract_sources(
    ctx: typer.Context,
    snapshot_id: str,
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--output-format"),
) -> None:
    """Extract supported source files for a previously registered snapshot."""

    from codeman.cli.app import get_container

    container: BootstrapContainer = get_container(ctx)
    try:
        result = container.extract_source_files.execute(
            ExtractSourceFilesRequest(snapshot_id=snapshot_id),
        )
    except ExtractSourceFilesError as error:
        _handle_extract_sources_error(
            error=error,
            output_format=output_format,
            command_name="index.extract-sources",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("index.extract-sources", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    persisted_summary = ", ".join(
        f"{language}={count}"
        for language, count in result.diagnostics.persisted_by_language.items()
    ) or "none"
    skipped_summary = ", ".join(
        f"{reason}={count}"
        for reason, count in result.diagnostics.skipped_by_reason.items()
    ) or "none"
    typer.echo(
        "\n".join(
            [
                f"Extracted source inventory: {result.diagnostics.persisted_total} files",
                f"Snapshot ID: {result.snapshot.snapshot_id}",
                f"Repository ID: {result.repository.repository_id}",
                f"Persisted by language: {persisted_summary}",
                f"Skipped by reason: {skipped_summary}",
            ]
        )
    )

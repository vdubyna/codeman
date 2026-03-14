"""Repository commands."""

from __future__ import annotations

from pathlib import Path

import typer

from codeman.application.repo.register_repository import RepositoryRegistrationError
from codeman.bootstrap import BootstrapContainer
from codeman.cli.common import OutputFormat, build_command_meta, emit_json_response
from codeman.contracts.common import SuccessEnvelope
from codeman.contracts.errors import ErrorDetail, FailureEnvelope
from codeman.contracts.repository import RegisterRepositoryRequest

app = typer.Typer(help="Repository registration and metadata commands.", no_args_is_help=True)


@app.callback()
def repo_group() -> None:
    """Manage repository registration and metadata."""


def _handle_registration_error(
    *,
    error: RepositoryRegistrationError,
    output_format: OutputFormat,
) -> None:
    """Render a repository registration failure in the requested format."""

    envelope = FailureEnvelope(
        error=ErrorDetail(code=error.error_code, message=error.message),
        meta=build_command_meta("repo.register", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
    else:
        typer.secho(error.message, err=True, fg=typer.colors.RED)

    raise typer.Exit(code=error.exit_code)


@app.command("register")
def register_repository(
    ctx: typer.Context,
    repository_path: Path,
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--output-format"),
) -> None:
    """Register a local repository as an indexing target."""

    from codeman.cli.app import get_container

    container: BootstrapContainer = get_container(ctx)
    try:
        result = container.register_repository.execute(
            RegisterRepositoryRequest(repository_path=repository_path),
        )
    except RepositoryRegistrationError as error:
        _handle_registration_error(error=error, output_format=output_format)

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("repo.register", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    typer.echo(
        "\n".join(
            [
                f"Registered repository: {result.repository.repository_name}",
                f"Repository ID: {result.repository.repository_id}",
                f"Canonical path: {result.repository.canonical_path}",
                f"Runtime workspace: {result.runtime_root}",
                f"Metadata database: {result.metadata_database_path}",
            ]
        )
    )

"""Repository commands."""

from __future__ import annotations

from pathlib import Path

import typer

from codeman.application.repo.create_snapshot import CreateSnapshotError
from codeman.application.repo.register_repository import RepositoryRegistrationError
from codeman.bootstrap import BootstrapContainer
from codeman.cli.common import OutputFormat, build_command_meta, emit_json_response
from codeman.contracts.common import SuccessEnvelope
from codeman.contracts.errors import ErrorDetail, FailureEnvelope
from codeman.contracts.repository import CreateSnapshotRequest, RegisterRepositoryRequest

app = typer.Typer(help="Repository registration and metadata commands.", no_args_is_help=True)


@app.callback()
def repo_group() -> None:
    """Manage repository registration and metadata."""


def _handle_repository_error(
    *,
    error: RepositoryRegistrationError | CreateSnapshotError,
    output_format: OutputFormat,
    command_name: str,
) -> None:
    """Render a repository command failure in the requested format."""

    envelope = FailureEnvelope(
        error=ErrorDetail(code=error.error_code, message=error.message),
        meta=build_command_meta(command_name, output_format),
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
        _handle_repository_error(
            error=error,
            output_format=output_format,
            command_name="repo.register",
        )

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


@app.command("snapshot")
def create_snapshot(
    ctx: typer.Context,
    repository_id: str,
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--output-format"),
) -> None:
    """Create an immutable snapshot for a registered repository."""

    from codeman.cli.app import get_container

    container: BootstrapContainer = get_container(ctx)
    try:
        result = container.create_snapshot.execute(
            CreateSnapshotRequest(repository_id=repository_id),
        )
    except CreateSnapshotError as error:
        _handle_repository_error(
            error=error,
            output_format=output_format,
            command_name="repo.snapshot",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("repo.snapshot", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    typer.echo(
        "\n".join(
            [
                f"Created snapshot: {result.snapshot.snapshot_id}",
                f"Repository ID: {result.repository.repository_id}",
                f"Repository path: {result.repository.canonical_path}",
                f"Revision source: {result.snapshot.revision_source}",
                f"Revision identity: {result.snapshot.revision_identity}",
                f"Manifest path: {result.snapshot.manifest_path}",
            ]
        )
    )

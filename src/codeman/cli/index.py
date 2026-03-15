"""Index commands."""

from __future__ import annotations

import typer

from codeman.application.indexing.build_chunks import BuildChunksError
from codeman.application.indexing.build_lexical_index import BuildLexicalIndexError
from codeman.application.indexing.build_semantic_index import BuildSemanticIndexError
from codeman.application.indexing.extract_source_files import ExtractSourceFilesError
from codeman.application.repo.reindex_repository import ReindexRepositoryError
from codeman.bootstrap import BootstrapContainer
from codeman.cli.common import OutputFormat, build_command_meta, emit_json_response
from codeman.contracts.chunking import BuildChunksRequest
from codeman.contracts.common import SuccessEnvelope
from codeman.contracts.errors import ErrorDetail, FailureEnvelope
from codeman.contracts.reindexing import ReindexRepositoryRequest
from codeman.contracts.repository import ExtractSourceFilesRequest
from codeman.contracts.retrieval import BuildLexicalIndexRequest, BuildSemanticIndexRequest

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


def _handle_build_chunks_error(
    *,
    error: BuildChunksError,
    output_format: OutputFormat,
    command_name: str,
) -> None:
    """Render chunk-generation failures in the requested output format."""

    envelope = FailureEnvelope(
        error=ErrorDetail(code=error.error_code, message=error.message),
        meta=build_command_meta(command_name, output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
    else:
        typer.secho(error.message, err=True, fg=typer.colors.RED)

    raise typer.Exit(code=error.exit_code)


def _handle_build_lexical_error(
    *,
    error: BuildLexicalIndexError,
    output_format: OutputFormat,
    command_name: str,
) -> None:
    """Render lexical-build failures in the requested output format."""

    envelope = FailureEnvelope(
        error=ErrorDetail(code=error.error_code, message=error.message),
        meta=build_command_meta(command_name, output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
    else:
        typer.secho(error.message, err=True, fg=typer.colors.RED)

    raise typer.Exit(code=error.exit_code)


def _handle_build_semantic_error(
    *,
    error: BuildSemanticIndexError,
    output_format: OutputFormat,
    command_name: str,
) -> None:
    """Render semantic-build failures in the requested output format."""

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


def _handle_reindex_error(
    *,
    error: ReindexRepositoryError,
    output_format: OutputFormat,
    command_name: str,
) -> None:
    """Render re-index failures in the requested output format."""

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

    persisted_summary = (
        ", ".join(
            f"{language}={count}"
            for language, count in result.diagnostics.persisted_by_language.items()
        )
        or "none"
    )
    skipped_summary = (
        ", ".join(
            f"{reason}={count}" for reason, count in result.diagnostics.skipped_by_reason.items()
        )
        or "none"
    )
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


@app.command("build-chunks")
def build_chunks(
    ctx: typer.Context,
    snapshot_id: str,
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--output-format"),
) -> None:
    """Generate retrieval chunks for a previously extracted snapshot inventory."""

    from codeman.cli.app import get_container

    typer.echo(f"Generating chunks for snapshot: {snapshot_id}", err=True)
    container: BootstrapContainer = get_container(ctx)
    try:
        result = container.build_chunks.execute(
            BuildChunksRequest(snapshot_id=snapshot_id),
        )
    except BuildChunksError as error:
        _handle_build_chunks_error(
            error=error,
            output_format=output_format,
            command_name="index.build-chunks",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("index.build-chunks", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    chunks_by_language = (
        ", ".join(
            f"{language}={count}"
            for language, count in result.diagnostics.chunks_by_language.items()
        )
        or "none"
    )
    chunks_by_strategy = (
        ", ".join(
            f"{strategy}={count}"
            for strategy, count in result.diagnostics.chunks_by_strategy.items()
        )
        or "none"
    )
    fallback_paths = [
        diagnostic.relative_path
        for diagnostic in result.diagnostics.file_diagnostics
        if diagnostic.mode == "fallback"
    ]
    lines = [
        f"Generated retrieval chunks: {result.diagnostics.total_chunks} chunks",
        f"Run ID: {result.run_id}",
        f"Snapshot ID: {result.snapshot.snapshot_id}",
        f"Repository ID: {result.repository.repository_id}",
        f"Chunks by language: {chunks_by_language}",
        f"Chunks by strategy: {chunks_by_strategy}",
        f"Files using fallback: {result.diagnostics.fallback_file_count}",
        f"Skipped files: {result.diagnostics.skipped_file_count}",
    ]
    if fallback_paths:
        lines.append(f"Fallback paths: {', '.join(fallback_paths)}")
    typer.echo("\n".join(lines))


@app.command("build-lexical")
def build_lexical(
    ctx: typer.Context,
    snapshot_id: str,
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--output-format"),
) -> None:
    """Build lexical retrieval artifacts for a previously chunked snapshot."""

    from codeman.cli.app import get_container

    typer.echo(f"Building lexical index for snapshot: {snapshot_id}", err=True)
    container: BootstrapContainer = get_container(ctx)
    try:
        result = container.build_lexical_index.execute(
            BuildLexicalIndexRequest(snapshot_id=snapshot_id),
        )
    except BuildLexicalIndexError as error:
        _handle_build_lexical_error(
            error=error,
            output_format=output_format,
            command_name="index.build-lexical",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("index.build-lexical", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    typer.echo(
        "\n".join(
            [
                f"Built lexical index: {result.diagnostics.chunks_indexed} chunks",
                f"Run ID: {result.run_id}",
                f"Build ID: {result.build.build_id}",
                f"Snapshot ID: {result.snapshot.snapshot_id}",
                f"Repository ID: {result.repository.repository_id}",
                f"Lexical engine: {result.build.lexical_engine}",
                f"Tokenizer: {result.build.tokenizer_spec}",
                f"Indexed fields: {', '.join(result.build.indexed_fields)}",
                f"Index path: {result.build.index_path}",
                "Refreshed existing artifact: "
                f"{'yes' if result.diagnostics.refreshed_existing_artifact else 'no'}",
            ]
        )
    )


@app.command("build-semantic")
def build_semantic(
    ctx: typer.Context,
    snapshot_id: str,
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--output-format"),
) -> None:
    """Build semantic retrieval artifacts for a previously chunked snapshot."""

    from codeman.cli.app import get_container

    typer.echo(f"Building semantic index for snapshot: {snapshot_id}", err=True)
    container: BootstrapContainer = get_container(ctx)
    try:
        result = container.build_semantic_index.execute(
            BuildSemanticIndexRequest(snapshot_id=snapshot_id),
        )
    except BuildSemanticIndexError as error:
        _handle_build_semantic_error(
            error=error,
            output_format=output_format,
            command_name="index.build-semantic",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("index.build-semantic", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    provider_mode = "external" if result.provider.is_external_provider else "local"
    lines = [
        f"Built semantic index: {result.diagnostics.document_count} documents",
        f"Run ID: {result.run_id}",
        f"Build ID: {result.build.build_id}",
        f"Snapshot ID: {result.snapshot.snapshot_id}",
        f"Repository ID: {result.repository.repository_id}",
        f"Provider: {result.provider.provider_id} ({provider_mode})",
        f"Model: {result.provider.model_id}@{result.provider.model_version}",
        f"Vector engine: {result.build.vector_engine}",
        f"Semantic config fingerprint: {result.build.semantic_config_fingerprint}",
        f"Embedding dimension: {result.diagnostics.embedding_dimension}",
        f"Embedding artifact: {result.diagnostics.embedding_documents_path}",
        f"Vector index path: {result.build.artifact_path}",
        "Refreshed existing artifact: "
        f"{'yes' if result.diagnostics.refreshed_existing_artifact else 'no'}",
    ]
    if result.provider.local_model_path is not None:
        lines.insert(6, f"Local model path: {result.provider.local_model_path}")
    typer.echo("\n".join(lines))


@app.command("reindex")
def reindex_repository(
    ctx: typer.Context,
    repository_id: str,
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--output-format"),
) -> None:
    """Re-index a registered repository using the latest usable baseline."""

    from codeman.cli.app import get_container

    typer.echo(f"Re-indexing repository: {repository_id}", err=True)
    container: BootstrapContainer = get_container(ctx)
    try:
        result = container.reindex_repository.execute(
            ReindexRepositoryRequest(repository_id=repository_id),
        )
    except ReindexRepositoryError as error:
        _handle_reindex_error(
            error=error,
            output_format=output_format,
            command_name="index.reindex",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("index.reindex", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    typer.echo(
        "\n".join(
            [
                f"Re-indexed repository: {result.repository.repository_name}",
                f"Run ID: {result.run_id}",
                f"Repository ID: {result.repository.repository_id}",
                f"Previous snapshot: {result.previous_snapshot_id}",
                f"Result snapshot: {result.result_snapshot_id}",
                f"Change reason: {result.change_reason}",
                f"No-op: {'yes' if result.noop else 'no'}",
                f"Source files reused: {result.source_files_reused}",
                f"Source files rebuilt: {result.source_files_rebuilt}",
                f"Source files removed: {result.source_files_removed}",
                f"Chunks reused: {result.chunks_reused}",
                f"Chunks rebuilt: {result.chunks_rebuilt}",
            ]
        )
    )

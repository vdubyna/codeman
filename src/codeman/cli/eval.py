"""Evaluation commands."""

from __future__ import annotations

from pathlib import Path

import typer
from pydantic import ValidationError

from codeman.application.evaluation.load_benchmark_dataset import BenchmarkDatasetLoadError
from codeman.application.evaluation.run_benchmark import BenchmarkRunError
from codeman.bootstrap import BootstrapContainer
from codeman.cli.common import (
    OutputFormat,
    build_command_meta,
    emit_failure_response,
    emit_json_response,
)
from codeman.contracts.common import SuccessEnvelope
from codeman.contracts.evaluation import RunBenchmarkRequest, RunBenchmarkResult

app = typer.Typer(help="Benchmark and evaluation commands.", no_args_is_help=True)


@app.callback()
def eval_group() -> None:
    """Run benchmark workflows."""


def _render_text_output(result: RunBenchmarkResult) -> str:
    lines = [
        "Benchmark run completed.",
        f"Run ID: {result.run.run_id}",
        f"Repository ID: {result.run.repository_id}",
        f"Snapshot ID: {result.run.snapshot_id}",
        f"Retrieval Mode: {result.run.retrieval_mode}",
        f"Build ID: {result.build.build_id}",
        f"Dataset ID: {result.dataset.dataset_id}",
        f"Dataset Version: {result.dataset.dataset_version}",
        f"Dataset Fingerprint: {result.dataset.dataset_fingerprint}",
        f"Case Count: {result.run.case_count}",
        f"Completed Case Count: {result.run.completed_case_count}",
        f"Status: {result.run.status}",
        f"Started At: {result.run.started_at.isoformat()}",
        f"Completed At: {result.run.completed_at.isoformat() if result.run.completed_at else '-'}",
        f"Artifact Path: {result.run.artifact_path}",
    ]
    return "\n".join(lines)


@app.command("benchmark")
def benchmark(
    ctx: typer.Context,
    repository_id: str,
    dataset_path: Path,
    retrieval_mode: str = typer.Option(
        "lexical",
        "--retrieval-mode",
        help="Retrieval mode to benchmark: lexical, semantic, or hybrid.",
    ),
    max_results: int = typer.Option(
        20,
        "--max-results",
        min=1,
        max=100,
        help="Maximum ranked retrieval results to retain per benchmark case.",
    ),
    output_format: OutputFormat = typer.Option(OutputFormat.TEXT, "--output-format"),
) -> None:
    """Execute a benchmark dataset against one indexed repository."""

    from codeman.cli.app import get_container

    container: BootstrapContainer = get_container(ctx)
    try:
        request = RunBenchmarkRequest(
            repository_id=repository_id,
            dataset_path=dataset_path,
            retrieval_mode=retrieval_mode,
            max_results=max_results,
        )
        result = container.run_benchmark.execute(
            request,
            progress=lambda line: typer.echo(line, err=True),
        )
    except ValidationError as error:
        typer.secho(str(error), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=2) from error
    except BenchmarkDatasetLoadError as error:
        emit_failure_response(
            error_code=error.error_code,
            message=error.message,
            details=error.details,
            exit_code=error.exit_code,
            output_format=output_format,
            command_name="eval.benchmark",
        )
    except BenchmarkRunError as error:
        emit_failure_response(
            error_code=error.error_code,
            message=error.message,
            details=error.details,
            exit_code=error.exit_code,
            output_format=output_format,
            command_name="eval.benchmark",
        )

    envelope = SuccessEnvelope(
        data=result,
        meta=build_command_meta("eval.benchmark", output_format),
    )
    if output_format is OutputFormat.JSON:
        emit_json_response(envelope)
        return

    typer.echo(_render_text_output(result))

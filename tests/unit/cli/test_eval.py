from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from codeman.application.evaluation.run_benchmark import BenchmarkRunModeUnavailableError
from codeman.bootstrap import bootstrap
from codeman.cli.app import app
from codeman.contracts.evaluation import (
    BenchmarkDatasetSummary,
    BenchmarkRunRecord,
    BenchmarkRunStatus,
    RunBenchmarkResult,
)
from codeman.contracts.retrieval import (
    LexicalRetrievalBuildContext,
    RetrievalRepositoryContext,
    RetrievalSnapshotContext,
)

runner = CliRunner()


def build_benchmark_result(dataset_path: Path) -> RunBenchmarkResult:
    return RunBenchmarkResult(
        run=BenchmarkRunRecord(
            run_id="run-123",
            repository_id="repo-123",
            snapshot_id="snapshot-123",
            retrieval_mode="lexical",
            dataset_id="fixture-benchmark",
            dataset_version="2026-03-15",
            dataset_fingerprint="f" * 64,
            case_count=2,
            completed_case_count=2,
            status=BenchmarkRunStatus.SUCCEEDED,
            artifact_path=Path("/tmp/.codeman/artifacts/benchmarks/run-123/run.json"),
            started_at=datetime(2026, 3, 15, 9, 0, tzinfo=UTC),
            completed_at=datetime(2026, 3, 15, 9, 1, tzinfo=UTC),
        ),
        repository=RetrievalRepositoryContext(
            repository_id="repo-123",
            repository_name="registered-repo",
        ),
        snapshot=RetrievalSnapshotContext(
            snapshot_id="snapshot-123",
            revision_identity="revision-abc",
            revision_source="filesystem_fingerprint",
        ),
        build=LexicalRetrievalBuildContext(
            build_id="lexical-build-123",
            indexing_config_fingerprint="index-fingerprint-123",
            lexical_engine="sqlite-fts5",
            tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
            indexed_fields=["content", "relative_path"],
        ),
        dataset=BenchmarkDatasetSummary(
            dataset_path=dataset_path,
            schema_version="1",
            dataset_id="fixture-benchmark",
            dataset_version="2026-03-15",
            case_count=2,
            judgment_count=2,
            dataset_fingerprint="f" * 64,
        ),
    )


def test_eval_benchmark_command_renders_text_summary_and_stderr_progress(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text("{}", encoding="utf-8")
    container = bootstrap(workspace_root=workspace)

    class StubRunBenchmarkUseCase:
        def execute(self, request: object, *, progress: object | None = None) -> RunBenchmarkResult:
            assert request.repository_id == "repo-123"
            assert request.retrieval_mode == "lexical"
            assert request.max_results == 7
            if progress is not None:
                progress(f"Loading benchmark dataset: {dataset_path}")
                progress("Running benchmark case 1/2: case-1")
            return build_benchmark_result(dataset_path)

    container.run_benchmark = StubRunBenchmarkUseCase()

    result = runner.invoke(
        app,
        [
            "eval",
            "benchmark",
            "repo-123",
            str(dataset_path),
            "--retrieval-mode",
            "lexical",
            "--max-results",
            "7",
        ],
        obj=container,
    )

    assert result.exit_code == 0, result.stdout
    assert "Benchmark run completed." in result.stdout
    assert "Run ID: run-123" in result.stdout
    assert "Retrieval Mode: lexical" in result.stdout


def test_eval_benchmark_command_emits_clean_json_stdout(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text("{}", encoding="utf-8")
    container = bootstrap(workspace_root=workspace)

    class StubRunBenchmarkUseCase:
        def execute(self, request: object, *, progress: object | None = None) -> RunBenchmarkResult:
            if progress is not None:
                progress("Resolving benchmark baseline for repository: repo-123 (lexical)")
            return build_benchmark_result(dataset_path)

    container.run_benchmark = StubRunBenchmarkUseCase()

    result = runner.invoke(
        app,
        [
            "eval",
            "benchmark",
            "repo-123",
            str(dataset_path),
            "--output-format",
            "json",
        ],
        obj=container,
    )
    payload = json.loads(result.stdout)

    assert result.exit_code == 0, result.stdout
    assert payload["ok"] is True
    assert payload["data"]["run"]["run_id"] == "run-123"
    assert payload["meta"]["command"] == "eval.benchmark"


def test_eval_benchmark_command_returns_json_failure_envelope(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text("{}", encoding="utf-8")
    container = bootstrap(workspace_root=workspace)

    class StubRunBenchmarkUseCase:
        def execute(self, request: object, *, progress: object | None = None) -> object:
            if progress is not None:
                progress("Running benchmark case 1/2: case-1")
            raise BenchmarkRunModeUnavailableError(
                (
                    "Benchmark cannot continue because the selected retrieval mode is "
                    "unavailable during execution."
                ),
                details={"query_id": "case-1", "retrieval_mode": "lexical"},
            )

    container.run_benchmark = StubRunBenchmarkUseCase()

    result = runner.invoke(
        app,
        [
            "eval",
            "benchmark",
            "repo-123",
            str(dataset_path),
            "--output-format",
            "json",
        ],
        obj=container,
    )
    payload = json.loads(result.stdout)

    assert result.exit_code == 67
    assert payload["ok"] is False
    assert payload["error"]["code"] == "benchmark_retrieval_mode_unavailable"
    assert payload["meta"]["command"] == "eval.benchmark"

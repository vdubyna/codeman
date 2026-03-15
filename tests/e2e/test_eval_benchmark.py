from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parents[1] / "fixtures" / "repositories" / "mixed_stack_fixture"
)
FIXTURE_DATASET = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "queries"
    / "mixed_stack_fixture_golden_queries.json"
)


def prepare_benchmark_repository(
    *,
    tmp_path: Path,
    scenario_name: str,
    build_semantic: bool,
) -> tuple[Path, dict[str, str], str]:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / f"{scenario_name}-workspace"
    workspace.mkdir()
    target_repo = tmp_path / f"{scenario_name}-registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, target_repo)
    cache_dir = project_root / ".local" / "uv-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", str(cache_dir))
    env["CODEMAN_WORKSPACE_ROOT"] = str(workspace)
    local_model_path = workspace / "local-model"
    local_model_path.mkdir()
    env["CODEMAN_SEMANTIC_PROVIDER_ID"] = "local-hash"
    env["CODEMAN_SEMANTIC_LOCAL_MODEL_PATH"] = str(local_model_path)
    env["CODEMAN_SEMANTIC_MODEL_ID"] = "fixture-local"
    env["CODEMAN_SEMANTIC_MODEL_VERSION"] = "2026-03-14"

    register_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "repo",
            "register",
            str(target_repo),
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )
    register_payload = json.loads(register_result.stdout)
    repository_id = register_payload["data"]["repository"]["repository_id"]

    snapshot_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "repo",
            "snapshot",
            repository_id,
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )
    snapshot_payload = json.loads(snapshot_result.stdout)
    snapshot_id = snapshot_payload["data"]["snapshot"]["snapshot_id"]

    extract_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "index",
            "extract-sources",
            snapshot_id,
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )
    build_chunks_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "index",
            "build-chunks",
            snapshot_id,
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )
    build_lexical_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "index",
            "build-lexical",
            snapshot_id,
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )

    assert register_result.returncode == 0, register_result.stderr
    assert snapshot_result.returncode == 0, snapshot_result.stderr
    assert extract_result.returncode == 0, extract_result.stderr
    assert build_chunks_result.returncode == 0, build_chunks_result.stderr
    assert build_lexical_result.returncode == 0, build_lexical_result.stderr

    if build_semantic:
        build_semantic_result = subprocess.run(
            [
                "uv",
                "run",
                "codeman",
                "index",
                "build-semantic",
                snapshot_id,
                "--output-format",
                "json",
            ],
            capture_output=True,
            check=False,
            text=True,
            cwd=project_root,
            env=env,
        )
        assert build_semantic_result.returncode == 0, build_semantic_result.stderr

    return project_root, env, repository_id


@pytest.mark.parametrize("retrieval_mode", ["lexical", "semantic", "hybrid"])
def test_uv_run_eval_benchmark_supports_text_and_json_output(
    tmp_path: Path,
    retrieval_mode: str,
) -> None:
    text_root, text_env, text_repository_id = prepare_benchmark_repository(
        tmp_path=tmp_path,
        scenario_name=f"{retrieval_mode}-text",
        build_semantic=retrieval_mode in {"semantic", "hybrid"},
    )
    json_root, json_env, json_repository_id = prepare_benchmark_repository(
        tmp_path=tmp_path,
        scenario_name=f"{retrieval_mode}-json",
        build_semantic=retrieval_mode in {"semantic", "hybrid"},
    )

    text_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "eval",
            "benchmark",
            text_repository_id,
            str(FIXTURE_DATASET),
            "--retrieval-mode",
            retrieval_mode,
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=text_root,
        env=text_env,
    )
    json_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "eval",
            "benchmark",
            json_repository_id,
            str(FIXTURE_DATASET),
            "--retrieval-mode",
            retrieval_mode,
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=json_root,
        env=json_env,
    )

    payload = json.loads(json_result.stdout)
    artifact_path = Path(payload["data"]["run"]["artifact_path"])
    metrics_artifact_path = Path(payload["data"]["metrics"]["artifact_path"])

    assert text_result.returncode == 0, text_result.stderr
    assert json_result.returncode == 0, json_result.stderr
    assert "Benchmark run completed." in text_result.stdout
    assert f"Retrieval Mode: {retrieval_mode}" in text_result.stdout
    assert "Dataset ID: mixed-stack-fixture-golden-queries" in text_result.stdout
    assert "Recall@K:" in text_result.stdout
    assert "Metrics Artifact Path:" in text_result.stdout
    assert payload["ok"] is True
    assert payload["data"]["run"]["status"] == "succeeded"
    assert payload["data"]["run"]["retrieval_mode"] == retrieval_mode
    assert payload["data"]["dataset"]["dataset_id"] == "mixed-stack-fixture-golden-queries"
    assert payload["data"]["metrics"]["evaluated_at_k"] == 20
    assert payload["data"]["metrics"]["metrics"]["recall_at_k"] >= 0.0
    assert payload["data"]["metrics"]["metrics"]["mrr"] >= 0.0
    assert payload["data"]["metrics"]["metrics"]["ndcg_at_k"] >= 0.0
    assert payload["meta"]["command"] == "eval.benchmark"
    assert artifact_path.exists()
    assert metrics_artifact_path.exists()
    assert ".codeman/artifacts/benchmarks/" in artifact_path.as_posix()
    assert metrics_artifact_path.name == "metrics.json"
    assert "Loading benchmark dataset:" in text_result.stderr
    assert "Resolving benchmark baseline for repository:" in text_result.stderr
    assert "Running benchmark case 1/" in text_result.stderr
    assert "Writing benchmark artifact for run:" in text_result.stderr
    assert "Calculating benchmark metrics for run:" in text_result.stderr
    assert "Recording benchmark provenance for run:" in json_result.stderr


def test_uv_run_eval_report_supports_text_and_json_output(tmp_path: Path) -> None:
    project_root, env, repository_id = prepare_benchmark_repository(
        tmp_path=tmp_path,
        scenario_name="report",
        build_semantic=False,
    )

    benchmark_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "eval",
            "benchmark",
            repository_id,
            str(FIXTURE_DATASET),
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )
    benchmark_payload = json.loads(benchmark_result.stdout)
    run_id = benchmark_payload["data"]["run"]["run_id"]

    text_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "eval",
            "report",
            run_id,
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )
    json_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "eval",
            "report",
            run_id,
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )

    payload = json.loads(json_result.stdout)
    report_artifact_path = Path(payload["data"]["report_artifact_path"])

    assert benchmark_result.returncode == 0, benchmark_result.stderr
    assert text_result.returncode == 0, text_result.stderr
    assert json_result.returncode == 0, json_result.stderr
    assert "Benchmark report generated." in text_result.stdout
    assert f"Run ID: {run_id}" in text_result.stdout
    assert "Retrieval Mode: lexical" in text_result.stdout
    assert "Configuration ID:" in text_result.stdout
    assert payload["ok"] is True
    assert payload["data"]["run"]["run_id"] == run_id
    assert payload["data"]["provenance"]["workflow_type"] == "eval.benchmark"
    assert payload["meta"]["command"] == "eval.report"
    assert report_artifact_path.exists()
    assert report_artifact_path.name == "report.md"
    assert "# Benchmark Report:" in report_artifact_path.read_text(encoding="utf-8")
    assert "Loading benchmark evidence for run:" in text_result.stderr
    assert "Writing benchmark report artifact for run:" in json_result.stderr


def test_uv_run_compare_benchmark_runs_marks_context_mismatches_explicitly(
    tmp_path: Path,
) -> None:
    project_root, env, repository_id = prepare_benchmark_repository(
        tmp_path=tmp_path,
        scenario_name="compare-benchmark-runs",
        build_semantic=True,
    )
    alternate_dataset = tmp_path / "mixed_stack_fixture_golden_queries_v2.json"
    dataset_payload = json.loads(FIXTURE_DATASET.read_text(encoding="utf-8"))
    dataset_payload["dataset_version"] = "2026-03-16"
    alternate_dataset.write_text(json.dumps(dataset_payload, indent=2), encoding="utf-8")

    first_benchmark = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "eval",
            "benchmark",
            repository_id,
            str(FIXTURE_DATASET),
            "--retrieval-mode",
            "lexical",
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )
    second_benchmark = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "eval",
            "benchmark",
            repository_id,
            str(alternate_dataset),
            "--retrieval-mode",
            "semantic",
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )

    first_payload = json.loads(first_benchmark.stdout)
    second_payload = json.loads(second_benchmark.stdout)
    first_run_id = first_payload["data"]["run"]["run_id"]
    second_run_id = second_payload["data"]["run"]["run_id"]

    text_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "compare",
            "benchmark-runs",
            "--run-id",
            first_run_id,
            "--run-id",
            second_run_id,
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )
    json_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "compare",
            "benchmark-runs",
            "--run-id",
            first_run_id,
            "--run-id",
            second_run_id,
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )

    payload = json.loads(json_result.stdout)
    difference_keys = {
        difference["key"] for difference in payload["data"]["comparability"]["differences"]
    }

    assert first_benchmark.returncode == 0, first_benchmark.stderr
    assert second_benchmark.returncode == 0, second_benchmark.stderr
    assert text_result.returncode == 0, text_result.stderr
    assert json_result.returncode == 0, json_result.stderr
    assert "Benchmark run comparison completed." in text_result.stdout
    assert "Apples-to-Apples: no" in text_result.stdout
    assert "Compared runs used different benchmark dataset versions." in text_result.stdout
    assert "Dataset Version:" in text_result.stdout
    assert payload["ok"] is True
    assert payload["data"]["entries"][0]["run"]["run_id"] == first_run_id
    assert payload["data"]["entries"][1]["run"]["run_id"] == second_run_id
    assert payload["data"]["comparability"]["is_apples_to_apples"] is False
    assert "dataset_version" in difference_keys
    assert payload["meta"]["command"] == "compare.benchmark_runs"
    assert "Running benchmark comparison for runs:" in text_result.stderr
    assert "Loading benchmark comparison evidence for run:" in text_result.stderr

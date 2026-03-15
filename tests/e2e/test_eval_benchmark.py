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

    assert text_result.returncode == 0, text_result.stderr
    assert json_result.returncode == 0, json_result.stderr
    assert "Benchmark run completed." in text_result.stdout
    assert f"Retrieval Mode: {retrieval_mode}" in text_result.stdout
    assert "Dataset ID: mixed-stack-fixture-golden-queries" in text_result.stdout
    assert payload["ok"] is True
    assert payload["data"]["run"]["status"] == "succeeded"
    assert payload["data"]["run"]["retrieval_mode"] == retrieval_mode
    assert payload["data"]["dataset"]["dataset_id"] == "mixed-stack-fixture-golden-queries"
    assert payload["meta"]["command"] == "eval.benchmark"
    assert artifact_path.exists()
    assert ".codeman/artifacts/benchmarks/" in artifact_path.as_posix()
    assert "Loading benchmark dataset:" in text_result.stderr
    assert "Resolving benchmark baseline for repository:" in text_result.stderr
    assert "Running benchmark case 1/" in text_result.stderr
    assert "Writing benchmark artifact for run:" in text_result.stderr
    assert "Recording benchmark provenance for run:" in json_result.stderr

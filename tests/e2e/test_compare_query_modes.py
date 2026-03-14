from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parents[1] / "fixtures" / "repositories" / "mixed_stack_fixture"
)


def prepare_repository(
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


def test_uv_run_compare_query_modes_supports_text_and_json_output(tmp_path: Path) -> None:
    text_root, text_env, text_repository_id = prepare_repository(
        tmp_path=tmp_path,
        scenario_name="text",
        build_semantic=True,
    )
    json_root, json_env, json_repository_id = prepare_repository(
        tmp_path=tmp_path,
        scenario_name="json",
        build_semantic=True,
    )

    text_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "compare",
            "query-modes",
            text_repository_id,
            "controller home route",
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
            "compare",
            "query-modes",
            json_repository_id,
            "controller home route",
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

    assert text_result.returncode == 0, text_result.stderr
    assert json_result.returncode == 0, json_result.stderr
    assert "Compared Modes: lexical, semantic, hybrid" in text_result.stdout
    assert "Rank Alignment:" in text_result.stdout
    assert "Lexical Results:" in text_result.stdout
    assert "Semantic Results:" in text_result.stdout
    assert "Hybrid Results:" in text_result.stdout
    assert payload["ok"] is True
    assert payload["data"]["entries"][0]["retrieval_mode"] == "lexical"
    assert payload["data"]["entries"][1]["retrieval_mode"] == "semantic"
    assert payload["data"]["entries"][2]["retrieval_mode"] == "hybrid"
    assert payload["data"]["alignment"][0]["chunk_id"]
    assert payload["data"]["diagnostics"]["alignment_count"] >= 1
    assert "Running retrieval mode comparison for repository" in text_result.stderr
    assert "Running retrieval mode comparison for repository" in json_result.stderr


def test_uv_run_compare_query_modes_returns_stable_failure_when_semantic_baseline_missing(
    tmp_path: Path,
) -> None:
    project_root, env, repository_id = prepare_repository(
        tmp_path=tmp_path,
        scenario_name="failure",
        build_semantic=False,
    )

    compare_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "compare",
            "query-modes",
            repository_id,
            "controller home route",
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )

    payload = json.loads(compare_result.stdout)

    assert compare_result.returncode == 52
    assert payload["ok"] is False
    assert payload["error"]["code"] == "compare_retrieval_mode_baseline_missing"
    assert payload["error"]["details"]["mode"] == "semantic"
    assert payload["meta"]["command"] == "compare.query_modes"
    assert "Traceback" not in compare_result.stderr

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parents[1] / "fixtures" / "repositories" / "mixed_stack_fixture"
)


def _base_env(project_root: Path) -> dict[str, str]:
    cache_dir = project_root / ".local" / "uv-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", str(cache_dir))
    return env


def _run_codeman(
    project_root: Path,
    env: dict[str, str],
    *args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "codeman", *args],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )


def test_uv_run_config_profile_can_drive_config_index_query_and_compare(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, target_repo)
    local_model_path = workspace / "local-model"
    local_model_path.mkdir()
    env = _base_env(project_root)
    env["CODEMAN_WORKSPACE_ROOT"] = str(workspace)
    env["CODEMAN_SEMANTIC_PROVIDER_ID"] = "local-hash"
    env["CODEMAN_SEMANTIC_LOCAL_MODEL_PATH"] = str(local_model_path)
    env["CODEMAN_SEMANTIC_MODEL_ID"] = "fixture-local"
    env["CODEMAN_SEMANTIC_MODEL_VERSION"] = "2026-03-14"

    save_profile_result = _run_codeman(
        project_root,
        env,
        "config",
        "profile",
        "save",
        "fixture-profile",
        "--output-format",
        "json",
    )
    config_show_result = _run_codeman(
        project_root,
        env,
        "--profile",
        "fixture-profile",
        "config",
        "show",
        "--output-format",
        "json",
    )
    register_result = _run_codeman(
        project_root,
        env,
        "repo",
        "register",
        str(target_repo),
        "--output-format",
        "json",
    )
    register_payload = json.loads(register_result.stdout)
    repository_id = register_payload["data"]["repository"]["repository_id"]

    snapshot_result = _run_codeman(
        project_root,
        env,
        "repo",
        "snapshot",
        repository_id,
        "--output-format",
        "json",
    )
    snapshot_payload = json.loads(snapshot_result.stdout)
    snapshot_id = snapshot_payload["data"]["snapshot"]["snapshot_id"]

    extract_result = _run_codeman(
        project_root,
        env,
        "index",
        "extract-sources",
        snapshot_id,
        "--output-format",
        "json",
    )
    build_chunks_result = _run_codeman(
        project_root,
        env,
        "index",
        "build-chunks",
        snapshot_id,
        "--output-format",
        "json",
    )
    build_lexical_result = _run_codeman(
        project_root,
        env,
        "index",
        "build-lexical",
        snapshot_id,
        "--output-format",
        "json",
    )
    build_semantic_result = _run_codeman(
        project_root,
        env,
        "--profile",
        "fixture-profile",
        "index",
        "build-semantic",
        snapshot_id,
        "--output-format",
        "json",
    )
    query_semantic_result = _run_codeman(
        project_root,
        env,
        "--profile",
        "fixture-profile",
        "query",
        "semantic",
        repository_id,
        "controller home route",
        "--output-format",
        "json",
    )
    compare_result = _run_codeman(
        project_root,
        env,
        "--profile",
        "fixture-profile",
        "compare",
        "query-modes",
        repository_id,
        "controller home route",
        "--output-format",
        "json",
    )

    save_profile_payload = json.loads(save_profile_result.stdout)
    config_show_payload = json.loads(config_show_result.stdout)
    build_semantic_payload = json.loads(build_semantic_result.stdout)
    query_semantic_payload = json.loads(query_semantic_result.stdout)
    compare_payload = json.loads(compare_result.stdout)

    assert save_profile_result.returncode == 0, save_profile_result.stderr
    assert save_profile_payload["data"]["profile"]["name"] == "fixture-profile"
    assert config_show_result.returncode == 0, config_show_result.stderr
    assert (
        config_show_payload["data"]["metadata"]["selected_profile"]["name"]
        == "fixture-profile"
    )
    assert (
        config_show_payload["data"]["metadata"]["configuration_reuse"]["reuse_kind"]
        == "profile_reuse"
    )
    assert (
        config_show_payload["data"]["metadata"]["configuration_reuse"]["base_profile_id"]
        == config_show_payload["data"]["metadata"]["selected_profile"]["profile_id"]
    )
    assert config_show_payload["data"]["semantic_indexing"]["model_id"] == "fixture-local"
    assert register_result.returncode == 0, register_result.stderr
    assert snapshot_result.returncode == 0, snapshot_result.stderr
    assert extract_result.returncode == 0, extract_result.stderr
    assert build_chunks_result.returncode == 0, build_chunks_result.stderr
    assert build_lexical_result.returncode == 0, build_lexical_result.stderr
    assert build_semantic_result.returncode == 0, build_semantic_result.stderr
    assert build_semantic_payload["data"]["provider"]["provider_id"] == "local-hash"
    assert build_semantic_payload["data"]["build"]["model_version"] == "2026-03-14"
    assert query_semantic_result.returncode == 0, query_semantic_result.stderr
    assert query_semantic_payload["data"]["build"]["provider_id"] == "local-hash"
    assert query_semantic_payload["data"]["build"]["model_version"] == "2026-03-14"
    assert compare_result.returncode == 0, compare_result.stderr
    assert compare_payload["data"]["entries"][1]["build"]["provider_id"] == "local-hash"
    assert compare_payload["data"]["entries"][1]["build"]["model_version"] == "2026-03-14"


def test_uv_run_missing_profile_selection_returns_stable_failure(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    env = _base_env(project_root)
    env["CODEMAN_WORKSPACE_ROOT"] = str(workspace)

    result = _run_codeman(
        project_root,
        env,
        "--profile",
        "missing-profile",
        "config",
        "show",
        "--output-format",
        "json",
    )

    payload = json.loads(result.stdout)
    database_path = workspace / ".codeman" / "metadata.sqlite3"

    assert result.returncode == 55
    assert payload["ok"] is False
    assert payload["error"]["code"] == "configuration_profile_not_found"
    assert "Traceback" not in result.stderr
    assert not database_path.exists()


def test_uv_run_config_profile_list_does_not_create_runtime_metadata_in_clean_workspace(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    env = _base_env(project_root)
    env["CODEMAN_WORKSPACE_ROOT"] = str(workspace)

    result = _run_codeman(
        project_root,
        env,
        "config",
        "profile",
        "list",
        "--output-format",
        "json",
    )

    payload = json.loads(result.stdout)
    database_path = workspace / ".codeman" / "metadata.sqlite3"

    assert result.returncode == 0, result.stderr
    assert payload["ok"] is True
    assert payload["data"]["profiles"] == []
    assert not database_path.exists()


def test_uv_run_config_profile_save_rejects_blank_names_without_runtime_side_effects(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    env = _base_env(project_root)
    env["CODEMAN_WORKSPACE_ROOT"] = str(workspace)

    result = _run_codeman(
        project_root,
        env,
        "config",
        "profile",
        "save",
        "   ",
        "--output-format",
        "json",
    )

    payload = json.loads(result.stdout)
    database_path = workspace / ".codeman" / "metadata.sqlite3"

    assert result.returncode == 18
    assert payload["ok"] is False
    assert payload["error"]["code"] == "configuration_invalid"
    assert payload["error"]["message"] == "Retrieval strategy profile name must not be blank."
    assert not database_path.exists()


def test_uv_run_config_profile_does_not_print_or_persist_provider_secrets(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    local_model_path = workspace / "local-model"
    local_model_path.mkdir()
    env = _base_env(project_root)
    env["CODEMAN_WORKSPACE_ROOT"] = str(workspace)
    env["CODEMAN_SEMANTIC_PROVIDER_ID"] = "local-hash"
    env["CODEMAN_SEMANTIC_LOCAL_MODEL_PATH"] = str(local_model_path)
    env["CODEMAN_SEMANTIC_MODEL_ID"] = "fixture-local"
    env["CODEMAN_SEMANTIC_MODEL_VERSION"] = "2026-03-14"
    env["CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_API_KEY"] = "super-secret"

    save_result = _run_codeman(
        project_root,
        env,
        "config",
        "profile",
        "save",
        "fixture-profile",
        "--output-format",
        "json",
    )
    list_result = _run_codeman(
        project_root,
        env,
        "config",
        "profile",
        "list",
        "--output-format",
        "json",
    )
    show_result = _run_codeman(
        project_root,
        env,
        "config",
        "profile",
        "show",
        "fixture-profile",
        "--output-format",
        "json",
    )

    database_path = workspace / ".codeman" / "metadata.sqlite3"
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "select payload_json from retrieval_strategy_profiles where name = ?",
            ("fixture-profile",),
        ).fetchone()

    assert save_result.returncode == 0, save_result.stderr
    assert list_result.returncode == 0, list_result.stderr
    assert show_result.returncode == 0, show_result.stderr
    assert row is not None
    assert "super-secret" not in save_result.stdout
    assert "super-secret" not in save_result.stderr
    assert "super-secret" not in list_result.stdout
    assert "super-secret" not in list_result.stderr
    assert "super-secret" not in show_result.stdout
    assert "super-secret" not in show_result.stderr
    assert "api_key" not in row[0]
    assert "super-secret" not in row[0]

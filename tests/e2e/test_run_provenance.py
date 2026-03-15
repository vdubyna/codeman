from __future__ import annotations

import json
import os
import shutil
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


def _json_payload(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(result.stdout)


def _save_profile(
    project_root: Path,
    env: dict[str, str],
    *,
    name: str,
    model_version: str,
    indexing_fingerprint_salt: str | None = None,
) -> dict[str, object]:
    profile_env = env.copy()
    profile_env["CODEMAN_SEMANTIC_MODEL_VERSION"] = model_version
    if indexing_fingerprint_salt is not None:
        profile_env["CODEMAN_INDEXING_FINGERPRINT_SALT"] = indexing_fingerprint_salt
    result = _run_codeman(
        project_root,
        profile_env,
        "config",
        "profile",
        "save",
        name,
        "--output-format",
        "json",
    )
    assert result.returncode == 0, result.stderr
    return _json_payload(result)


def _prepare_index_baseline(
    project_root: Path,
    env: dict[str, str],
    *,
    target_repo: Path,
) -> tuple[str, str, dict[str, object]]:
    register_result = _run_codeman(
        project_root,
        env,
        "repo",
        "register",
        str(target_repo),
        "--output-format",
        "json",
    )
    register_payload = _json_payload(register_result)
    assert register_result.returncode == 0, register_result.stderr
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
    snapshot_payload = _json_payload(snapshot_result)
    assert snapshot_result.returncode == 0, snapshot_result.stderr
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
    chunks_result = _run_codeman(
        project_root,
        env,
        "index",
        "build-chunks",
        snapshot_id,
        "--output-format",
        "json",
    )
    lexical_result = _run_codeman(
        project_root,
        env,
        "index",
        "build-lexical",
        snapshot_id,
        "--output-format",
        "json",
    )

    assert extract_result.returncode == 0, extract_result.stderr
    assert chunks_result.returncode == 0, chunks_result.stderr
    assert lexical_result.returncode == 0, lexical_result.stderr

    return repository_id, snapshot_id, _json_payload(lexical_result)


def _show_provenance(
    project_root: Path,
    env: dict[str, str],
    run_id: str,
) -> dict[str, object]:
    result = _run_codeman(
        project_root,
        env,
        "config",
        "provenance",
        "show",
        run_id,
        "--output-format",
        "json",
    )
    assert result.returncode == 0, result.stderr
    return _json_payload(result)


def test_uv_run_provenance_tracks_profile_selected_config_identity_and_component_refs(
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
    runtime_env = env.copy()
    runtime_env.pop("CODEMAN_SEMANTIC_MODEL_VERSION", None)

    alpha_profile = _save_profile(project_root, env, name="alpha", model_version="2026-03-14")
    beta_profile = _save_profile(project_root, env, name="beta", model_version="2026-03-15")
    repository_id, snapshot_id, lexical_payload = _prepare_index_baseline(
        project_root,
        runtime_env,
        target_repo=target_repo,
    )

    build_semantic_alpha_result = _run_codeman(
        project_root,
        runtime_env,
        "--profile",
        "alpha",
        "index",
        "build-semantic",
        snapshot_id,
        "--output-format",
        "json",
    )
    query_semantic_alpha_result = _run_codeman(
        project_root,
        runtime_env,
        "--profile",
        "alpha",
        "query",
        "semantic",
        repository_id,
        "controller home route",
        "--output-format",
        "json",
    )
    query_hybrid_alpha_result = _run_codeman(
        project_root,
        runtime_env,
        "--profile",
        "alpha",
        "query",
        "hybrid",
        repository_id,
        "controller home route",
        "--output-format",
        "json",
    )
    compare_alpha_result = _run_codeman(
        project_root,
        runtime_env,
        "--profile",
        "alpha",
        "compare",
        "query-modes",
        repository_id,
        "controller home route",
        "--output-format",
        "json",
    )
    build_semantic_beta_result = _run_codeman(
        project_root,
        runtime_env,
        "--profile",
        "beta",
        "index",
        "build-semantic",
        snapshot_id,
        "--output-format",
        "json",
    )

    build_semantic_alpha_payload = _json_payload(build_semantic_alpha_result)
    query_semantic_alpha_payload = _json_payload(query_semantic_alpha_result)
    query_hybrid_alpha_payload = _json_payload(query_hybrid_alpha_result)
    compare_alpha_payload = _json_payload(compare_alpha_result)
    build_semantic_beta_payload = _json_payload(build_semantic_beta_result)

    assert build_semantic_alpha_result.returncode == 0, build_semantic_alpha_result.stderr
    assert query_semantic_alpha_result.returncode == 0, query_semantic_alpha_result.stderr
    assert query_hybrid_alpha_result.returncode == 0, query_hybrid_alpha_result.stderr
    assert compare_alpha_result.returncode == 0, compare_alpha_result.stderr
    assert build_semantic_beta_result.returncode == 0, build_semantic_beta_result.stderr

    build_alpha_provenance = _show_provenance(
        project_root,
        runtime_env,
        build_semantic_alpha_payload["data"]["run_id"],
    )
    query_alpha_provenance = _show_provenance(
        project_root,
        runtime_env,
        query_semantic_alpha_payload["data"]["run_id"],
    )
    hybrid_alpha_provenance = _show_provenance(
        project_root,
        runtime_env,
        query_hybrid_alpha_payload["data"]["run_id"],
    )
    compare_alpha_provenance = _show_provenance(
        project_root,
        runtime_env,
        compare_alpha_payload["data"]["run_id"],
    )
    build_beta_provenance = _show_provenance(
        project_root,
        runtime_env,
        build_semantic_beta_payload["data"]["run_id"],
    )

    assert (
        build_alpha_provenance["data"]["provenance"]["configuration_id"]
        == query_alpha_provenance["data"]["provenance"]["configuration_id"]
    )
    assert (
        build_alpha_provenance["data"]["provenance"]["configuration_reuse"]["reuse_kind"]
        == "profile_reuse"
    )
    assert (
        build_alpha_provenance["data"]["provenance"]["configuration_reuse"]["base_profile_id"]
        == alpha_profile["data"]["profile"]["profile_id"]
    )
    assert (
        build_alpha_provenance["data"]["provenance"]["configuration_id"]
        != build_beta_provenance["data"]["provenance"]["configuration_id"]
    )
    assert (
        build_beta_provenance["data"]["provenance"]["configuration_reuse"]["base_profile_id"]
        == beta_profile["data"]["profile"]["profile_id"]
    )
    assert (
        build_alpha_provenance["data"]["provenance"]["effective_config"]["embedding_providers"][
            "local_hash"
        ]["model_version"]
        == "2026-03-14"
    )
    assert (
        build_beta_provenance["data"]["provenance"]["effective_config"]["embedding_providers"][
            "local_hash"
        ]["model_version"]
        == "2026-03-15"
    )
    assert (
        query_alpha_provenance["data"]["provenance"]["workflow_context"]["semantic_build_id"]
        == build_semantic_alpha_payload["data"]["build"]["build_id"]
    )
    assert (
        hybrid_alpha_provenance["data"]["provenance"]["workflow_context"]["lexical_build_id"]
        == lexical_payload["data"]["build"]["build_id"]
    )
    assert (
        hybrid_alpha_provenance["data"]["provenance"]["workflow_context"]["semantic_build_id"]
        == build_semantic_alpha_payload["data"]["build"]["build_id"]
    )
    assert compare_alpha_provenance["data"]["provenance"]["workflow_context"]["compared_modes"] == [
        "lexical",
        "semantic",
        "hybrid",
    ]


def test_uv_run_provenance_marks_modified_profile_reuse_and_requires_matching_lexical_baseline(
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

    stable_profile = _save_profile(project_root, env, name="stable", model_version="2026-03-14")
    _save_profile(
        project_root,
        env,
        name="salted",
        model_version="2026-03-14",
        indexing_fingerprint_salt="profile-v2",
    )
    repository_id, snapshot_id, _ = _prepare_index_baseline(
        project_root,
        env,
        target_repo=target_repo,
    )

    build_semantic_result = _run_codeman(
        project_root,
        env,
        "index",
        "build-semantic",
        snapshot_id,
        "--output-format",
        "json",
    )
    modified_semantic_result = _run_codeman(
        project_root,
        {
            **env,
            "CODEMAN_SEMANTIC_MODEL_VERSION": "2026-03-15",
        },
        "--profile",
        "stable",
        "index",
        "build-semantic",
        snapshot_id,
        "--output-format",
        "json",
    )
    mismatched_lexical_build = _run_codeman(
        project_root,
        {
            **env,
            "CODEMAN_INDEXING_FINGERPRINT_SALT": "cli-override",
        },
        "--profile",
        "stable",
        "index",
        "build-lexical",
        snapshot_id,
        "--output-format",
        "json",
    )
    lexical_failure = _run_codeman(
        project_root,
        env,
        "--profile",
        "salted",
        "query",
        "lexical",
        repository_id,
        "HomeController",
        "--output-format",
        "json",
    )
    hybrid_failure = _run_codeman(
        project_root,
        env,
        "--profile",
        "salted",
        "query",
        "hybrid",
        repository_id,
        "controller home route",
        "--output-format",
        "json",
    )
    compare_failure = _run_codeman(
        project_root,
        env,
        "--profile",
        "salted",
        "compare",
        "query-modes",
        repository_id,
        "controller home route",
        "--output-format",
        "json",
    )

    modified_semantic_payload = _json_payload(modified_semantic_result)
    modified_semantic_provenance = _show_provenance(
        project_root,
        env,
        modified_semantic_payload["data"]["run_id"],
    )
    mismatched_lexical_build_payload = _json_payload(mismatched_lexical_build)
    lexical_failure_payload = _json_payload(lexical_failure)
    hybrid_failure_payload = _json_payload(hybrid_failure)
    compare_failure_payload = _json_payload(compare_failure)

    assert build_semantic_result.returncode == 0, build_semantic_result.stderr
    assert modified_semantic_result.returncode == 0, modified_semantic_result.stderr
    assert (
        modified_semantic_provenance["data"]["provenance"]["configuration_reuse"]["reuse_kind"]
        == "modified_profile_reuse"
    )
    assert (
        modified_semantic_provenance["data"]["provenance"]["configuration_reuse"][
            "base_profile_id"
        ]
        == stable_profile["data"]["profile"]["profile_id"]
    )
    assert (
        modified_semantic_provenance["data"]["provenance"]["configuration_id"]
        != stable_profile["data"]["profile"]["profile_id"]
    )
    assert (
        modified_semantic_provenance["data"]["provenance"]["effective_config"][
            "embedding_providers"
        ]["local_hash"]["model_version"]
        == "2026-03-15"
    )

    assert mismatched_lexical_build.returncode == 34
    assert mismatched_lexical_build_payload["error"]["code"] == "chunk_baseline_missing"
    assert "current configuration" in mismatched_lexical_build_payload["error"]["message"]

    assert lexical_failure.returncode == 38
    assert lexical_failure_payload["error"]["code"] == "lexical_build_baseline_missing"
    assert "current configuration" in lexical_failure_payload["error"]["message"]

    assert hybrid_failure.returncode == 48
    assert hybrid_failure_payload["error"]["code"] == "hybrid_component_baseline_missing"
    assert hybrid_failure_payload["error"]["details"]["component"] == "lexical"

    assert compare_failure.returncode == 52
    assert compare_failure_payload["error"]["code"] == "compare_retrieval_mode_baseline_missing"
    assert compare_failure_payload["error"]["details"]["mode"] == "lexical"

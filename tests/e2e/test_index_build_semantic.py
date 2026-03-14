from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parents[1] / "fixtures" / "repositories" / "mixed_stack_fixture"
)


def prepare_chunked_repository(
    *,
    tmp_path: Path,
    scenario_name: str,
    configure_semantic: bool,
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
    if configure_semantic:
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

    assert register_result.returncode == 0, register_result.stderr
    assert snapshot_result.returncode == 0, snapshot_result.stderr
    assert extract_result.returncode == 0, extract_result.stderr
    assert build_chunks_result.returncode == 0, build_chunks_result.stderr

    return project_root, env, snapshot_id


def test_uv_run_index_build_semantic_supports_text_and_json_output(
    tmp_path: Path,
) -> None:
    text_root, text_env, text_snapshot_id = prepare_chunked_repository(
        tmp_path=tmp_path,
        scenario_name="text",
        configure_semantic=True,
    )
    json_root, json_env, json_snapshot_id = prepare_chunked_repository(
        tmp_path=tmp_path,
        scenario_name="json",
        configure_semantic=True,
    )

    text_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "index",
            "build-semantic",
            text_snapshot_id,
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
            "index",
            "build-semantic",
            json_snapshot_id,
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
    assert "Built semantic index: 8 documents" in text_result.stdout
    assert "Provider: local-hash (local)" in text_result.stdout
    assert "Vector engine: sqlite-exact" in text_result.stdout
    assert payload["ok"] is True
    assert payload["data"]["provider"]["provider_id"] == "local-hash"
    assert payload["data"]["build"]["vector_engine"] == "sqlite-exact"
    assert payload["data"]["diagnostics"]["document_count"] == 8
    assert "Building semantic index for snapshot" in text_result.stderr
    assert "Building semantic index for snapshot" in json_result.stderr


def test_uv_run_index_build_semantic_returns_stable_failure_when_provider_missing(
    tmp_path: Path,
) -> None:
    project_root, env, snapshot_id = prepare_chunked_repository(
        tmp_path=tmp_path,
        scenario_name="failure",
        configure_semantic=False,
    )
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

    payload = json.loads(build_semantic_result.stdout)

    assert build_semantic_result.returncode == 37
    assert payload["ok"] is False
    assert payload["error"]["code"] == "embedding_provider_unavailable"


def test_uv_run_index_build_semantic_returns_stable_failure_for_invalid_vector_dimension(
    tmp_path: Path,
) -> None:
    project_root, env, snapshot_id = prepare_chunked_repository(
        tmp_path=tmp_path,
        scenario_name="invalid-dimension",
        configure_semantic=True,
    )
    env["CODEMAN_SEMANTIC_VECTOR_DIMENSION"] = "abc"

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

    payload = json.loads(build_semantic_result.stdout)

    assert build_semantic_result.returncode == 18
    assert payload["ok"] is False
    assert payload["error"]["code"] == "configuration_invalid"
    assert "CODEMAN_SEMANTIC_VECTOR_DIMENSION" in payload["error"]["message"]
    assert "Traceback" not in build_semantic_result.stderr


def test_uv_run_index_build_semantic_does_not_leak_provider_secrets(
    tmp_path: Path,
) -> None:
    project_root, env, snapshot_id = prepare_chunked_repository(
        tmp_path=tmp_path,
        scenario_name="secret-redaction",
        configure_semantic=True,
    )
    env["CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_API_KEY"] = "super-secret"

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

    payload = json.loads(build_semantic_result.stdout)
    embedding_documents_path = Path(payload["data"]["diagnostics"]["embedding_documents_path"])
    metadata_database_path = Path(env["CODEMAN_WORKSPACE_ROOT"]) / ".codeman" / "metadata.sqlite3"

    assert build_semantic_result.returncode == 0, build_semantic_result.stderr
    assert "super-secret" not in build_semantic_result.stdout
    assert "super-secret" not in build_semantic_result.stderr
    assert "super-secret" not in embedding_documents_path.read_text(encoding="utf-8")
    assert b"super-secret" not in metadata_database_path.read_bytes()

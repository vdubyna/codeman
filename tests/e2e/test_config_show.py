from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def _base_env(project_root: Path) -> dict[str, str]:
    cache_dir = project_root / ".local" / "uv-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", str(cache_dir))
    return env


def test_uv_run_config_show_reports_effective_configuration(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    local_config_path = tmp_path / "codeman.local.toml"
    local_config_path.write_text(
        """
[runtime]
root_dir_name = ".local-runtime"

[semantic_indexing]
model_version = "local-version"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    env = _base_env(project_root)
    env["CODEMAN_RUNTIME_ROOT_DIR"] = ".env-runtime"
    env["CODEMAN_SEMANTIC_MODEL_VERSION"] = "env-version"

    result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "--config-path",
            str(local_config_path),
            "--workspace-root",
            str(workspace),
            "config",
            "show",
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )

    payload = json.loads(result.stdout)

    assert result.returncode == 0, result.stderr
    assert payload["ok"] is True
    assert payload["data"]["runtime"]["workspace_root"] == str(workspace.resolve())
    assert payload["data"]["runtime"]["root_dir_name"] == ".env-runtime"
    assert payload["data"]["semantic_indexing"]["model_version"] == "env-version"
    assert payload["data"]["embedding_providers"]["local_hash"]["model_version"] == "env-version"
    assert payload["data"]["metadata"]["local_config_present"] is True


def test_uv_run_config_show_redacts_provider_secrets(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    env = _base_env(project_root)
    env["CODEMAN_WORKSPACE_ROOT"] = str(workspace)
    env["CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_API_KEY"] = "super-secret"

    result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "config",
            "show",
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )

    payload = json.loads(result.stdout)

    assert result.returncode == 0, result.stderr
    assert payload["data"]["embedding_providers"]["local_hash"]["api_key_configured"] is True
    assert "api_key" not in payload["data"]["embedding_providers"]["local_hash"]
    assert "super-secret" not in result.stdout
    assert "super-secret" not in result.stderr


def test_invalid_configuration_fails_before_repo_workflow_starts(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    env = _base_env(project_root)
    env["CODEMAN_WORKSPACE_ROOT"] = str(workspace)
    env["CODEMAN_SEMANTIC_VECTOR_DIMENSION"] = "abc"

    result = subprocess.run(
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

    payload = json.loads(result.stdout)

    assert result.returncode == 18
    assert payload["ok"] is False
    assert payload["error"]["code"] == "configuration_invalid"
    assert not (workspace / ".codeman" / "metadata.sqlite3").exists()
    assert "Traceback" not in result.stderr


def test_explicit_env_config_path_missing_returns_stable_failure(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    env = _base_env(project_root)
    env["CODEMAN_CONFIG_PATH"] = str(tmp_path / "missing-config.toml")

    result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "config",
            "show",
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )

    payload = json.loads(result.stdout)

    assert result.returncode == 18
    assert payload["ok"] is False
    assert payload["error"]["code"] == "configuration_invalid"
    assert "missing-config.toml" in payload["error"]["message"]

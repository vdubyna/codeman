from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def test_uv_run_repo_register_succeeds(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    cache_dir = project_root / ".local" / "uv-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", str(cache_dir))
    env["CODEMAN_WORKSPACE_ROOT"] = str(workspace)

    result = subprocess.run(
        ["uv", "run", "codeman", "repo", "register", str(target_repo)],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "Registered repository" in result.stdout
    assert (workspace / ".codeman" / "metadata.sqlite3").exists()


def test_uv_run_repo_register_missing_path_returns_json_failure(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    missing_repo = tmp_path / "missing-repo"
    cache_dir = project_root / ".local" / "uv-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", str(cache_dir))
    env["CODEMAN_WORKSPACE_ROOT"] = str(workspace)

    result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "repo",
            "register",
            str(missing_repo),
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

    assert result.returncode == 20
    assert payload["ok"] is False
    assert payload["error"]["code"] == "repository_path_not_found"
    assert not (workspace / ".codeman" / "metadata.sqlite3").exists()

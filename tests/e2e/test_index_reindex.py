from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "repositories"
    / "mixed_stack_fixture"
)


def prepare_reindex_scenario(
    *,
    tmp_path: Path,
    scenario_name: str,
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
    build_result = subprocess.run(
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
    assert build_result.returncode == 0, build_result.stderr

    return target_repo, env, repository_id


def test_uv_run_index_reindex_supports_text_and_json_output(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    text_repo, text_env, text_repository_id = prepare_reindex_scenario(
        tmp_path=tmp_path,
        scenario_name="text",
    )
    json_repo, json_env, json_repository_id = prepare_reindex_scenario(
        tmp_path=tmp_path,
        scenario_name="json",
    )

    (text_repo / "assets" / "app.js").write_text(
        'export function boot() {\n  return "reindexed";\n}\n',
        encoding="utf-8",
    )
    (json_repo / "assets" / "app.js").write_text(
        'export function boot() {\n  return "reindexed";\n}\n',
        encoding="utf-8",
    )

    text_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "index",
            "reindex",
            text_repository_id,
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=text_env,
    )
    json_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "index",
            "reindex",
            json_repository_id,
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=json_env,
    )

    payload = json.loads(json_result.stdout)

    assert text_result.returncode == 0, text_result.stderr
    assert json_result.returncode == 0, json_result.stderr
    assert "Change reason: source_changed" in text_result.stdout
    assert "Source files rebuilt: 1" in text_result.stdout
    assert payload["ok"] is True
    assert payload["data"]["change_reason"] == "source_changed"
    assert payload["data"]["source_files_reused"] == 4
    assert payload["data"]["source_files_rebuilt"] == 1
    assert payload["data"]["chunks_reused"] == 7
    assert payload["data"]["chunks_rebuilt"] == 1
    assert "Re-indexing repository" in text_result.stderr
    assert "Re-indexing repository" in json_result.stderr

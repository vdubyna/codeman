from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parents[1] / "fixtures" / "repositories" / "mixed_stack_fixture"
)


def test_uv_run_index_build_chunks_supports_text_and_json_output(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
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

    snapshot_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "repo",
            "snapshot",
            register_payload["data"]["repository"]["repository_id"],
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

    extract_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "index",
            "extract-sources",
            snapshot_payload["data"]["snapshot"]["snapshot_id"],
            "--output-format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )

    text_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "index",
            "build-chunks",
            snapshot_payload["data"]["snapshot"]["snapshot_id"],
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
            "index",
            "build-chunks",
            snapshot_payload["data"]["snapshot"]["snapshot_id"],
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

    assert register_result.returncode == 0, register_result.stderr
    assert snapshot_result.returncode == 0, snapshot_result.stderr
    assert extract_result.returncode == 0, extract_result.stderr
    assert text_result.returncode == 0, text_result.stderr
    assert json_result.returncode == 0, json_result.stderr
    assert "Generated retrieval chunks: 8 chunks" in text_result.stdout
    assert "Files using fallback: 1" in text_result.stdout
    assert "Parser cache reused/regenerated: 0/4" in text_result.stdout
    assert "Chunk cache reused/regenerated: 0/5" in text_result.stdout
    assert payload["ok"] is True
    assert payload["data"]["diagnostics"]["total_chunks"] == 8
    assert payload["data"]["diagnostics"]["fallback_file_count"] == 1
    assert payload["data"]["diagnostics"]["cache_summary"]["parser_entries_reused"] == 0
    assert payload["data"]["diagnostics"]["cache_summary"]["parser_entries_regenerated"] == 0
    assert payload["data"]["diagnostics"]["cache_summary"]["chunk_entries_reused"] == 5
    assert payload["data"]["diagnostics"]["cache_summary"]["chunk_entries_regenerated"] == 0
    assert payload["data"]["diagnostics"]["chunks_by_strategy"] == {
        "html_structure": 2,
        "javascript_fallback": 1,
        "javascript_structure": 1,
        "php_structure": 2,
        "twig_structure": 2,
    }
    assert "Generating chunks for snapshot" in text_result.stderr
    assert "Generating chunks for snapshot" in json_result.stderr


def test_uv_run_index_build_chunks_reports_cache_reuse_on_second_run(
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
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
    repository_id = json.loads(register_result.stdout)["data"]["repository"]["repository_id"]
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
    snapshot_id = json.loads(snapshot_result.stdout)["data"]["snapshot"]["snapshot_id"]
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
    first_result = subprocess.run(
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
    second_result = subprocess.run(
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

    first_payload = json.loads(first_result.stdout)
    second_payload = json.loads(second_result.stdout)

    assert register_result.returncode == 0, register_result.stderr
    assert snapshot_result.returncode == 0, snapshot_result.stderr
    assert extract_result.returncode == 0, extract_result.stderr
    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    assert first_payload["data"]["diagnostics"]["cache_summary"]["chunk_entries_regenerated"] == 5
    assert second_payload["data"]["diagnostics"]["cache_summary"]["chunk_entries_reused"] == 5
    assert second_payload["data"]["diagnostics"]["cache_summary"]["chunk_entries_regenerated"] == 0

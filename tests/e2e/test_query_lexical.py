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


def prepare_lexical_repository(
    *,
    tmp_path: Path,
    scenario_name: str,
    extra_source: tuple[str, str] | None = None,
) -> tuple[Path, dict[str, str], str]:
    project_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / f"{scenario_name}-workspace"
    workspace.mkdir()
    target_repo = tmp_path / f"{scenario_name}-registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, target_repo)
    if extra_source is not None:
        relative_path, content = extra_source
        target_file = target_repo / relative_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content, encoding="utf-8")
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

    return project_root, env, repository_id


def prepare_chunked_repository_without_lexical(
    *,
    tmp_path: Path,
) -> tuple[Path, dict[str, str], str]:
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

    return project_root, env, repository_id


def test_uv_run_query_lexical_supports_text_and_json_output(tmp_path: Path) -> None:
    text_root, text_env, text_repository_id = prepare_lexical_repository(
        tmp_path=tmp_path,
        scenario_name="text",
    )
    json_root, json_env, json_repository_id = prepare_lexical_repository(
        tmp_path=tmp_path,
        scenario_name="json",
    )

    text_result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "query",
            "lexical",
            text_repository_id,
            "HomeController",
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
            "query",
            "lexical",
            json_repository_id,
            "HomeController",
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
    assert "Lexical query matched" in text_result.stdout
    assert "src/Controller/HomeController.php" in text_result.stdout
    assert payload["ok"] is True
    assert payload["data"]["query"] == "HomeController"
    assert payload["data"]["diagnostics"]["match_count"] >= 1
    assert any(
        match["relative_path"] == "src/Controller/HomeController.php"
        for match in payload["data"]["matches"]
    )
    assert "Running lexical query for repository" in text_result.stderr
    assert "Running lexical query for repository" in json_result.stderr


def test_uv_run_query_lexical_returns_stable_failure_when_build_is_missing(
    tmp_path: Path,
) -> None:
    project_root, env, repository_id = prepare_chunked_repository_without_lexical(
        tmp_path=tmp_path,
    )

    result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "query",
            "lexical",
            repository_id,
            "HomeController",
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

    assert result.returncode == 38
    assert payload["ok"] is False
    assert payload["error"]["code"] == "lexical_build_baseline_missing"
    assert payload["meta"]["command"] == "query.lexical"
    assert "Running lexical query for repository" in result.stderr


def test_uv_run_query_lexical_accepts_option_like_query_values(tmp_path: Path) -> None:
    project_root, env, repository_id = prepare_lexical_repository(
        tmp_path=tmp_path,
        scenario_name="flag-like-query",
        extra_source=(
            "assets/flags.js",
            'export const flag = "--output-format";\n',
        ),
    )

    result = subprocess.run(
        [
            "uv",
            "run",
            "codeman",
            "query",
            "lexical",
            repository_id,
            "--query=--output-format",
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
    assert payload["data"]["query"] == "--output-format"
    assert any(
        match["relative_path"] == "assets/flags.js"
        for match in payload["data"]["matches"]
    )

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codeman.application.repo.register_repository import RepositoryPathNotReadableError
from codeman.bootstrap import bootstrap
from codeman.cli.app import app

runner = CliRunner()


def test_repo_register_command_registers_repository_in_text_mode(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()

    result = runner.invoke(
        app,
        ["repo", "register", str(target_repo)],
        obj=bootstrap(workspace_root=workspace),
    )

    assert result.exit_code == 0, result.stdout
    assert "Registered repository" in result.stdout
    assert str(target_repo.resolve()) in result.stdout
    assert (workspace / ".codeman" / "metadata.sqlite3").exists()


def test_repo_register_command_returns_json_failure_for_missing_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    missing_repo = tmp_path / "missing-repo"

    result = runner.invoke(
        app,
        ["repo", "register", str(missing_repo), "--output-format", "json"],
        obj=bootstrap(workspace_root=workspace),
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 20
    assert payload["ok"] is False
    assert payload["error"]["code"] == "repository_path_not_found"
    assert not (workspace / ".codeman" / "metadata.sqlite3").exists()


def test_repo_register_command_returns_json_failure_for_non_directory_path(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    not_a_directory = tmp_path / "plain-file.txt"
    not_a_directory.write_text("content", encoding="utf-8")

    result = runner.invoke(
        app,
        ["repo", "register", str(not_a_directory), "--output-format", "json"],
        obj=bootstrap(workspace_root=workspace),
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 21
    assert payload["ok"] is False
    assert payload["error"]["code"] == "repository_path_not_directory"
    assert not (workspace / ".codeman" / "metadata.sqlite3").exists()


def test_repo_register_command_returns_json_failure_for_unreadable_path(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    unreadable_repo = tmp_path / "unreadable-repo"
    unreadable_repo.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubRegisterRepositoryUseCase:
        def execute(self, _request: object) -> object:
            raise RepositoryPathNotReadableError(
                f"Repository path is not readable: {unreadable_repo.resolve()}",
            )

    container.register_repository = StubRegisterRepositoryUseCase()

    result = runner.invoke(
        app,
        ["repo", "register", str(unreadable_repo), "--output-format", "json"],
        obj=container,
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 22
    assert payload["ok"] is False
    assert payload["error"]["code"] == "repository_path_not_readable"
    assert not (workspace / ".codeman" / "metadata.sqlite3").exists()

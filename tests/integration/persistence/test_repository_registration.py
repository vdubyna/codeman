from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from codeman.application.repo.register_repository import RepositoryPathNotFoundError
from codeman.bootstrap import bootstrap
from codeman.contracts.repository import RegisterRepositoryRequest


def test_register_repository_persists_metadata_and_runtime_directories(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)

    result = container.register_repository.execute(
        RegisterRepositoryRequest(repository_path=target_repo),
    )

    db_path = result.metadata_database_path
    row = (
        sqlite3.connect(db_path)
        .execute(
            "SELECT repository_name, canonical_path, requested_path FROM repositories",
        )
        .fetchone()
    )

    assert db_path.exists()
    assert row == (
        target_repo.name,
        str(target_repo.resolve()),
        str(target_repo.resolve()),
    )
    assert result.runtime_root.is_dir()
    assert (workspace / ".codeman" / "artifacts").is_dir()
    assert (workspace / ".codeman" / "indexes").is_dir()
    assert (workspace / ".codeman" / "cache").is_dir()
    assert (workspace / ".codeman" / "logs").is_dir()
    assert (workspace / ".codeman" / "tmp").is_dir()


def test_register_repository_initializes_existing_empty_metadata_database(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    runtime_root = workspace / ".codeman"
    workspace.mkdir()
    runtime_root.mkdir()
    (runtime_root / "metadata.sqlite3").touch()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)

    result = container.register_repository.execute(
        RegisterRepositoryRequest(repository_path=target_repo),
    )

    row = (
        sqlite3.connect(result.metadata_database_path)
        .execute(
            "SELECT repository_name, canonical_path FROM repositories",
        )
        .fetchone()
    )

    assert row == (target_repo.name, str(target_repo.resolve()))


def test_register_repository_invalid_path_does_not_persist_row(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    missing_repo = tmp_path / "missing-repo"
    container = bootstrap(workspace_root=workspace)

    with pytest.raises(RepositoryPathNotFoundError):
        container.register_repository.execute(
            RegisterRepositoryRequest(repository_path=missing_repo),
        )

    assert not (workspace / ".codeman" / "metadata.sqlite3").exists()

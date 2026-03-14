from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from codeman.application.repo import register_repository as register_repository_module
from codeman.application.repo.register_repository import (
    RegisterRepositoryUseCase,
    RepositoryAlreadyRegisteredError,
    RepositoryPathNotDirectoryError,
    RepositoryPathNotFoundError,
    RepositoryPathNotReadableError,
)
from codeman.contracts.repository import RegisterRepositoryRequest, RepositoryRecord
from codeman.runtime import build_runtime_paths


@dataclass
class FakeRepositoryStore:
    initialized: int = 0
    records: dict[Path, RepositoryRecord] = field(default_factory=dict)

    def initialize(self) -> None:
        self.initialized += 1

    def get_by_canonical_path(self, canonical_path: Path) -> RepositoryRecord | None:
        return self.records.get(canonical_path)

    def create_repository(
        self,
        *,
        repository_name: str,
        canonical_path: Path,
        requested_path: Path,
    ) -> RepositoryRecord:
        record = RepositoryRecord(
            repository_id=uuid4().hex,
            repository_name=repository_name,
            canonical_path=canonical_path,
            requested_path=requested_path,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.records[canonical_path] = record
        return record


def test_register_repository_provisions_runtime_and_returns_canonical_record(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    store = FakeRepositoryStore()
    use_case = RegisterRepositoryUseCase(
        runtime_paths=build_runtime_paths(workspace),
        metadata_store=store,
    )

    result = use_case.execute(
        RegisterRepositoryRequest(repository_path=target_repo / "."),  # canonicalization check
    )

    assert store.initialized == 1
    assert result.repository.canonical_path == target_repo.resolve()
    assert result.repository.requested_path == target_repo.resolve()
    assert result.runtime_root == workspace / ".codeman"
    assert result.metadata_database_path == workspace / ".codeman" / "metadata.sqlite3"
    assert result.runtime_root.is_dir()


def test_register_repository_rejects_missing_path_before_store_initialization(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    missing_repo = tmp_path / "missing-repo"
    store = FakeRepositoryStore()
    use_case = RegisterRepositoryUseCase(
        runtime_paths=build_runtime_paths(workspace),
        metadata_store=store,
    )

    with pytest.raises(RepositoryPathNotFoundError):
        use_case.execute(RegisterRepositoryRequest(repository_path=missing_repo))

    assert store.initialized == 0
    assert not (workspace / ".codeman").exists()


def test_register_repository_rejects_non_directory_path_before_store_initialization(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    not_a_directory = tmp_path / "plain-file.txt"
    not_a_directory.write_text("content", encoding="utf-8")
    store = FakeRepositoryStore()
    use_case = RegisterRepositoryUseCase(
        runtime_paths=build_runtime_paths(workspace),
        metadata_store=store,
    )

    with pytest.raises(RepositoryPathNotDirectoryError):
        use_case.execute(RegisterRepositoryRequest(repository_path=not_a_directory))

    assert store.initialized == 0
    assert not (workspace / ".codeman").exists()


def test_register_repository_rejects_unreadable_path_before_store_initialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    unreadable_repo = tmp_path / "unreadable-repo"
    unreadable_repo.mkdir()
    store = FakeRepositoryStore()
    use_case = RegisterRepositoryUseCase(
        runtime_paths=build_runtime_paths(workspace),
        metadata_store=store,
    )
    original_access = register_repository_module.os.access

    monkeypatch.setattr(
        register_repository_module.os,
        "access",
        lambda path, mode: False
        if Path(path) == unreadable_repo.resolve()
        else original_access(path, mode),
    )

    with pytest.raises(RepositoryPathNotReadableError):
        use_case.execute(RegisterRepositoryRequest(repository_path=unreadable_repo))

    assert store.initialized == 0
    assert not (workspace / ".codeman").exists()


def test_register_repository_rejects_duplicate_canonical_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    store = FakeRepositoryStore()
    use_case = RegisterRepositoryUseCase(
        runtime_paths=build_runtime_paths(workspace),
        metadata_store=store,
    )

    use_case.execute(RegisterRepositoryRequest(repository_path=target_repo))

    with pytest.raises(RepositoryAlreadyRegisteredError):
        use_case.execute(RegisterRepositoryRequest(repository_path=target_repo / "."))

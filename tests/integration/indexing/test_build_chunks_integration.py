from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from codeman.bootstrap import bootstrap
from codeman.contracts.chunking import BuildChunksRequest
from codeman.contracts.repository import (
    CreateSnapshotRequest,
    ExtractSourceFilesRequest,
    RegisterRepositoryRequest,
)

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parents[2] / "fixtures" / "repositories" / "mixed_stack_fixture"
)


def prepare_extracted_repository(
    *,
    workspace: Path,
    repository_path: Path,
) -> tuple[object, str]:
    container = bootstrap(workspace_root=workspace)
    registration = container.register_repository.execute(
        RegisterRepositoryRequest(repository_path=repository_path),
    )
    snapshot = container.create_snapshot.execute(
        CreateSnapshotRequest(repository_id=registration.repository.repository_id),
    )
    container.extract_source_files.execute(
        ExtractSourceFilesRequest(snapshot_id=snapshot.snapshot.snapshot_id),
    )
    return container, snapshot.snapshot.snapshot_id


def test_build_chunks_reuses_cache_for_same_snapshot_and_configuration(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    first_container, snapshot_id = prepare_extracted_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    first = first_container.build_chunks.execute(BuildChunksRequest(snapshot_id=snapshot_id))

    second_container = bootstrap(workspace_root=workspace)
    second = second_container.build_chunks.execute(BuildChunksRequest(snapshot_id=snapshot_id))

    assert first.diagnostics.cache_summary.chunk_entries_regenerated > 0
    assert second.diagnostics.total_chunks == first.diagnostics.total_chunks
    assert second.diagnostics.cache_summary.chunk_entries_reused > 0
    assert second.diagnostics.cache_summary.chunk_entries_regenerated == 0


def test_build_chunks_invalidates_cache_when_current_indexing_configuration_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    first_container, snapshot_id = prepare_extracted_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    first = first_container.build_chunks.execute(BuildChunksRequest(snapshot_id=snapshot_id))

    monkeypatch.setenv("CODEMAN_INDEXING_FINGERPRINT_SALT", "profile-v2")
    second_container = bootstrap(workspace_root=workspace)
    second = second_container.build_chunks.execute(BuildChunksRequest(snapshot_id=snapshot_id))

    assert first.diagnostics.cache_summary.chunk_entries_regenerated > 0
    assert second.diagnostics.cache_summary.chunk_entries_reused == 0
    assert second.diagnostics.cache_summary.chunk_entries_regenerated > 0

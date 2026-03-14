from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from codeman.application.repo.reindex_repository import IndexedBaselineMissingError
from codeman.bootstrap import bootstrap
from codeman.contracts.chunking import BuildChunksRequest
from codeman.contracts.reindexing import ReindexRepositoryRequest
from codeman.contracts.repository import (
    CreateSnapshotRequest,
    ExtractSourceFilesRequest,
    RegisterRepositoryRequest,
)

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "repositories"
    / "mixed_stack_fixture"
)


def prepare_indexed_repository(
    *,
    workspace: Path,
    repository_path: Path,
) -> tuple[object, str, str]:
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
    container.build_chunks.execute(
        BuildChunksRequest(snapshot_id=snapshot.snapshot.snapshot_id),
    )
    return (
        container,
        registration.repository.repository_id,
        snapshot.snapshot.snapshot_id,
    )


def test_reindex_persists_noop_run_without_creating_a_new_snapshot(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, baseline_snapshot_id = prepare_indexed_repository(
        workspace=workspace,
        repository_path=repository_path,
    )

    result = container.reindex_repository.execute(
        ReindexRepositoryRequest(repository_id=repository_id),
    )

    database_path = workspace / ".codeman" / "metadata.sqlite3"
    connection = sqlite3.connect(database_path)
    snapshot_count = connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    reindex_row = connection.execute(
        """
        SELECT
            previous_snapshot_id,
            result_snapshot_id,
            change_reason,
            chunks_reused,
            chunks_rebuilt
        FROM reindex_runs
        """,
    ).fetchone()

    assert result.noop is True
    assert result.previous_snapshot_id == baseline_snapshot_id
    assert result.result_snapshot_id == baseline_snapshot_id
    assert snapshot_count == 1
    assert reindex_row == (
        baseline_snapshot_id,
        baseline_snapshot_id,
        "no_change",
        8,
        0,
    )


def test_reindex_treats_unsupported_only_revision_changes_as_true_noop(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, baseline_snapshot_id = prepare_indexed_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    (repository_path / "README.md").write_text("docs-only change\n", encoding="utf-8")

    result = container.reindex_repository.execute(
        ReindexRepositoryRequest(repository_id=repository_id),
    )

    database_path = workspace / ".codeman" / "metadata.sqlite3"
    connection = sqlite3.connect(database_path)
    snapshot_count = connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    reindex_row = connection.execute(
        """
        SELECT
            previous_snapshot_id,
            result_snapshot_id,
            previous_revision_identity,
            result_revision_identity,
            change_reason
        FROM reindex_runs
        """,
    ).fetchone()

    assert result.noop is True
    assert result.change_reason == "no_change"
    assert result.previous_snapshot_id == baseline_snapshot_id
    assert result.result_snapshot_id == baseline_snapshot_id
    assert result.previous_revision_identity != result.result_revision_identity
    assert snapshot_count == 1
    assert reindex_row == (
        baseline_snapshot_id,
        baseline_snapshot_id,
        result.previous_revision_identity,
        result.result_revision_identity,
        "no_change",
    )


def test_reindex_creates_new_snapshot_reuses_unchanged_chunks_and_drops_removed_files(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, baseline_snapshot_id = prepare_indexed_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    (repository_path / "assets" / "app.js").write_text(
        'export function boot() {\n  return "changed";\n}\n',
        encoding="utf-8",
    )
    (repository_path / "templates" / "page.html.twig").unlink()

    result = container.reindex_repository.execute(
        ReindexRepositoryRequest(repository_id=repository_id),
    )

    database_path = workspace / ".codeman" / "metadata.sqlite3"
    connection = sqlite3.connect(database_path)
    snapshot_count = connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    result_rows = connection.execute(
        """
        SELECT relative_path
        FROM chunks
        WHERE snapshot_id = ?
        ORDER BY relative_path, start_line, start_byte
        """,
        (result.result_snapshot_id,),
    ).fetchall()
    reindex_row = connection.execute(
        """
        SELECT
            source_files_reused,
            source_files_rebuilt,
            source_files_removed,
            chunks_reused,
            chunks_rebuilt
        FROM reindex_runs
        WHERE result_snapshot_id = ?
        """,
        (result.result_snapshot_id,),
    ).fetchone()

    assert result.noop is False
    assert result.change_reason == "source_changed"
    assert result.previous_snapshot_id == baseline_snapshot_id
    assert result.result_snapshot_id != baseline_snapshot_id
    assert result.diagnostics.source_files_reused == 3
    assert result.diagnostics.source_files_rebuilt == 1
    assert result.diagnostics.source_files_removed == 1
    assert result.diagnostics.chunks_reused == 5
    assert result.diagnostics.chunks_rebuilt == 1
    assert result.diagnostics.chunks_removed == 2
    assert snapshot_count == 2
    assert [row[0] for row in result_rows] == [
        "assets/app.js",
        "assets/broken.js",
        "public/index.html",
        "public/index.html",
        "src/Controller/HomeController.php",
        "src/Controller/HomeController.php",
    ]
    assert reindex_row == (3, 1, 1, 5, 1)


def test_reindex_requires_an_indexed_baseline_even_for_empty_repositories(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()

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

    with pytest.raises(IndexedBaselineMissingError):
        container.reindex_repository.execute(
            ReindexRepositoryRequest(repository_id=registration.repository.repository_id),
        )

    database_path = workspace / ".codeman" / "metadata.sqlite3"
    connection = sqlite3.connect(database_path)
    snapshot_count = connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    run_count = connection.execute("SELECT COUNT(*) FROM reindex_runs").fetchone()[0]

    assert snapshot_count == 1
    assert run_count == 0


def test_reindex_rebuilds_all_chunks_when_config_fingerprint_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    _, repository_id, baseline_snapshot_id = prepare_indexed_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    monkeypatch.setenv("CODEMAN_INDEXING_FINGERPRINT_SALT", "v2")
    container = bootstrap(workspace_root=workspace)

    result = container.reindex_repository.execute(
        ReindexRepositoryRequest(repository_id=repository_id),
    )

    database_path = workspace / ".codeman" / "metadata.sqlite3"
    connection = sqlite3.connect(database_path)
    baseline_chunk_count = connection.execute(
        "SELECT COUNT(*) FROM chunks WHERE snapshot_id = ?",
        (baseline_snapshot_id,),
    ).fetchone()[0]
    result_chunk_count = connection.execute(
        "SELECT COUNT(*) FROM chunks WHERE snapshot_id = ?",
        (result.result_snapshot_id,),
    ).fetchone()[0]

    assert result.noop is False
    assert result.change_reason == "config_changed"
    assert result.result_snapshot_id != baseline_snapshot_id
    assert result.diagnostics.source_files_reused == 0
    assert result.diagnostics.source_files_rebuilt == 5
    assert result.diagnostics.source_files_invalidated_by_config == 5
    assert result.diagnostics.chunks_reused == 0
    assert result.diagnostics.chunks_rebuilt == 8
    assert result.diagnostics.chunks_invalidated_by_config == 8
    assert baseline_chunk_count == 8
    assert result_chunk_count == 8

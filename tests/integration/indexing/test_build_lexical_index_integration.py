from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from codeman.bootstrap import bootstrap
from codeman.contracts.chunking import BuildChunksRequest
from codeman.contracts.reindexing import ReindexRepositoryRequest
from codeman.contracts.repository import (
    CreateSnapshotRequest,
    ExtractSourceFilesRequest,
    RegisterRepositoryRequest,
)
from codeman.contracts.retrieval import BuildLexicalIndexRequest

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


def test_build_lexical_index_refreshes_same_snapshot_artifact_atomically(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, _, snapshot_id = prepare_indexed_repository(
        workspace=workspace,
        repository_path=repository_path,
    )

    first_result = container.build_lexical_index.execute(
        BuildLexicalIndexRequest(snapshot_id=snapshot_id),
    )
    first_result.build.index_path.write_bytes(b"stale lexical artifact")

    second_result = container.build_lexical_index.execute(
        BuildLexicalIndexRequest(snapshot_id=snapshot_id),
    )

    metadata_database_path = workspace / ".codeman" / "metadata.sqlite3"
    connection = sqlite3.connect(second_result.build.index_path)
    indexed_chunk_count = connection.execute(
        "SELECT COUNT(*) FROM lexical_chunks",
    ).fetchone()[0]
    metadata_connection = sqlite3.connect(metadata_database_path)
    build_rows = metadata_connection.execute(
        """
        SELECT id, snapshot_id, index_path
        FROM lexical_index_builds
        WHERE snapshot_id = ?
        ORDER BY created_at ASC
        """,
        (snapshot_id,),
    ).fetchall()

    assert first_result.build.index_path == second_result.build.index_path
    assert indexed_chunk_count == 8
    assert len(build_rows) == 2
    assert build_rows[0][0] != build_rows[1][0]
    assert all(row[1] == snapshot_id for row in build_rows)
    assert all(row[2] == str(second_result.build.index_path) for row in build_rows)


def test_build_lexical_index_after_reindex_creates_new_snapshot_scoped_artifact(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, snapshot_id = prepare_indexed_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    baseline_build = container.build_lexical_index.execute(
        BuildLexicalIndexRequest(snapshot_id=snapshot_id),
    )
    (repository_path / "assets" / "app.js").write_text(
        'export function boot() {\n  return "fresh";\n}\n',
        encoding="utf-8",
    )

    reindex_result = container.reindex_repository.execute(
        ReindexRepositoryRequest(repository_id=repository_id),
    )
    stale_lookup = container.index_build_store.get_latest_build_for_repository(
        repository_id,
    )
    refreshed_build = container.build_lexical_index.execute(
        BuildLexicalIndexRequest(snapshot_id=reindex_result.result_snapshot_id),
    )
    latest_lookup = container.index_build_store.get_latest_build_for_repository(
        repository_id,
    )

    metadata_database_path = workspace / ".codeman" / "metadata.sqlite3"
    metadata_connection = sqlite3.connect(metadata_database_path)
    build_rows = metadata_connection.execute(
        """
        SELECT snapshot_id, index_path
        FROM lexical_index_builds
        WHERE repository_id = ?
        ORDER BY created_at ASC
        """,
        (repository_id,),
    ).fetchall()

    assert baseline_build.build.snapshot_id == snapshot_id
    assert refreshed_build.build.snapshot_id == reindex_result.result_snapshot_id
    assert baseline_build.build.snapshot_id != refreshed_build.build.snapshot_id
    assert stale_lookup is None
    assert latest_lookup is not None
    assert latest_lookup.snapshot_id == refreshed_build.build.snapshot_id
    assert baseline_build.build.index_path != refreshed_build.build.index_path
    assert baseline_build.build.index_path.exists()
    assert refreshed_build.build.index_path.exists()
    assert build_rows == [
        (baseline_build.build.snapshot_id, str(baseline_build.build.index_path)),
        (refreshed_build.build.snapshot_id, str(refreshed_build.build.index_path)),
    ]

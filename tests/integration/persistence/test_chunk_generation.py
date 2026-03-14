from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from codeman.bootstrap import bootstrap
from codeman.contracts.chunking import BuildChunksRequest
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


def test_build_chunks_creates_chunk_rows_and_payload_artifacts_via_alembic(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

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

    first = container.build_chunks.execute(
        BuildChunksRequest(snapshot_id=snapshot.snapshot.snapshot_id),
    )
    second = container.build_chunks.execute(
        BuildChunksRequest(snapshot_id=snapshot.snapshot.snapshot_id),
    )

    database_path = workspace / ".codeman" / "metadata.sqlite3"
    connection = sqlite3.connect(database_path)
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'",
        ).fetchall()
    }
    rows = connection.execute(
        """
        SELECT relative_path, strategy, start_line, end_line
        FROM chunks
        ORDER BY relative_path, start_line, start_byte
        """,
    ).fetchall()
    row_count = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    assert "chunks" in tables
    assert first.diagnostics.total_chunks == 8
    assert second.diagnostics.total_chunks == 8
    assert first.diagnostics.fallback_file_count == 1
    assert row_count == 8
    assert rows == [
        ("assets/app.js", "javascript_structure", 1, 3),
        ("assets/broken.js", "javascript_fallback", 1, 2),
        ("public/index.html", "html_structure", 1, 3),
        ("public/index.html", "html_structure", 4, 6),
        ("src/Controller/HomeController.php", "php_structure", 1, 6),
        ("src/Controller/HomeController.php", "php_structure", 7, 11),
        ("templates/page.html.twig", "twig_structure", 1, 2),
        ("templates/page.html.twig", "twig_structure", 3, 5),
    ]

    artifacts_root = (
        workspace
        / ".codeman"
        / "artifacts"
        / "snapshots"
        / snapshot.snapshot.snapshot_id
        / "chunks"
    )
    payload_files = sorted(path.name for path in artifacts_root.glob("*.json"))
    assert len(payload_files) == 8
    assert all(chunk.payload_path.exists() for chunk in first.chunks)

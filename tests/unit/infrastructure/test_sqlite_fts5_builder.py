from __future__ import annotations

import sqlite3
from pathlib import Path

from codeman.contracts.retrieval import LexicalIndexDocument
from codeman.infrastructure.indexes.lexical.sqlite_fts5_builder import (
    SqliteFts5LexicalIndexBuilder,
)
from codeman.runtime import build_runtime_paths


def build_documents() -> list[LexicalIndexDocument]:
    return [
        LexicalIndexDocument(
            chunk_id="chunk-1",
            snapshot_id="snapshot-123",
            repository_id="repo-123",
            relative_path="assets/app.js",
            language="javascript",
            strategy="javascript_structure",
            content="export function snake_case() { return bootValue; }",
        ),
        LexicalIndexDocument(
            chunk_id="chunk-2",
            snapshot_id="snapshot-123",
            repository_id="repo-123",
            relative_path="src/Controller/HomeController.php",
            language="php",
            strategy="php_structure",
            content="class HomeController { public function bootValue() {} }",
        ),
        LexicalIndexDocument(
            chunk_id="chunk-3",
            snapshot_id="snapshot-123",
            repository_id="repo-123",
            relative_path="templates/page.html.twig",
            language="twig",
            strategy="twig_structure",
            content="{{ include('partials/card.html.twig') }}",
        ),
    ]


def test_sqlite_fts5_builder_creates_searchable_artifact_with_traceability(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    builder = SqliteFts5LexicalIndexBuilder(runtime_paths=runtime_paths)

    artifact = builder.build(
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        documents=build_documents(),
    )

    assert artifact.chunks_indexed == 3
    assert artifact.index_path == (
        workspace
        / ".codeman"
        / "indexes"
        / "lexical"
        / "repo-123"
        / "snapshot-123"
        / "lexical.sqlite3"
    )
    assert artifact.index_path.exists()

    connection = sqlite3.connect(artifact.index_path)
    schema_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'lexical_chunks'",
    ).fetchone()[0]
    snake_case_rows = connection.execute(
        """
        SELECT chunk_id, relative_path, snapshot_id, repository_id, language, strategy
        FROM lexical_chunks
        WHERE lexical_chunks MATCH ?
        ORDER BY chunk_id
        """,
        ("snake_case",),
    ).fetchall()
    mixed_case_rows = connection.execute(
        """
        SELECT chunk_id, relative_path
        FROM lexical_chunks
        WHERE lexical_chunks MATCH ?
        ORDER BY chunk_id
        """,
        ("HomeController",),
    ).fetchall()
    path_rows = connection.execute(
        """
        SELECT chunk_id, relative_path
        FROM lexical_chunks
        WHERE lexical_chunks MATCH ?
        ORDER BY chunk_id
        """,
        ("templates",),
    ).fetchall()

    assert "fts5" in schema_sql.lower()
    assert snake_case_rows == [
        (
            "chunk-1",
            "assets/app.js",
            "snapshot-123",
            "repo-123",
            "javascript",
            "javascript_structure",
        )
    ]
    assert mixed_case_rows == [("chunk-2", "src/Controller/HomeController.php")]
    assert path_rows == [("chunk-3", "templates/page.html.twig")]

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from codeman.contracts.retrieval import SemanticEmbeddingDocument
from codeman.infrastructure.indexes.vector.sqlite_exact_builder import (
    SqliteExactVectorIndexBuilder,
)
from codeman.runtime import build_runtime_paths


def build_embedding_document(
    *,
    chunk_id: str,
    relative_path: str,
    start_line: int,
) -> SemanticEmbeddingDocument:
    return SemanticEmbeddingDocument(
        chunk_id=chunk_id,
        snapshot_id="snapshot-123",
        repository_id="repo-123",
        source_file_id=f"{chunk_id}-source",
        relative_path=relative_path,
        language="javascript",
        strategy="javascript_structure",
        serialization_version="1",
        source_content_hash=f"hash-{chunk_id}",
        start_line=start_line,
        end_line=start_line + 2,
        start_byte=start_line * 10,
        end_byte=(start_line * 10) + 42,
        content=f"content for {chunk_id}",
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="1",
        vector_dimension=4,
        embedding=[0.1, 0.2, 0.3, 0.4],
    )


def test_sqlite_exact_vector_builder_writes_deterministic_rows(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    builder = SqliteExactVectorIndexBuilder(runtime_paths=build_runtime_paths(workspace))

    result = builder.build(
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        semantic_config_fingerprint="fingerprint-123",
        documents=[
            build_embedding_document(
                chunk_id="chunk-b",
                relative_path="src/b.js",
                start_line=20,
            ),
            build_embedding_document(
                chunk_id="chunk-a",
                relative_path="assets/a.js",
                start_line=1,
            ),
        ],
    )

    with sqlite3.connect(result.artifact_path) as connection:
        rows = connection.execute(
            "SELECT chunk_id FROM semantic_vectors ORDER BY rowid",
        ).fetchall()

    assert result.document_count == 2
    assert rows == [("chunk-a",), ("chunk-b",)]


def test_sqlite_exact_vector_builder_reports_refresh_on_rebuild(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    builder = SqliteExactVectorIndexBuilder(runtime_paths=build_runtime_paths(workspace))
    documents = [
        build_embedding_document(
            chunk_id="chunk-a",
            relative_path="assets/a.js",
            start_line=1,
        )
    ]

    first = builder.build(
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        semantic_config_fingerprint="fingerprint-123",
        documents=documents,
    )
    second = builder.build(
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        semantic_config_fingerprint="fingerprint-123",
        documents=documents,
    )

    assert first.artifact_path == second.artifact_path
    assert first.refreshed_existing_artifact is False
    assert second.refreshed_existing_artifact is True


def test_sqlite_exact_vector_builder_rejects_mixed_embedding_dimensions(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    builder = SqliteExactVectorIndexBuilder(runtime_paths=build_runtime_paths(workspace))

    first = build_embedding_document(
        chunk_id="chunk-a",
        relative_path="assets/a.js",
        start_line=1,
    )
    second = build_embedding_document(
        chunk_id="chunk-b",
        relative_path="src/b.js",
        start_line=2,
    )
    second = second.model_copy(update={"vector_dimension": 8, "embedding": [0.1] * 8})

    with pytest.raises(ValueError, match="shared embedding dimension"):
        builder.build(
            repository_id="repo-123",
            snapshot_id="snapshot-123",
            semantic_config_fingerprint="fingerprint-123",
            documents=[first, second],
        )

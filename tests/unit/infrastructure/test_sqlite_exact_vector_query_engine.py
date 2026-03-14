from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codeman.application.ports.semantic_query_port import SemanticVectorArtifactCorruptError
from codeman.contracts.retrieval import (
    SemanticEmbeddingDocument,
    SemanticIndexBuildRecord,
    SemanticQueryEmbedding,
)
from codeman.infrastructure.indexes.vector.sqlite_exact_builder import (
    SqliteExactVectorIndexBuilder,
)
from codeman.infrastructure.indexes.vector.sqlite_exact_query_engine import (
    SqliteExactVectorQueryEngine,
)
from codeman.runtime import build_runtime_paths


def build_embedding_document(
    *,
    chunk_id: str,
    embedding: list[float],
) -> SemanticEmbeddingDocument:
    return SemanticEmbeddingDocument(
        chunk_id=chunk_id,
        snapshot_id="snapshot-123",
        repository_id="repo-123",
        source_file_id=f"{chunk_id}-source",
        relative_path=f"assets/{chunk_id}.js",
        language="javascript",
        strategy="javascript_structure",
        serialization_version="1",
        source_content_hash=f"hash-{chunk_id}",
        start_line=1,
        end_line=3,
        start_byte=0,
        end_byte=42,
        content=f"content for {chunk_id}",
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="2026-03-14",
        vector_dimension=len(embedding),
        embedding=embedding,
    )


def build_semantic_build_record(
    artifact_path: Path,
    *,
    document_count: int = 3,
    embedding_dimension: int = 4,
) -> SemanticIndexBuildRecord:
    return SemanticIndexBuildRecord(
        build_id="semantic-build-123",
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        semantic_config_fingerprint="semantic-fingerprint-123",
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="2026-03-14",
        vector_engine="sqlite-exact",
        document_count=document_count,
        embedding_dimension=embedding_dimension,
        artifact_path=artifact_path,
        created_at=datetime.now(UTC),
    )


def build_query_embedding(values: list[float]) -> SemanticQueryEmbedding:
    return SemanticQueryEmbedding(
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="2026-03-14",
        vector_dimension=len(values),
        embedding=values,
    )


def test_sqlite_exact_vector_query_engine_orders_results_deterministically(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    builder = SqliteExactVectorIndexBuilder(runtime_paths=runtime_paths)
    query_engine = SqliteExactVectorQueryEngine()

    artifact = builder.build(
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        semantic_config_fingerprint="semantic-fingerprint-123",
        documents=[
            build_embedding_document(chunk_id="chunk-b", embedding=[1.0, 0.0, 0.0, 0.0]),
            build_embedding_document(chunk_id="chunk-a", embedding=[1.0, 0.0, 0.0, 0.0]),
            build_embedding_document(chunk_id="chunk-c", embedding=[0.0, 1.0, 0.0, 0.0]),
        ],
    )

    result = query_engine.query(
        build=build_semantic_build_record(artifact.artifact_path, document_count=3),
        query_embedding=build_query_embedding([1.0, 0.0, 0.0, 0.0]),
        max_results=2,
    )

    assert [match.chunk_id for match in result.matches] == ["chunk-a", "chunk-b"]
    assert [match.rank for match in result.matches] == [1, 2]
    assert result.matches[0].score == pytest.approx(1.0)
    assert result.diagnostics.match_count == 2
    assert result.diagnostics.total_match_count == 3
    assert result.diagnostics.truncated is True


def test_sqlite_exact_vector_query_engine_rejects_dimension_mismatch(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    builder = SqliteExactVectorIndexBuilder(runtime_paths=runtime_paths)
    query_engine = SqliteExactVectorQueryEngine()

    artifact = builder.build(
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        semantic_config_fingerprint="semantic-fingerprint-123",
        documents=[
            build_embedding_document(chunk_id="chunk-a", embedding=[1.0, 0.0, 0.0, 0.0]),
        ],
    )

    with pytest.raises(ValueError, match="different embedding dimension"):
        query_engine.query(
            build=build_semantic_build_record(
                artifact.artifact_path,
                document_count=1,
                embedding_dimension=4,
            ),
            query_embedding=build_query_embedding([1.0, 0.0, 0.0]),
        )


def test_sqlite_exact_vector_query_engine_rejects_invalid_embedding_rows(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "semantic.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE semantic_vectors (
                chunk_id TEXT PRIMARY KEY,
                embedding_dimension INTEGER NOT NULL,
                embedding_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO semantic_vectors (chunk_id, embedding_dimension, embedding_json)
            VALUES (?, ?, ?)
            """,
            ("chunk-a", 4, json.dumps(["not-a-number", 0.0, 0.0, 0.0])),
        )
        connection.executemany(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            [
                ("vector_engine", "sqlite-exact"),
                ("document_count", "1"),
                ("embedding_dimension", "4"),
            ],
        )
        connection.commit()

    query_engine = SqliteExactVectorQueryEngine()

    with pytest.raises(SemanticVectorArtifactCorruptError, match="not numeric"):
        query_engine.query(
            build=build_semantic_build_record(database_path, document_count=1),
            query_embedding=build_query_embedding([1.0, 0.0, 0.0, 0.0]),
        )


def test_sqlite_exact_vector_query_engine_rejects_truncated_artifacts(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    builder = SqliteExactVectorIndexBuilder(runtime_paths=runtime_paths)
    query_engine = SqliteExactVectorQueryEngine()

    artifact = builder.build(
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        semantic_config_fingerprint="semantic-fingerprint-123",
        documents=[
            build_embedding_document(chunk_id="chunk-a", embedding=[1.0, 0.0, 0.0, 0.0]),
            build_embedding_document(chunk_id="chunk-b", embedding=[0.0, 1.0, 0.0, 0.0]),
        ],
    )
    with sqlite3.connect(artifact.artifact_path) as connection:
        connection.execute("DELETE FROM semantic_vectors")
        connection.commit()

    with pytest.raises(SemanticVectorArtifactCorruptError, match="row count does not match"):
        query_engine.query(
            build=build_semantic_build_record(artifact.artifact_path, document_count=2),
            query_embedding=build_query_embedding([1.0, 0.0, 0.0, 0.0]),
        )

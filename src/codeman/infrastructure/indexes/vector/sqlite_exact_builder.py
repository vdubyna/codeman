"""SQLite exact-search vector index builder."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Sequence

from codeman.application.ports.vector_index_port import VectorIndexPort
from codeman.contracts.retrieval import SemanticEmbeddingDocument, SemanticIndexArtifact
from codeman.runtime import RuntimePaths, provision_runtime_paths

VECTOR_ENGINE_ID = "sqlite-exact"


def _ordered_documents(
    documents: Sequence[SemanticEmbeddingDocument],
) -> list[SemanticEmbeddingDocument]:
    return sorted(
        documents,
        key=lambda document: (
            document.relative_path,
            document.start_line,
            document.start_byte,
            document.chunk_id,
        ),
    )


def _validated_embedding_dimension(
    documents: Sequence[SemanticEmbeddingDocument],
) -> int:
    if not documents:
        return 0

    expected_dimension = documents[0].vector_dimension
    for document in documents:
        if document.vector_dimension != expected_dimension:
            raise ValueError("Semantic vector documents must use one shared embedding dimension.")
        if len(document.embedding) != document.vector_dimension:
            raise ValueError(
                "Semantic vector documents must store an embedding length matching "
                "their declared dimension."
            )

    return expected_dimension


@dataclass(slots=True)
class SqliteExactVectorIndexBuilder(VectorIndexPort):
    """Build a snapshot/config-scoped SQLite exact-search vector index."""

    runtime_paths: RuntimePaths

    def build(
        self,
        *,
        repository_id: str,
        snapshot_id: str,
        semantic_config_fingerprint: str,
        documents: Sequence[SemanticEmbeddingDocument],
    ) -> SemanticIndexArtifact:
        """Persist a semantic vector index database atomically under `.codeman/indexes/`."""

        provision_runtime_paths(self.runtime_paths)
        final_path = (
            self.runtime_paths.indexes
            / "vector"
            / repository_id
            / snapshot_id
            / semantic_config_fingerprint
            / "semantic.sqlite3"
        )
        final_path.parent.mkdir(parents=True, exist_ok=True)
        refreshed_existing_artifact = final_path.exists()

        temp_path = self._allocate_temp_path()
        try:
            ordered_documents = _ordered_documents(documents)
            embedding_dimension = _validated_embedding_dimension(ordered_documents)
            self._write_database(temp_path, ordered_documents)
            temp_path.replace(final_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

        return SemanticIndexArtifact(
            vector_engine=VECTOR_ENGINE_ID,
            document_count=len(ordered_documents),
            embedding_dimension=embedding_dimension,
            artifact_path=final_path,
            refreshed_existing_artifact=refreshed_existing_artifact,
        )

    def _allocate_temp_path(self) -> Path:
        with NamedTemporaryFile(
            dir=self.runtime_paths.tmp,
            prefix="semantic-",
            suffix=".sqlite3",
            delete=False,
        ) as handle:
            return Path(handle.name)

    @staticmethod
    def _write_database(
        database_path: Path,
        documents: Sequence[SemanticEmbeddingDocument],
    ) -> None:
        connection = sqlite3.connect(database_path)
        try:
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
                    snapshot_id TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    source_file_id TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    language TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    serialization_version TEXT NOT NULL,
                    source_content_hash TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    start_byte INTEGER NOT NULL,
                    end_byte INTEGER NOT NULL,
                    provider_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    embedding_dimension INTEGER NOT NULL,
                    embedding_json TEXT NOT NULL
                )
                """
            )
            connection.executemany(
                """
                INSERT INTO semantic_vectors (
                    chunk_id,
                    snapshot_id,
                    repository_id,
                    source_file_id,
                    relative_path,
                    language,
                    strategy,
                    serialization_version,
                    source_content_hash,
                    start_line,
                    end_line,
                    start_byte,
                    end_byte,
                    provider_id,
                    model_id,
                    model_version,
                    embedding_dimension,
                    embedding_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        document.chunk_id,
                        document.snapshot_id,
                        document.repository_id,
                        document.source_file_id,
                        document.relative_path,
                        document.language,
                        document.strategy,
                        document.serialization_version,
                        document.source_content_hash,
                        document.start_line,
                        document.end_line,
                        document.start_byte,
                        document.end_byte,
                        document.provider_id,
                        document.model_id,
                        document.model_version,
                        document.vector_dimension,
                        json.dumps(document.embedding, separators=(",", ":")),
                    )
                    for document in documents
                ],
            )
            connection.executemany(
                "INSERT INTO metadata (key, value) VALUES (?, ?)",
                [
                    ("vector_engine", VECTOR_ENGINE_ID),
                    ("document_count", str(len(documents))),
                    (
                        "embedding_dimension",
                        str(documents[0].vector_dimension if documents else 0),
                    ),
                ],
            )
            connection.commit()
        finally:
            connection.close()

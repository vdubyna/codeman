"""SQLite exact-search semantic query adapter."""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from json import JSONDecodeError
from time import perf_counter

from codeman.application.ports.semantic_query_port import (
    SemanticQueryPort,
    SemanticVectorArtifactCorruptError,
)
from codeman.contracts.retrieval import (
    SemanticIndexBuildRecord,
    SemanticQueryDiagnostics,
    SemanticQueryEmbedding,
    SemanticQueryMatch,
    SemanticQueryResult,
)

VECTOR_ENGINE_ID = "sqlite-exact"


def _validate_query_embedding(query_embedding: SemanticQueryEmbedding) -> None:
    if query_embedding.vector_dimension <= 0:
        raise ValueError("Semantic query embedding must declare a positive vector dimension.")
    if len(query_embedding.embedding) != query_embedding.vector_dimension:
        raise ValueError(
            "Semantic query embedding length must match its declared vector dimension."
        )


def _load_metadata(connection: sqlite3.Connection) -> dict[str, str]:
    try:
        rows = connection.execute(
            """
            SELECT key, value
            FROM metadata
            """
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise SemanticVectorArtifactCorruptError(
            "Semantic vector artifact is missing required metadata."
        ) from exc

    metadata = {str(key): str(value) for key, value in rows}
    missing_keys = sorted(
        key
        for key in ("vector_engine", "document_count", "embedding_dimension")
        if key not in metadata
    )
    if missing_keys:
        missing_list = ", ".join(missing_keys)
        raise SemanticVectorArtifactCorruptError(
            f"Semantic vector artifact metadata is missing required field(s): {missing_list}."
        )
    return metadata


def _metadata_int_value(metadata: dict[str, str], key: str) -> int:
    raw_value = metadata[key]
    try:
        return int(raw_value)
    except ValueError as exc:
        raise SemanticVectorArtifactCorruptError(
            f"Semantic vector artifact metadata field {key!r} must be an integer."
        ) from exc


def _validate_artifact_metadata(
    *,
    build: SemanticIndexBuildRecord,
    metadata: dict[str, str],
) -> tuple[int, int]:
    vector_engine = metadata["vector_engine"]
    if vector_engine != VECTOR_ENGINE_ID or build.vector_engine != VECTOR_ENGINE_ID:
        raise SemanticVectorArtifactCorruptError(
            "Semantic vector artifact metadata does not match the expected vector engine."
        )

    document_count = _metadata_int_value(metadata, "document_count")
    if document_count != build.document_count:
        raise SemanticVectorArtifactCorruptError(
            "Semantic vector artifact metadata does not match the recorded document count."
        )

    embedding_dimension = _metadata_int_value(metadata, "embedding_dimension")
    if embedding_dimension != build.embedding_dimension:
        raise SemanticVectorArtifactCorruptError(
            "Semantic vector artifact metadata does not match the recorded embedding dimension."
        )

    return document_count, embedding_dimension


def _normalize_embedding(raw_embedding: object, *, expected_dimension: int) -> list[float]:
    if not isinstance(raw_embedding, list):
        raise ValueError("Semantic vector artifact row is invalid: embedding must be a list.")
    if len(raw_embedding) != expected_dimension:
        raise ValueError(
            "Semantic vector artifact row is invalid: embedding length does not match "
            "the expected vector dimension."
        )

    values: list[float] = []
    for value in raw_embedding:
        if not isinstance(value, int | float):
            raise ValueError(
                "Semantic vector artifact row is invalid: embedding value is not numeric."
            )
        values.append(float(value))
    return values


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(
        left_value * right_value for left_value, right_value in zip(left, right, strict=True)
    )
    left_magnitude = math.sqrt(sum(value * value for value in left))
    right_magnitude = math.sqrt(sum(value * value for value in right))
    if left_magnitude == 0 or right_magnitude == 0:
        return 0.0
    return numerator / (left_magnitude * right_magnitude)


@dataclass(slots=True)
class SqliteExactVectorQueryEngine(SemanticQueryPort):
    """Execute semantic queries against a persisted SQLite exact-search artifact."""

    def query(
        self,
        *,
        build: SemanticIndexBuildRecord,
        query_embedding: SemanticQueryEmbedding,
        max_results: int = 20,
    ) -> SemanticQueryResult:
        _validate_query_embedding(query_embedding)
        if query_embedding.vector_dimension != build.embedding_dimension:
            raise ValueError(
                "Semantic query embedding uses a different embedding dimension than the semantic "
                "build."
            )

        started_at = perf_counter()
        connection = sqlite3.connect(build.artifact_path)
        try:
            metadata = _load_metadata(connection)
            expected_document_count, expected_dimension = _validate_artifact_metadata(
                build=build,
                metadata=metadata,
            )
            rows = connection.execute(
                """
                SELECT chunk_id, embedding_dimension, embedding_json
                FROM semantic_vectors
                """
            ).fetchall()
        finally:
            connection.close()

        if len(rows) != expected_document_count:
            raise SemanticVectorArtifactCorruptError(
                "Semantic vector artifact row count does not match recorded metadata."
            )

        scored_matches: list[tuple[str, float]] = []
        for chunk_id, embedding_dimension, embedding_json in rows:
            try:
                row_dimension = int(embedding_dimension)
            except (TypeError, ValueError) as exc:
                raise SemanticVectorArtifactCorruptError(
                    "Semantic vector artifact row is invalid: embedding dimension must be an "
                    "integer."
                ) from exc
            if row_dimension != expected_dimension:
                raise SemanticVectorArtifactCorruptError(
                    "Semantic vector artifact row dimension does not match recorded metadata."
                )
            try:
                raw_embedding = json.loads(embedding_json)
            except JSONDecodeError as exc:
                raise SemanticVectorArtifactCorruptError(
                    "Semantic vector artifact row is invalid: embedding JSON could not be decoded."
                ) from exc
            try:
                document_embedding = _normalize_embedding(
                    raw_embedding,
                    expected_dimension=query_embedding.vector_dimension,
                )
            except (TypeError, ValueError) as exc:
                raise SemanticVectorArtifactCorruptError(str(exc)) from exc
            try:
                score = _cosine_similarity(query_embedding.embedding, document_embedding)
            except ValueError as exc:
                raise SemanticVectorArtifactCorruptError(
                    "Semantic vector artifact row is invalid: embedding dimension mismatch."
                ) from exc
            except TypeError as exc:
                raise SemanticVectorArtifactCorruptError(
                    "Semantic vector artifact row is invalid: embedding contains unsupported "
                    "values."
                ) from exc
            scored_matches.append((str(chunk_id), score))

        ordered_matches = sorted(
            scored_matches,
            key=lambda item: (-item[1], item[0]),
        )
        selected_matches = ordered_matches[:max_results]
        elapsed_ms = int(round((perf_counter() - started_at) * 1000))

        return SemanticQueryResult(
            matches=[
                SemanticQueryMatch(
                    chunk_id=chunk_id,
                    score=score,
                    rank=index,
                )
                for index, (chunk_id, score) in enumerate(selected_matches, start=1)
            ],
            diagnostics=SemanticQueryDiagnostics(
                match_count=len(selected_matches),
                query_latency_ms=elapsed_ms,
                total_match_count=len(ordered_matches),
                truncated=len(selected_matches) < len(ordered_matches),
            ),
        )

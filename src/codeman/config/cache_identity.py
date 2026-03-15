"""Deterministic cache-identity helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Sequence

from codeman.config.indexing import CHUNK_SERIALIZATION_VERSION
from codeman.contracts.cache import NormalizedChunkIdentityDocument
from codeman.contracts.repository import SourceLanguage
from codeman.contracts.retrieval import SemanticSourceDocument

CACHE_IDENTITY_SCHEMA_VERSION = "1"


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _hash_descriptor(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def build_chunk_content_hash(content: str) -> str:
    """Return a deterministic hash for one chunk body."""

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_parser_cache_descriptor(
    *,
    language: SourceLanguage,
    relative_path: str,
    source_content_hash: str,
    parser_policy_id: str,
) -> dict[str, Any]:
    """Build the normalized parser cache descriptor."""

    return {
        "schema_version": CACHE_IDENTITY_SCHEMA_VERSION,
        "artifact_kind": "parser",
        "source": {
            "language": language,
            "relative_path": relative_path,
            "source_content_hash": source_content_hash,
        },
        "parser": {
            "policy_id": parser_policy_id,
        },
    }


def build_parser_cache_key(
    *,
    language: SourceLanguage,
    relative_path: str,
    source_content_hash: str,
    parser_policy_id: str,
) -> str:
    """Return the deterministic parser cache key."""

    return _hash_descriptor(
        build_parser_cache_descriptor(
            language=language,
            relative_path=relative_path,
            source_content_hash=source_content_hash,
            parser_policy_id=parser_policy_id,
        )
    )


def build_chunk_cache_descriptor(
    *,
    language: SourceLanguage,
    relative_path: str,
    source_content_hash: str,
    indexing_config_fingerprint: str,
    chunk_serialization_version: str = CHUNK_SERIALIZATION_VERSION,
) -> dict[str, Any]:
    """Build the normalized chunk cache descriptor."""

    return {
        "schema_version": CACHE_IDENTITY_SCHEMA_VERSION,
        "artifact_kind": "chunk",
        "source": {
            "language": language,
            "relative_path": relative_path,
            "source_content_hash": source_content_hash,
        },
        "indexing": {
            "indexing_config_fingerprint": indexing_config_fingerprint,
            "chunk_serialization_version": chunk_serialization_version,
        },
    }


def build_chunk_cache_key(
    *,
    language: SourceLanguage,
    relative_path: str,
    source_content_hash: str,
    indexing_config_fingerprint: str,
    chunk_serialization_version: str = CHUNK_SERIALIZATION_VERSION,
) -> str:
    """Return the deterministic chunk cache key."""

    return _hash_descriptor(
        build_chunk_cache_descriptor(
            language=language,
            relative_path=relative_path,
            source_content_hash=source_content_hash,
            indexing_config_fingerprint=indexing_config_fingerprint,
            chunk_serialization_version=chunk_serialization_version,
        )
    )


def build_normalized_chunk_identity(
    document: SemanticSourceDocument,
) -> NormalizedChunkIdentityDocument:
    """Return a snapshot-independent cache identity for one chunk."""

    descriptor = {
        "schema_version": CACHE_IDENTITY_SCHEMA_VERSION,
        "artifact_kind": "normalized_chunk",
        "chunk": {
            "relative_path": document.relative_path,
            "language": document.language,
            "strategy": document.strategy,
            "serialization_version": document.serialization_version,
            "source_content_hash": document.source_content_hash,
            "start_line": document.start_line,
            "end_line": document.end_line,
            "start_byte": document.start_byte,
            "end_byte": document.end_byte,
            "content_hash": build_chunk_content_hash(document.content),
        },
    }
    identity_key = _hash_descriptor(descriptor)
    chunk_descriptor = descriptor["chunk"]
    return NormalizedChunkIdentityDocument(
        identity_key=identity_key,
        relative_path=chunk_descriptor["relative_path"],
        language=chunk_descriptor["language"],
        strategy=chunk_descriptor["strategy"],
        serialization_version=chunk_descriptor["serialization_version"],
        source_content_hash=chunk_descriptor["source_content_hash"],
        start_line=chunk_descriptor["start_line"],
        end_line=chunk_descriptor["end_line"],
        start_byte=chunk_descriptor["start_byte"],
        end_byte=chunk_descriptor["end_byte"],
        content_hash=chunk_descriptor["content_hash"],
    )


def build_embedding_cache_descriptor(
    *,
    semantic_config_fingerprint: str,
    provider_id: str,
    model_id: str,
    model_version: str,
    vector_dimension: int,
    normalized_chunks: Sequence[NormalizedChunkIdentityDocument],
) -> dict[str, Any]:
    """Build the normalized embedding cache descriptor."""

    ordered_chunks = sorted(
        normalized_chunks,
        key=lambda chunk: (
            chunk.relative_path,
            chunk.start_line,
            chunk.start_byte,
            chunk.identity_key,
        ),
    )
    return {
        "schema_version": CACHE_IDENTITY_SCHEMA_VERSION,
        "artifact_kind": "embedding",
        "semantic": {
            "semantic_config_fingerprint": semantic_config_fingerprint,
            "provider_id": provider_id,
            "model_id": model_id,
            "model_version": model_version,
            "vector_dimension": vector_dimension,
        },
        "chunks": [chunk.model_dump(mode="json") for chunk in ordered_chunks],
    }


def build_embedding_cache_key(
    *,
    semantic_config_fingerprint: str,
    provider_id: str,
    model_id: str,
    model_version: str,
    vector_dimension: int,
    normalized_chunks: Sequence[NormalizedChunkIdentityDocument],
) -> str:
    """Return the deterministic embedding cache key."""

    return _hash_descriptor(
        build_embedding_cache_descriptor(
            semantic_config_fingerprint=semantic_config_fingerprint,
            provider_id=provider_id,
            model_id=model_id,
            model_version=model_version,
            vector_dimension=vector_dimension,
            normalized_chunks=normalized_chunks,
        )
    )

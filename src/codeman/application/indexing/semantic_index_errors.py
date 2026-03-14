"""Stable semantic-index build failure types."""

from __future__ import annotations

from typing import Any

from codeman.contracts.errors import ErrorCode

__all__ = [
    "BuildSemanticIndexError",
    "InvalidSemanticConfigurationError",
    "SemanticSnapshotNotFoundError",
    "SemanticChunkBaselineMissingError",
    "SemanticChunkPayloadMissingError",
    "SemanticChunkPayloadCorruptError",
    "EmbeddingProviderUnavailableError",
    "VectorIndexBuildError",
]


class BuildSemanticIndexError(Exception):
    """Base exception for semantic-index build failures."""

    exit_code = 39
    error_code = ErrorCode.SEMANTIC_INDEX_BUILD_FAILED

    def __init__(
        self,
        message: str,
        *,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class InvalidSemanticConfigurationError(BuildSemanticIndexError):
    """Raised when semantic indexing configuration is invalid."""


class SemanticSnapshotNotFoundError(BuildSemanticIndexError):
    """Raised when semantic index building is requested for an unknown snapshot."""

    exit_code = 26
    error_code = ErrorCode.SNAPSHOT_NOT_FOUND


class SemanticChunkBaselineMissingError(BuildSemanticIndexError):
    """Raised when chunk generation has not produced a usable baseline yet."""

    exit_code = 34
    error_code = ErrorCode.CHUNK_BASELINE_MISSING


class SemanticChunkPayloadMissingError(BuildSemanticIndexError):
    """Raised when a persisted chunk payload artifact cannot be loaded."""

    exit_code = 35
    error_code = ErrorCode.CHUNK_PAYLOAD_MISSING


class SemanticChunkPayloadCorruptError(BuildSemanticIndexError):
    """Raised when a persisted chunk payload artifact is unreadable or mismatched."""

    exit_code = 36
    error_code = ErrorCode.CHUNK_PAYLOAD_CORRUPT


class EmbeddingProviderUnavailableError(BuildSemanticIndexError):
    """Raised when no explicit local embedding provider is configured."""

    exit_code = 37
    error_code = ErrorCode.EMBEDDING_PROVIDER_UNAVAILABLE


class VectorIndexBuildError(BuildSemanticIndexError):
    """Raised when vector-index artifact construction fails."""

    exit_code = 38
    error_code = ErrorCode.VECTOR_INDEX_BUILD_FAILED

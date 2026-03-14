"""Error contract DTOs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from codeman.contracts.common import CommandMeta


class ErrorDetail(BaseModel):
    """Stable error payload placeholder."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: Any | None = None


class FailureEnvelope(BaseModel):
    """Failure response envelope placeholder."""

    model_config = ConfigDict(extra="forbid")

    ok: Literal[False] = False
    error: ErrorDetail
    meta: CommandMeta | None = None


class ErrorCode:
    """Stable error-code identifiers for the current CLI surface."""

    REPOSITORY_PATH_NOT_FOUND = "repository_path_not_found"
    REPOSITORY_PATH_NOT_DIRECTORY = "repository_path_not_directory"
    REPOSITORY_PATH_NOT_READABLE = "repository_path_not_readable"
    REPOSITORY_ALREADY_REGISTERED = "repository_already_registered"
    REPOSITORY_NOT_REGISTERED = "repository_not_registered"
    SNAPSHOT_NOT_FOUND = "snapshot_not_found"
    SNAPSHOT_SOURCE_MISMATCH = "snapshot_source_mismatch"
    SNAPSHOT_CREATION_FAILED = "snapshot_creation_failed"
    SOURCE_EXTRACTION_FAILED = "source_extraction_failed"
    SOURCE_INVENTORY_MISSING = "source_inventory_missing"
    CHUNK_GENERATION_FAILED = "chunk_generation_failed"
    CHUNK_BASELINE_MISSING = "chunk_baseline_missing"
    CHUNK_METADATA_MISSING = "chunk_metadata_missing"
    CHUNK_PAYLOAD_MISSING = "chunk_payload_missing"
    CHUNK_PAYLOAD_CORRUPT = "chunk_payload_corrupt"
    INDEXED_BASELINE_MISSING = "indexed_baseline_missing"
    LEXICAL_INDEX_BUILD_FAILED = "lexical_index_build_failed"
    LEXICAL_ARTIFACT_MISSING = "lexical_artifact_missing"
    LEXICAL_BUILD_BASELINE_MISSING = "lexical_build_baseline_missing"
    LEXICAL_QUERY_FAILED = "lexical_query_failed"
    SEMANTIC_INDEX_BUILD_FAILED = "semantic_index_build_failed"
    EMBEDDING_PROVIDER_UNAVAILABLE = "embedding_provider_unavailable"
    VECTOR_INDEX_BUILD_FAILED = "vector_index_build_failed"
    SEMANTIC_ARTIFACT_MISSING = "semantic_artifact_missing"
    SEMANTIC_ARTIFACT_CORRUPT = "semantic_artifact_corrupt"
    SEMANTIC_BUILD_BASELINE_MISSING = "semantic_build_baseline_missing"
    SEMANTIC_QUERY_FAILED = "semantic_query_failed"
    HYBRID_COMPONENT_BASELINE_MISSING = "hybrid_component_baseline_missing"
    HYBRID_COMPONENT_UNAVAILABLE = "hybrid_component_unavailable"
    HYBRID_SNAPSHOT_MISMATCH = "hybrid_snapshot_mismatch"
    HYBRID_QUERY_FAILED = "hybrid_query_failed"
    COMPARE_RETRIEVAL_MODE_BASELINE_MISSING = "compare_retrieval_mode_baseline_missing"
    COMPARE_RETRIEVAL_MODE_UNAVAILABLE = "compare_retrieval_mode_unavailable"
    COMPARE_RETRIEVAL_MODE_SNAPSHOT_MISMATCH = "compare_retrieval_mode_snapshot_mismatch"
    COMPARE_RETRIEVAL_MODES_FAILED = "compare_retrieval_modes_failed"
    REINDEX_FAILED = "reindex_failed"
    CONFIGURATION_INVALID = "configuration_invalid"
    INTERNAL_ERROR = "internal_error"

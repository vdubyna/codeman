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
    CHUNK_PAYLOAD_MISSING = "chunk_payload_missing"
    CHUNK_PAYLOAD_CORRUPT = "chunk_payload_corrupt"
    INDEXED_BASELINE_MISSING = "indexed_baseline_missing"
    LEXICAL_INDEX_BUILD_FAILED = "lexical_index_build_failed"
    LEXICAL_ARTIFACT_MISSING = "lexical_artifact_missing"
    LEXICAL_BUILD_BASELINE_MISSING = "lexical_build_baseline_missing"
    LEXICAL_QUERY_FAILED = "lexical_query_failed"
    REINDEX_FAILED = "reindex_failed"
    INTERNAL_ERROR = "internal_error"

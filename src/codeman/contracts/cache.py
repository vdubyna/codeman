"""Reusable cache artifact DTOs."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from codeman.contracts.repository import SourceLanguage


class CacheUsageSummary(BaseModel):
    """Machine-readable cache reuse/regeneration counters."""

    model_config = ConfigDict(extra="forbid")

    parser_entries_reused: int = 0
    parser_entries_regenerated: int = 0
    chunk_entries_reused: int = 0
    chunk_entries_regenerated: int = 0
    embedding_documents_reused: int = 0
    embedding_documents_regenerated: int = 0


class StructuralBoundaryDocument(BaseModel):
    """Serialized structural parser boundary."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    start_line: int
    label: str | None = None


class ChunkDraftDocument(BaseModel):
    """Serialized reusable chunk draft."""

    model_config = ConfigDict(extra="forbid")

    strategy: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    content: str


class NormalizedChunkIdentityDocument(BaseModel):
    """Snapshot-independent chunk identity used for cache reuse."""

    model_config = ConfigDict(extra="forbid")

    identity_key: str
    relative_path: str
    language: SourceLanguage
    strategy: str
    serialization_version: str
    source_content_hash: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    content_hash: str


class ParserCacheArtifactDocument(BaseModel):
    """Reusable parser output artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    cache_key: str
    language: SourceLanguage
    relative_path: str
    source_content_hash: str
    parser_policy_id: str
    boundaries: list[StructuralBoundaryDocument] = Field(default_factory=list)


class ChunkCacheArtifactDocument(BaseModel):
    """Reusable chunk draft artifact for one source file."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    cache_key: str
    parser_cache_key: str | None = None
    indexing_config_fingerprint: str
    language: SourceLanguage
    relative_path: str
    source_content_hash: str
    preferred_strategy: str
    strategy_used: str
    mode: Literal["structural", "fallback"]
    reason: str | None = None
    message: str | None = None
    drafts: list[ChunkDraftDocument] = Field(default_factory=list)


class CachedSemanticEmbeddingDocument(BaseModel):
    """Reusable embedding vector bound to a normalized chunk identity."""

    model_config = ConfigDict(extra="forbid")

    chunk_identity: NormalizedChunkIdentityDocument
    provider_id: str
    model_id: str
    model_version: str
    vector_dimension: int
    embedding: list[float] = Field(default_factory=list)


class EmbeddingCacheArtifactDocument(BaseModel):
    """Reusable embedding artifact detached from snapshot-local chunk ids."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    cache_key: str
    semantic_config_fingerprint: str
    provider_id: str
    model_id: str
    model_version: str
    local_model_path: Path | None = None
    vector_dimension: int
    documents: list[CachedSemanticEmbeddingDocument] = Field(default_factory=list)

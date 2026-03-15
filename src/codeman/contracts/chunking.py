"""Chunk-generation contract DTOs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from codeman.contracts.cache import CacheUsageSummary
from codeman.contracts.repository import RepositoryRecord, SnapshotRecord, SourceLanguage


class BuildChunksRequest(BaseModel):
    """Input DTO for chunk generation from extracted source inventory."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str


class ChunkRecord(BaseModel):
    """Persisted metadata for a generated retrieval chunk."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    snapshot_id: str
    repository_id: str
    source_file_id: str
    relative_path: str
    language: SourceLanguage
    strategy: str
    serialization_version: str = "1"
    source_content_hash: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    payload_path: Path
    created_at: datetime


class ChunkPayloadDocument(BaseModel):
    """Payload artifact stored on disk for a generated retrieval chunk."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    snapshot_id: str
    repository_id: str
    source_file_id: str
    relative_path: str
    language: SourceLanguage
    strategy: str
    serialization_version: str = "1"
    source_content_hash: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    content: str


class ChunkFileDiagnostic(BaseModel):
    """Per-file machine-readable chunking diagnostic."""

    model_config = ConfigDict(extra="forbid")

    source_file_id: str
    relative_path: str
    language: SourceLanguage
    preferred_strategy: str
    strategy_used: str
    mode: Literal["structural", "fallback"]
    chunk_count: int = 0
    reason: str | None = None
    message: str | None = None


class ChunkGenerationDiagnostics(BaseModel):
    """Chunk-generation summary safe for CLI and JSON output."""

    model_config = ConfigDict(extra="forbid")

    chunks_by_language: dict[SourceLanguage, int] = Field(default_factory=dict)
    chunks_by_strategy: dict[str, int] = Field(default_factory=dict)
    total_chunks: int = 0
    fallback_file_count: int = 0
    degraded_file_count: int = 0
    skipped_file_count: int = 0
    file_diagnostics: list[ChunkFileDiagnostic] = Field(default_factory=list)
    cache_summary: CacheUsageSummary = Field(default_factory=CacheUsageSummary)


class BuildChunksResult(BaseModel):
    """Output DTO for successful chunk generation."""

    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    repository: RepositoryRecord
    snapshot: SnapshotRecord
    chunks: list[ChunkRecord]
    diagnostics: ChunkGenerationDiagnostics

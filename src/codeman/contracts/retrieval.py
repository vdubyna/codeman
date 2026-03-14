"""Retrieval and index-build contract DTOs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from codeman.contracts.repository import RepositoryRecord, SnapshotRecord, SourceLanguage


class BuildLexicalIndexRequest(BaseModel):
    """Input DTO for building lexical index artifacts for a snapshot."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str


class LexicalIndexDocument(BaseModel):
    """Normalized lexical document passed to the lexical-index adapter."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    snapshot_id: str
    repository_id: str
    relative_path: str
    language: SourceLanguage
    strategy: str
    content: str


class LexicalIndexArtifact(BaseModel):
    """Result returned by the lexical-index adapter after a successful build."""

    model_config = ConfigDict(extra="forbid")

    lexical_engine: Literal["sqlite-fts5"]
    tokenizer_spec: str
    indexed_fields: list[str] = Field(default_factory=list)
    chunks_indexed: int = 0
    index_path: Path
    refreshed_existing_artifact: bool = False


class LexicalIndexBuildRecord(BaseModel):
    """Persisted attribution record for one lexical-index build."""

    model_config = ConfigDict(extra="forbid")

    build_id: str
    repository_id: str
    snapshot_id: str
    revision_identity: str
    revision_source: Literal["git", "filesystem_fingerprint"]
    indexing_config_fingerprint: str
    lexical_engine: str
    tokenizer_spec: str
    indexed_fields: list[str] = Field(default_factory=list)
    chunks_indexed: int = 0
    index_path: Path
    created_at: datetime


class LexicalIndexBuildDiagnostics(BaseModel):
    """Summary diagnostics safe for CLI and JSON output."""

    model_config = ConfigDict(extra="forbid")

    chunks_indexed: int = 0
    refreshed_existing_artifact: bool = False


class BuildLexicalIndexResult(BaseModel):
    """Output DTO for successful lexical-index builds."""

    model_config = ConfigDict(extra="forbid")

    repository: RepositoryRecord
    snapshot: SnapshotRecord
    build: LexicalIndexBuildRecord
    diagnostics: LexicalIndexBuildDiagnostics


class RunLexicalQueryRequest(BaseModel):
    """Input DTO for lexical-query execution."""

    model_config = ConfigDict(extra="forbid")

    repository_id: str
    query_text: str


class LexicalQueryMatch(BaseModel):
    """One ranked lexical match returned from an indexed artifact."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    relative_path: str
    language: SourceLanguage
    strategy: str
    score: float
    rank: int


class LexicalQueryDiagnostics(BaseModel):
    """Minimal diagnostics safe for CLI and JSON lexical query output."""

    model_config = ConfigDict(extra="forbid")

    match_count: int = 0
    query_latency_ms: int = 0


class LexicalQueryResult(BaseModel):
    """Adapter-facing lexical query payload before repository context is attached."""

    model_config = ConfigDict(extra="forbid")

    matches: list[LexicalQueryMatch] = Field(default_factory=list)
    diagnostics: LexicalQueryDiagnostics


class RunLexicalQueryResult(BaseModel):
    """Output DTO for successful lexical-query execution."""

    model_config = ConfigDict(extra="forbid")

    repository: RepositoryRecord
    snapshot: SnapshotRecord
    build: LexicalIndexBuildRecord
    query: str
    matches: list[LexicalQueryMatch] = Field(default_factory=list)
    diagnostics: LexicalQueryDiagnostics

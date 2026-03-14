"""Retrieval and index-build contract DTOs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from codeman.contracts.repository import RepositoryRecord, SnapshotRecord, SourceLanguage

RetrievalMode = Literal["lexical", "semantic", "hybrid"]


class BuildLexicalIndexRequest(BaseModel):
    """Input DTO for building lexical index artifacts for a snapshot."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str


class BuildSemanticIndexRequest(BaseModel):
    """Input DTO for building semantic index artifacts for a snapshot."""

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


class SemanticSourceDocument(BaseModel):
    """Normalized source document assembled from persisted chunk artifacts only."""

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


class EmbeddingProviderDescriptor(BaseModel):
    """Stable provider/model attribution for semantic indexing."""

    model_config = ConfigDict(extra="forbid")

    provider_id: str
    model_id: str
    model_version: str
    is_external_provider: bool = False
    local_model_path: Path | None = None


class SemanticEmbeddingDocument(BaseModel):
    """Embedding-ready document artifact traceable to a persisted retrieval chunk."""

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
    provider_id: str
    model_id: str
    model_version: str
    vector_dimension: int
    embedding: list[float] = Field(default_factory=list)


class SemanticQueryEmbedding(BaseModel):
    """Provider-owned query embedding used for semantic retrieval execution."""

    model_config = ConfigDict(extra="forbid")

    provider_id: str
    model_id: str
    model_version: str
    vector_dimension: int
    embedding: list[float] = Field(default_factory=list)


class SemanticEmbeddingArtifactDocument(BaseModel):
    """Persisted embedding artifact for one semantic build configuration."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1"
    snapshot_id: str
    repository_id: str
    semantic_config_fingerprint: str
    provider: EmbeddingProviderDescriptor
    documents: list[SemanticEmbeddingDocument] = Field(default_factory=list)


class LexicalIndexArtifact(BaseModel):
    """Result returned by the lexical-index adapter after a successful build."""

    model_config = ConfigDict(extra="forbid")

    lexical_engine: Literal["sqlite-fts5"]
    tokenizer_spec: str
    indexed_fields: list[str] = Field(default_factory=list)
    chunks_indexed: int = 0
    index_path: Path
    refreshed_existing_artifact: bool = False


class SemanticIndexArtifact(BaseModel):
    """Result returned by the vector-index adapter after a successful build."""

    model_config = ConfigDict(extra="forbid")

    vector_engine: str
    document_count: int = 0
    embedding_dimension: int = 0
    artifact_path: Path
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


class SemanticIndexBuildRecord(BaseModel):
    """Persisted attribution record for one semantic-index build."""

    model_config = ConfigDict(extra="forbid")

    build_id: str
    repository_id: str
    snapshot_id: str
    revision_identity: str
    revision_source: Literal["git", "filesystem_fingerprint"]
    semantic_config_fingerprint: str
    provider_id: str
    model_id: str
    model_version: str
    is_external_provider: bool = False
    vector_engine: str
    document_count: int = 0
    embedding_dimension: int = 0
    artifact_path: Path
    created_at: datetime


class LexicalIndexBuildDiagnostics(BaseModel):
    """Summary diagnostics safe for CLI and JSON output."""

    model_config = ConfigDict(extra="forbid")

    chunks_indexed: int = 0
    refreshed_existing_artifact: bool = False


class SemanticIndexBuildDiagnostics(BaseModel):
    """Summary diagnostics safe for semantic-build CLI and JSON output."""

    model_config = ConfigDict(extra="forbid")

    document_count: int = 0
    embedding_dimension: int = 0
    embedding_documents_path: Path
    refreshed_existing_artifact: bool = False


class BuildLexicalIndexResult(BaseModel):
    """Output DTO for successful lexical-index builds."""

    model_config = ConfigDict(extra="forbid")

    repository: RepositoryRecord
    snapshot: SnapshotRecord
    build: LexicalIndexBuildRecord
    diagnostics: LexicalIndexBuildDiagnostics


class BuildSemanticIndexResult(BaseModel):
    """Output DTO for successful semantic-index builds."""

    model_config = ConfigDict(extra="forbid")

    repository: RepositoryRecord
    snapshot: SnapshotRecord
    build: SemanticIndexBuildRecord
    provider: EmbeddingProviderDescriptor
    diagnostics: SemanticIndexBuildDiagnostics


class RunLexicalQueryRequest(BaseModel):
    """Input DTO for lexical-query execution."""

    model_config = ConfigDict(extra="forbid")

    repository_id: str
    query_text: str
    max_results: int = Field(default=20, gt=0, le=100)


class RunSemanticQueryRequest(BaseModel):
    """Input DTO for semantic-query execution."""

    model_config = ConfigDict(extra="forbid")

    repository_id: str
    query_text: str
    max_results: int = Field(default=20, gt=0, le=100)


class RetrievalQueryMetadata(BaseModel):
    """Stable query metadata shared by retrieval result packages."""

    model_config = ConfigDict(extra="forbid")

    text: str


class RetrievalRepositoryContext(BaseModel):
    """Compact repository identity for retrieval output."""

    model_config = ConfigDict(extra="forbid")

    repository_id: str
    repository_name: str


class RetrievalSnapshotContext(BaseModel):
    """Compact snapshot identity for retrieval output."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    revision_identity: str
    revision_source: Literal["git", "filesystem_fingerprint"]


class RetrievalBuildContext(BaseModel):
    """Compact build identity for retrieval output."""

    model_config = ConfigDict(extra="forbid")

    build_id: str


class LexicalRetrievalBuildContext(RetrievalBuildContext):
    """Compact lexical build identity for retrieval output."""

    lexical_engine: str
    tokenizer_spec: str
    indexed_fields: list[str] = Field(default_factory=list)


class SemanticRetrievalBuildContext(RetrievalBuildContext):
    """Compact semantic build identity for retrieval output."""

    provider_id: str
    model_id: str
    model_version: str
    vector_engine: str
    semantic_config_fingerprint: str


class LexicalQueryMatch(BaseModel):
    """One ranked lexical match returned from an indexed artifact."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    relative_path: str
    language: SourceLanguage
    strategy: str
    score: float
    rank: int
    path_match_context: str | None = None
    content_match_context: str | None = None
    path_match_highlighted: bool = False
    content_match_highlighted: bool = False


class RetrievalQueryDiagnostics(BaseModel):
    """Minimal diagnostics safe for retrieval CLI and JSON output."""

    model_config = ConfigDict(extra="forbid")

    match_count: int = 0
    query_latency_ms: int = 0
    total_match_count: int = 0
    truncated: bool = False


class LexicalQueryDiagnostics(RetrievalQueryDiagnostics):
    """Minimal diagnostics safe for CLI and JSON lexical query output."""


class LexicalQueryResult(BaseModel):
    """Adapter-facing lexical query payload before repository context is attached."""

    model_config = ConfigDict(extra="forbid")

    matches: list[LexicalQueryMatch] = Field(default_factory=list)
    diagnostics: LexicalQueryDiagnostics


class SemanticQueryMatch(BaseModel):
    """One ranked semantic match returned from a persisted vector artifact."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    score: float
    rank: int


class SemanticQueryDiagnostics(RetrievalQueryDiagnostics):
    """Minimal diagnostics safe for CLI and JSON semantic query output."""


class SemanticQueryResult(BaseModel):
    """Adapter-facing semantic query payload before repository context is attached."""

    model_config = ConfigDict(extra="forbid")

    matches: list[SemanticQueryMatch] = Field(default_factory=list)
    diagnostics: SemanticQueryDiagnostics


class RetrievalResultItem(BaseModel):
    """Stable result item shared by retrieval result packages."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    relative_path: str
    language: SourceLanguage
    strategy: str
    rank: int
    score: float
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    content_preview: str
    explanation: str


class RetrievalResultPackage(BaseModel):
    """Shared agent-friendly retrieval package for CLI and future retrieval modes."""

    model_config = ConfigDict(extra="forbid")

    retrieval_mode: RetrievalMode
    query: RetrievalQueryMetadata
    repository: RetrievalRepositoryContext
    snapshot: RetrievalSnapshotContext
    build: RetrievalBuildContext
    results: list[RetrievalResultItem] = Field(default_factory=list)
    diagnostics: RetrievalQueryDiagnostics


class RunLexicalQueryResult(RetrievalResultPackage):
    """Output DTO for successful lexical-query execution."""

    retrieval_mode: Literal["lexical"] = "lexical"
    build: LexicalRetrievalBuildContext


class RunSemanticQueryResult(RetrievalResultPackage):
    """Output DTO for successful semantic-query execution."""

    retrieval_mode: Literal["semantic"] = "semantic"
    build: SemanticRetrievalBuildContext

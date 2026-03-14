"""Run semantic retrieval queries against the current repository build."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from codeman.application.indexing.build_embeddings import resolve_local_embedding_provider
from codeman.application.indexing.semantic_index_errors import (
    EmbeddingProviderUnavailableError,
)
from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.application.ports.chunk_store_port import ChunkStorePort
from codeman.application.ports.embedding_provider_port import EmbeddingProviderPort
from codeman.application.ports.metadata_store_port import RepositoryMetadataStorePort
from codeman.application.ports.semantic_index_build_store_port import (
    SemanticIndexBuildStorePort,
)
from codeman.application.ports.semantic_query_port import (
    SemanticQueryPort,
    SemanticVectorArtifactCorruptError,
)
from codeman.application.ports.snapshot_port import SnapshotMetadataStorePort
from codeman.application.query.format_results import (
    ResolvedSemanticMatch,
    RetrievalResultFormatter,
)
from codeman.config.semantic_indexing import (
    SemanticIndexingConfig,
    build_semantic_indexing_fingerprint,
)
from codeman.contracts.errors import ErrorCode
from codeman.contracts.retrieval import (
    RunSemanticQueryRequest,
    RunSemanticQueryResult,
    SemanticIndexBuildRecord,
    SemanticQueryEmbedding,
    SemanticQueryMatch,
)
from codeman.runtime import RuntimePaths, provision_runtime_paths

__all__ = [
    "SemanticArtifactCorruptError",
    "RunSemanticQueryUseCase",
    "SemanticArtifactMissingError",
    "SemanticBuildBaselineMissingError",
    "SemanticQueryChunkMetadataMissingError",
    "SemanticQueryChunkPayloadCorruptError",
    "SemanticQueryChunkPayloadMissingError",
    "SemanticQueryError",
    "SemanticQueryProviderUnavailableError",
    "SemanticQueryRepositoryNotRegisteredError",
]


class SemanticQueryError(Exception):
    """Base exception for semantic-query failures."""

    exit_code = 43
    error_code = ErrorCode.SEMANTIC_QUERY_FAILED

    def __init__(
        self,
        message: str,
        *,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class SemanticQueryRepositoryNotRegisteredError(SemanticQueryError):
    """Raised when querying an unknown repository."""

    exit_code = 24
    error_code = ErrorCode.REPOSITORY_NOT_REGISTERED


class SemanticBuildBaselineMissingError(SemanticQueryError):
    """Raised when a repository has no current semantic build to query."""

    exit_code = 44
    error_code = ErrorCode.SEMANTIC_BUILD_BASELINE_MISSING


class SemanticArtifactMissingError(SemanticQueryError):
    """Raised when semantic build metadata points to a missing artifact."""

    exit_code = 45
    error_code = ErrorCode.SEMANTIC_ARTIFACT_MISSING


class SemanticArtifactCorruptError(SemanticQueryError):
    """Raised when a semantic artifact exists but no longer matches its recorded metadata."""

    exit_code = 46
    error_code = ErrorCode.SEMANTIC_ARTIFACT_CORRUPT


class SemanticQueryProviderUnavailableError(SemanticQueryError):
    """Raised when semantic query cannot use the configured local provider."""

    exit_code = 37
    error_code = ErrorCode.EMBEDDING_PROVIDER_UNAVAILABLE


class SemanticQueryChunkMetadataMissingError(SemanticQueryError):
    """Raised when ranked semantic hits cannot be resolved to chunk metadata."""

    exit_code = 40
    error_code = ErrorCode.CHUNK_METADATA_MISSING


class SemanticQueryChunkPayloadMissingError(SemanticQueryError):
    """Raised when a persisted chunk payload artifact is missing."""

    exit_code = 41
    error_code = ErrorCode.CHUNK_PAYLOAD_MISSING


class SemanticQueryChunkPayloadCorruptError(SemanticQueryError):
    """Raised when a persisted chunk payload artifact cannot be trusted."""

    exit_code = 42
    error_code = ErrorCode.CHUNK_PAYLOAD_CORRUPT


def _query_configuration_matches_build(
    *,
    provider_id: str,
    model_id: str,
    model_version: str,
    vector_dimension: int,
    build: SemanticIndexBuildRecord,
) -> bool:
    return (
        build.provider_id == provider_id
        and build.model_id == model_id
        and build.model_version == model_version
        and build.embedding_dimension == vector_dimension
    )


def _query_embedding_matches_build(
    *,
    query_embedding: SemanticQueryEmbedding,
    build: SemanticIndexBuildRecord,
) -> bool:
    return (
        query_embedding.provider_id == build.provider_id
        and query_embedding.model_id == build.model_id
        and query_embedding.model_version == build.model_version
        and query_embedding.vector_dimension == build.embedding_dimension
    )


@dataclass(slots=True)
class RunSemanticQueryUseCase:
    """Resolve the current semantic build for a repository and execute one query."""

    runtime_paths: RuntimePaths
    repository_store: RepositoryMetadataStorePort
    snapshot_store: SnapshotMetadataStorePort
    semantic_index_build_store: SemanticIndexBuildStorePort
    chunk_store: ChunkStorePort
    artifact_store: ArtifactStorePort
    embedding_provider: EmbeddingProviderPort
    semantic_query: SemanticQueryPort
    formatter: RetrievalResultFormatter
    semantic_indexing_config: SemanticIndexingConfig

    def execute(self, request: RunSemanticQueryRequest) -> RunSemanticQueryResult:
        """Run a semantic query against the current repository build."""

        provision_runtime_paths(self.runtime_paths)
        self.repository_store.initialize()
        self.snapshot_store.initialize()
        self.semantic_index_build_store.initialize()
        self.chunk_store.initialize()

        repository = self.repository_store.get_by_repository_id(request.repository_id)
        if repository is None:
            raise SemanticQueryRepositoryNotRegisteredError(
                f"Repository is not registered: {request.repository_id}",
            )

        try:
            semantic_config_fingerprint = build_semantic_indexing_fingerprint(
                self.semantic_indexing_config,
            )
            vector_dimension = self.semantic_indexing_config.resolved_vector_dimension()
        except ValueError as exc:
            raise SemanticQueryError(
                f"Semantic query configuration is invalid: {exc}",
            ) from exc

        build = self.semantic_index_build_store.get_latest_build_for_repository(
            repository.repository_id,
            semantic_config_fingerprint,
        )
        if build is None:
            raise SemanticBuildBaselineMissingError(
                "No semantic baseline exists yet for this repository and current configuration; "
                "run `codeman index build-semantic <snapshot-id>` first.",
            )
        if not build.artifact_path.exists():
            raise SemanticArtifactMissingError(
                f"Semantic artifact is missing for build: {build.build_id}",
            )

        snapshot = self.snapshot_store.get_by_snapshot_id(build.snapshot_id)
        if snapshot is None:
            raise SemanticQueryError(
                f"Semantic build points to an unknown snapshot: {build.snapshot_id}",
            )

        try:
            provider = resolve_local_embedding_provider(self.semantic_indexing_config)
        except EmbeddingProviderUnavailableError as exc:
            raise SemanticQueryProviderUnavailableError(
                exc.message,
                details=exc.details,
            ) from exc

        if not _query_configuration_matches_build(
            provider_id=provider.provider_id,
            model_id=provider.model_id,
            model_version=provider.model_version,
            vector_dimension=vector_dimension,
            build=build,
        ):
            raise SemanticBuildBaselineMissingError(
                "No semantic baseline exists yet for this repository and current configuration; "
                "run `codeman index build-semantic <snapshot-id>` first.",
            )

        try:
            query_embedding = self.embedding_provider.embed_query(
                provider=provider,
                query_text=request.query_text,
                vector_dimension=vector_dimension,
            )
        except EmbeddingProviderUnavailableError as exc:
            raise SemanticQueryProviderUnavailableError(
                exc.message,
                details=exc.details,
            ) from exc
        except Exception as exc:
            raise SemanticQueryProviderUnavailableError(
                "Semantic query failed to initialize the configured local embedding provider.",
                details={
                    "provider_id": provider.provider_id,
                    "local_model_path": str(provider.local_model_path)
                    if provider.local_model_path is not None
                    else None,
                },
            ) from exc

        if not _query_embedding_matches_build(
            query_embedding=query_embedding,
            build=build,
        ):
            raise SemanticQueryProviderUnavailableError(
                "Semantic query embedding metadata does not match the current semantic build.",
                details={
                    "expected": {
                        "provider_id": build.provider_id,
                        "model_id": build.model_id,
                        "model_version": build.model_version,
                        "vector_dimension": build.embedding_dimension,
                    },
                    "actual": {
                        "provider_id": query_embedding.provider_id,
                        "model_id": query_embedding.model_id,
                        "model_version": query_embedding.model_version,
                        "vector_dimension": query_embedding.vector_dimension,
                    },
                },
            )

        try:
            query_result = self.semantic_query.query(
                build=build,
                query_embedding=query_embedding,
                max_results=request.max_results,
            )
        except SemanticVectorArtifactCorruptError as exc:
            raise SemanticArtifactCorruptError(
                f"Semantic artifact is invalid for build: {build.build_id}",
                details={
                    "artifact_path": str(build.artifact_path),
                    "reason": str(exc),
                },
            ) from exc
        except SemanticQueryError:
            raise
        except Exception as exc:
            raise SemanticQueryError(
                f"Semantic query failed for repository: {request.repository_id}",
            ) from exc

        resolved_matches = self._resolve_matches(query_result.matches)
        return self.formatter.format_semantic_results(
            repository=repository,
            snapshot=snapshot,
            build=build,
            query_text=request.query_text,
            diagnostics=query_result.diagnostics,
            matches=resolved_matches,
        )

    def _resolve_matches(
        self,
        matches: list[SemanticQueryMatch],
    ) -> list[ResolvedSemanticMatch]:
        if not matches:
            return []

        chunk_ids = [match.chunk_id for match in matches]
        chunks = self.chunk_store.get_by_chunk_ids(chunk_ids)
        chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        missing_chunk_ids = [chunk_id for chunk_id in chunk_ids if chunk_id not in chunks_by_id]
        if missing_chunk_ids:
            missing_list = ", ".join(missing_chunk_ids)
            raise SemanticQueryChunkMetadataMissingError(
                f"Chunk metadata is missing for ranked retrieval result(s): {missing_list}",
            )

        resolved_matches: list[ResolvedSemanticMatch] = []
        for match in matches:
            chunk = chunks_by_id[match.chunk_id]
            try:
                payload = self.artifact_store.read_chunk_payload(chunk.payload_path)
            except FileNotFoundError as exc:
                raise SemanticQueryChunkPayloadMissingError(
                    f"Chunk payload artifact is missing for retrieval result: {chunk.chunk_id}",
                ) from exc
            except (ValidationError, ValueError) as exc:
                raise SemanticQueryChunkPayloadCorruptError(
                    f"Chunk payload artifact is invalid for retrieval result: {chunk.chunk_id}",
                ) from exc

            if payload.chunk_id != chunk.chunk_id or payload.snapshot_id != chunk.snapshot_id:
                raise SemanticQueryChunkPayloadCorruptError(
                    f"Chunk payload artifact does not match retrieval metadata: {chunk.chunk_id}",
                )

            resolved_matches.append(
                ResolvedSemanticMatch(
                    match=match,
                    chunk=chunk,
                    payload=payload,
                )
            )

        return resolved_matches

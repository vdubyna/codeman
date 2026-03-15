"""Semantic embedding stage for persisted chunk artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from codeman.application.indexing.semantic_index_errors import (
    EmbeddingProviderUnavailableError,
    InvalidSemanticConfigurationError,
)
from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.application.ports.cache_store_port import CacheStorePort
from codeman.application.ports.embedding_provider_port import EmbeddingProviderPort
from codeman.config.cache_identity import (
    build_embedding_cache_key,
    build_normalized_chunk_identity,
)
from codeman.config.embedding_providers import (
    LOCAL_HASH_PROVIDER_ID,
    EmbeddingProvidersConfig,
)
from codeman.config.semantic_indexing import SemanticIndexingConfig
from codeman.contracts.cache import (
    CachedSemanticEmbeddingDocument,
    CacheUsageSummary,
    EmbeddingCacheArtifactDocument,
)
from codeman.contracts.retrieval import (
    EmbeddingProviderDescriptor,
    SemanticEmbeddingArtifactDocument,
    SemanticEmbeddingDocument,
    SemanticSourceDocument,
)

__all__ = [
    "BuildEmbeddingsStage",
    "BuildEmbeddingsStageResult",
    "LOCAL_HASH_PROVIDER_ID",
    "resolve_local_embedding_provider",
]


def resolve_local_embedding_provider(
    semantic_indexing_config: SemanticIndexingConfig,
    embedding_providers_config: EmbeddingProvidersConfig,
) -> EmbeddingProviderDescriptor:
    """Resolve the configured local embedding provider or fail safely."""

    provider_id = semantic_indexing_config.provider_id
    if provider_id != LOCAL_HASH_PROVIDER_ID:
        raise EmbeddingProviderUnavailableError(
            "Semantic indexing requires an explicit local embedding provider. "
            "Set CODEMAN_SEMANTIC_PROVIDER_ID=local-hash and "
            "CODEMAN_SEMANTIC_LOCAL_MODEL_PATH=/path/to/local/model before running "
            "`codeman index build-semantic`.",
            details={
                "provider_id": provider_id,
            },
        )

    provider_config = embedding_providers_config.get_provider_config(provider_id)
    if provider_config is None:
        raise EmbeddingProviderUnavailableError(
            "Semantic indexing requires a configured provider block for the selected provider. "
            "Add [embedding_providers.local_hash] settings or set "
            "CODEMAN_EMBEDDING_PROVIDER_LOCAL_HASH_* / CODEMAN_SEMANTIC_* environment variables "
            "before running `codeman index build-semantic`.",
            details={
                "provider_id": provider_id,
            },
        )

    local_model_path = provider_config.local_model_path
    if local_model_path is None or not local_model_path.exists():
        raise EmbeddingProviderUnavailableError(
            "Semantic indexing requires a readable local model path. "
            "Set CODEMAN_SEMANTIC_LOCAL_MODEL_PATH to an existing local path before "
            "running `codeman index build-semantic`.",
            details={
                "provider_id": provider_id,
                "local_model_path": str(local_model_path) if local_model_path is not None else None,
            },
        )

    return EmbeddingProviderDescriptor(
        provider_id=provider_id,
        model_id=provider_config.model_id,
        model_version=provider_config.model_version,
        is_external_provider=False,
        local_model_path=local_model_path,
    )


@dataclass(frozen=True, slots=True)
class BuildEmbeddingsStageResult:
    """Embedding-stage outputs used by semantic index orchestration."""

    provider: EmbeddingProviderDescriptor
    documents: list[SemanticEmbeddingDocument]
    embedding_documents_path: Path
    cache_summary: CacheUsageSummary


@dataclass(slots=True)
class BuildEmbeddingsStage:
    """Generate semantic embeddings and persist the embedding artifact."""

    artifact_store: ArtifactStorePort
    cache_store: CacheStorePort
    embedding_provider: EmbeddingProviderPort
    semantic_indexing_config: SemanticIndexingConfig
    embedding_providers_config: EmbeddingProvidersConfig

    def execute(
        self,
        *,
        repository_id: str,
        snapshot_id: str,
        semantic_config_fingerprint: str,
        source_documents: Sequence[SemanticSourceDocument],
    ) -> BuildEmbeddingsStageResult:
        """Generate embeddings from persisted source documents only."""

        provider = resolve_local_embedding_provider(
            self.semantic_indexing_config,
            self.embedding_providers_config,
        )
        try:
            vector_dimension = self.semantic_indexing_config.resolved_vector_dimension()
        except ValueError as exc:
            raise InvalidSemanticConfigurationError(
                f"Semantic indexing configuration is invalid: {exc}",
                details={
                    "provider_id": provider.provider_id,
                    "vector_dimension": self.semantic_indexing_config.vector_dimension,
                },
            ) from exc

        normalized_chunks = [
            build_normalized_chunk_identity(document) for document in source_documents
        ]
        cache_key = build_embedding_cache_key(
            semantic_config_fingerprint=semantic_config_fingerprint,
            provider_id=provider.provider_id,
            model_id=provider.model_id,
            model_version=provider.model_version,
            vector_dimension=vector_dimension,
            normalized_chunks=normalized_chunks,
        )
        documents = self._load_cached_documents(
            cache_key=cache_key,
            provider=provider,
            semantic_config_fingerprint=semantic_config_fingerprint,
            source_documents=source_documents,
            vector_dimension=vector_dimension,
        )
        if documents is None:
            try:
                documents = self.embedding_provider.embed(
                    provider=provider,
                    documents=source_documents,
                    vector_dimension=vector_dimension,
                )
            except EmbeddingProviderUnavailableError:
                raise
            except Exception as exc:
                raise EmbeddingProviderUnavailableError(
                    "Semantic indexing failed to initialize the configured local "
                    "embedding provider.",
                    details={
                        "provider_id": provider.provider_id,
                        "local_model_path": str(provider.local_model_path)
                        if provider.local_model_path is not None
                        else None,
                    },
                ) from exc
            self.cache_store.write_embedding_cache(
                EmbeddingCacheArtifactDocument(
                    cache_key=cache_key,
                    semantic_config_fingerprint=semantic_config_fingerprint,
                    provider_id=provider.provider_id,
                    model_id=provider.model_id,
                    model_version=provider.model_version,
                    local_model_path=provider.local_model_path,
                    vector_dimension=vector_dimension,
                    documents=[
                        CachedSemanticEmbeddingDocument(
                            chunk_identity=normalized_chunk,
                            provider_id=document.provider_id,
                            model_id=document.model_id,
                            model_version=document.model_version,
                            vector_dimension=document.vector_dimension,
                            embedding=list(document.embedding),
                        )
                        for normalized_chunk, document in zip(
                            normalized_chunks,
                            documents,
                            strict=True,
                        )
                    ],
                )
            )
            cache_summary = CacheUsageSummary(
                embedding_documents_regenerated=len(documents),
            )
        else:
            cache_summary = CacheUsageSummary(
                embedding_documents_reused=len(documents),
            )

        artifact = SemanticEmbeddingArtifactDocument(
            snapshot_id=snapshot_id,
            repository_id=repository_id,
            semantic_config_fingerprint=semantic_config_fingerprint,
            provider=provider,
            documents=list(documents),
        )
        embedding_documents_path = self.artifact_store.write_embedding_documents(
            artifact,
            snapshot_id=snapshot_id,
            semantic_config_fingerprint=semantic_config_fingerprint,
        )
        return BuildEmbeddingsStageResult(
            provider=provider,
            documents=list(documents),
            embedding_documents_path=embedding_documents_path,
            cache_summary=cache_summary,
        )

    def _load_cached_documents(
        self,
        *,
        cache_key: str,
        provider: EmbeddingProviderDescriptor,
        semantic_config_fingerprint: str,
        source_documents: Sequence[SemanticSourceDocument],
        vector_dimension: int,
    ) -> list[SemanticEmbeddingDocument] | None:
        try:
            cached_artifact = self.cache_store.read_embedding_cache(cache_key)
        except (OSError, ValidationError, ValueError):
            return None
        if cached_artifact is None or cached_artifact.cache_key != cache_key:
            return None
        if cached_artifact.semantic_config_fingerprint != semantic_config_fingerprint:
            return None
        if cached_artifact.provider_id != provider.provider_id:
            return None
        if cached_artifact.model_id != provider.model_id:
            return None
        if cached_artifact.model_version != provider.model_version:
            return None
        if cached_artifact.vector_dimension != vector_dimension:
            return None

        cached_by_identity = {
            document.chunk_identity.identity_key: document for document in cached_artifact.documents
        }
        if len(cached_by_identity) != len(source_documents):
            return None

        documents: list[SemanticEmbeddingDocument] = []
        for source_document in source_documents:
            normalized_chunk = build_normalized_chunk_identity(source_document)
            cached_document = cached_by_identity.get(normalized_chunk.identity_key)
            if cached_document is None:
                return None
            if cached_document.provider_id != provider.provider_id:
                return None
            if cached_document.model_id != provider.model_id:
                return None
            if cached_document.model_version != provider.model_version:
                return None
            if cached_document.vector_dimension != vector_dimension:
                return None
            if len(cached_document.embedding) != vector_dimension:
                return None
            documents.append(
                SemanticEmbeddingDocument(
                    chunk_id=source_document.chunk_id,
                    snapshot_id=source_document.snapshot_id,
                    repository_id=source_document.repository_id,
                    source_file_id=source_document.source_file_id,
                    relative_path=source_document.relative_path,
                    language=source_document.language,
                    strategy=source_document.strategy,
                    serialization_version=source_document.serialization_version,
                    source_content_hash=source_document.source_content_hash,
                    start_line=source_document.start_line,
                    end_line=source_document.end_line,
                    start_byte=source_document.start_byte,
                    end_byte=source_document.end_byte,
                    content=source_document.content,
                    provider_id=provider.provider_id,
                    model_id=provider.model_id,
                    model_version=provider.model_version,
                    vector_dimension=vector_dimension,
                    embedding=list(cached_document.embedding),
                )
            )
        return documents

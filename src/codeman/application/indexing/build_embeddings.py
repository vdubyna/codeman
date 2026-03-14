"""Semantic embedding stage for persisted chunk artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from codeman.application.indexing.semantic_index_errors import (
    EmbeddingProviderUnavailableError,
    InvalidSemanticConfigurationError,
)
from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.application.ports.embedding_provider_port import EmbeddingProviderPort
from codeman.config.semantic_indexing import SemanticIndexingConfig
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
]

LOCAL_HASH_PROVIDER_ID = "local-hash"


@dataclass(frozen=True, slots=True)
class BuildEmbeddingsStageResult:
    """Embedding-stage outputs used by semantic index orchestration."""

    provider: EmbeddingProviderDescriptor
    documents: list[SemanticEmbeddingDocument]
    embedding_documents_path: Path


@dataclass(slots=True)
class BuildEmbeddingsStage:
    """Generate semantic embeddings and persist the embedding artifact."""

    artifact_store: ArtifactStorePort
    embedding_provider: EmbeddingProviderPort
    semantic_indexing_config: SemanticIndexingConfig

    def execute(
        self,
        *,
        repository_id: str,
        snapshot_id: str,
        semantic_config_fingerprint: str,
        source_documents: Sequence[SemanticSourceDocument],
    ) -> BuildEmbeddingsStageResult:
        """Generate embeddings from persisted source documents only."""

        provider = self._resolve_provider()
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
                "Semantic indexing failed to initialize the configured local embedding provider.",
                details={
                    "provider_id": provider.provider_id,
                    "local_model_path": str(provider.local_model_path)
                    if provider.local_model_path is not None
                    else None,
                },
            ) from exc

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
        )

    def _resolve_provider(self) -> EmbeddingProviderDescriptor:
        provider_id = self.semantic_indexing_config.provider_id
        if provider_id != LOCAL_HASH_PROVIDER_ID:
            raise EmbeddingProviderUnavailableError(
                "Semantic indexing requires an explicit local embedding provider. "
                "Set CODEMAN_SEMANTIC_PROVIDER_ID=local-hash and "
                "CODEMAN_SEMANTIC_LOCAL_MODEL_PATH=/path/to/local/model before running "
                "`codeman index build-semantic`.",
                details={
                    "provider_id": provider_id,
                    "local_model_path": str(self.semantic_indexing_config.local_model_path)
                    if self.semantic_indexing_config.local_model_path is not None
                    else None,
                },
            )

        local_model_path = self.semantic_indexing_config.local_model_path
        if local_model_path is None or not local_model_path.exists():
            raise EmbeddingProviderUnavailableError(
                "Semantic indexing requires a readable local model path. "
                "Set CODEMAN_SEMANTIC_LOCAL_MODEL_PATH to an existing local path before "
                "running `codeman index build-semantic`.",
                details={
                    "provider_id": provider_id,
                    "local_model_path": str(local_model_path)
                    if local_model_path is not None
                    else None,
                },
            )

        return EmbeddingProviderDescriptor(
            provider_id=provider_id,
            model_id=self.semantic_indexing_config.model_id,
            model_version=self.semantic_indexing_config.model_version,
            is_external_provider=False,
            local_model_path=local_model_path,
        )

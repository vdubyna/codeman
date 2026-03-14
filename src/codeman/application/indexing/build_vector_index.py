"""Semantic vector-index stage for persisted embedding artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from codeman.application.indexing.semantic_index_errors import VectorIndexBuildError
from codeman.application.ports.vector_index_port import VectorIndexPort
from codeman.config.semantic_indexing import SemanticIndexingConfig
from codeman.contracts.retrieval import SemanticEmbeddingDocument, SemanticIndexArtifact

__all__ = [
    "BuildVectorIndexStage",
    "SQLITE_EXACT_VECTOR_ENGINE",
]

SQLITE_EXACT_VECTOR_ENGINE = "sqlite-exact"


@dataclass(slots=True)
class BuildVectorIndexStage:
    """Build the semantic vector artifact for one snapshot/config pair."""

    vector_index: VectorIndexPort
    semantic_indexing_config: SemanticIndexingConfig

    def execute(
        self,
        *,
        repository_id: str,
        snapshot_id: str,
        semantic_config_fingerprint: str,
        documents: Sequence[SemanticEmbeddingDocument],
    ) -> SemanticIndexArtifact:
        """Persist the vector artifact using the configured local backend."""

        if self.semantic_indexing_config.vector_engine != SQLITE_EXACT_VECTOR_ENGINE:
            raise VectorIndexBuildError(
                "Semantic indexing is configured with an unsupported vector engine.",
                details={
                    "vector_engine": self.semantic_indexing_config.vector_engine,
                },
            )

        try:
            return self.vector_index.build(
                repository_id=repository_id,
                snapshot_id=snapshot_id,
                semantic_config_fingerprint=semantic_config_fingerprint,
                documents=documents,
            )
        except VectorIndexBuildError:
            raise
        except Exception as exc:
            raise VectorIndexBuildError(
                f"Vector index build failed for snapshot: {snapshot_id}",
                details={
                    "vector_engine": self.semantic_indexing_config.vector_engine,
                },
            ) from exc

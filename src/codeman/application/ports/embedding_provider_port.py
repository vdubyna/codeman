"""Port for generating deterministic semantic embeddings."""

from __future__ import annotations

from typing import Protocol, Sequence

from codeman.contracts.retrieval import (
    EmbeddingProviderDescriptor,
    SemanticEmbeddingDocument,
    SemanticQueryEmbedding,
    SemanticSourceDocument,
)


class EmbeddingProviderPort(Protocol):
    """Boundary for provider-owned embedding generation."""

    def embed(
        self,
        *,
        provider: EmbeddingProviderDescriptor,
        documents: Sequence[SemanticSourceDocument],
        vector_dimension: int,
    ) -> list[SemanticEmbeddingDocument]:
        """Generate embeddings for source documents using an explicit provider config."""

    def embed_query(
        self,
        *,
        provider: EmbeddingProviderDescriptor,
        query_text: str,
        vector_dimension: int,
    ) -> SemanticQueryEmbedding:
        """Generate an embedding for one retrieval query using the provider lineage."""

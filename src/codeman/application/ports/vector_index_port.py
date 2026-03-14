"""Port for building semantic vector index artifacts."""

from __future__ import annotations

from typing import Protocol, Sequence

from codeman.contracts.retrieval import SemanticEmbeddingDocument, SemanticIndexArtifact


class VectorIndexPort(Protocol):
    """Boundary for adapter-owned semantic vector artifact construction."""

    def build(
        self,
        *,
        repository_id: str,
        snapshot_id: str,
        semantic_config_fingerprint: str,
        documents: Sequence[SemanticEmbeddingDocument],
    ) -> SemanticIndexArtifact:
        """Build and persist vector index artifacts for one snapshot/config pair."""

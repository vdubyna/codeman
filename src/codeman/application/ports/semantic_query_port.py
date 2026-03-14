"""Port for executing semantic queries against persisted vector artifacts."""

from __future__ import annotations

from typing import Protocol

from codeman.contracts.retrieval import (
    SemanticIndexBuildRecord,
    SemanticQueryEmbedding,
    SemanticQueryResult,
)


class SemanticVectorArtifactCorruptError(Exception):
    """Raised when a persisted semantic vector artifact cannot be trusted."""


class SemanticQueryPort(Protocol):
    """Adapter boundary for repository-scoped semantic query execution."""

    def query(
        self,
        *,
        build: SemanticIndexBuildRecord,
        query_embedding: SemanticQueryEmbedding,
        max_results: int = 20,
    ) -> SemanticQueryResult:
        """Execute one semantic query against the provided build artifact."""

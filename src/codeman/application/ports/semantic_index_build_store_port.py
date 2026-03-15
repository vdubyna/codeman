"""Persistence port for semantic index-build attribution records."""

from __future__ import annotations

from typing import Protocol

from codeman.contracts.retrieval import SemanticIndexBuildRecord


class SemanticIndexBuildStorePort(Protocol):
    """Persistence boundary for semantic-index build metadata."""

    def initialize(self) -> None:
        """Prepare semantic index-build persistence for use."""

    def create_build(self, build: SemanticIndexBuildRecord) -> SemanticIndexBuildRecord:
        """Persist one semantic-index build record."""

    def get_latest_build_for_snapshot(
        self,
        snapshot_id: str,
        semantic_config_fingerprint: str,
    ) -> SemanticIndexBuildRecord | None:
        """Return the latest semantic build recorded for a snapshot/config pair."""

    def get_latest_build_for_repository(
        self,
        repository_id: str,
        semantic_config_fingerprint: str,
    ) -> SemanticIndexBuildRecord | None:
        """Return the latest semantic build for the repository's current snapshot/config pair."""

    def get_by_build_id(self, build_id: str) -> SemanticIndexBuildRecord | None:
        """Return one semantic build by its stable identifier."""

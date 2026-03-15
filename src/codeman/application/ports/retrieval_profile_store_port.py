"""Persistence port for retrieval-strategy profile records."""

from __future__ import annotations

from typing import Protocol

from codeman.contracts.configuration import RetrievalStrategyProfileRecord


class RetrievalStrategyProfileStorePort(Protocol):
    """Persistence boundary for workspace-local retrieval profiles."""

    def initialize(self) -> None:
        """Prepare the retrieval-profile store for use."""

    def get_by_name(self, name: str) -> RetrievalStrategyProfileRecord | None:
        """Return the saved profile for an exact name match, if present."""

    def list_by_profile_id(self, profile_id: str) -> list[RetrievalStrategyProfileRecord]:
        """Return all saved profiles that share the given stable content id."""

    def list_profiles(self) -> list[RetrievalStrategyProfileRecord]:
        """Return all saved profiles in deterministic operator-facing order."""

    def create_profile(
        self, profile: RetrievalStrategyProfileRecord
    ) -> RetrievalStrategyProfileRecord:
        """Persist one retrieval profile record."""

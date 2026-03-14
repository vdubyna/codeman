"""Persistence port for lexical index-build attribution records."""

from __future__ import annotations

from typing import Protocol

from codeman.contracts.retrieval import LexicalIndexBuildRecord


class IndexBuildStorePort(Protocol):
    """Persistence boundary for lexical-index build metadata."""

    def initialize(self) -> None:
        """Prepare index-build persistence for use."""

    def create_build(self, build: LexicalIndexBuildRecord) -> LexicalIndexBuildRecord:
        """Persist one lexical-index build record."""

    def get_latest_build_for_snapshot(
        self,
        snapshot_id: str,
    ) -> LexicalIndexBuildRecord | None:
        """Return the latest lexical build recorded for a snapshot."""

    def get_latest_build_for_repository(
        self,
        repository_id: str,
    ) -> LexicalIndexBuildRecord | None:
        """Return the latest lexical build for the repository's current snapshot."""

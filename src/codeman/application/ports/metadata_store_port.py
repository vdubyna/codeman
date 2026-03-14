"""Ports for metadata persistence used by application services."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from codeman.contracts.repository import RepositoryRecord


class RepositoryMetadataStorePort(Protocol):
    """Persistence boundary for repository registration metadata."""

    def initialize(self) -> None:
        """Prepare the metadata store for use."""

    def get_by_canonical_path(self, canonical_path: Path) -> RepositoryRecord | None:
        """Return a repository record if the canonical path is already registered."""

    def create_repository(
        self,
        *,
        repository_name: str,
        canonical_path: Path,
        requested_path: Path,
    ) -> RepositoryRecord:
        """Persist a newly registered repository."""

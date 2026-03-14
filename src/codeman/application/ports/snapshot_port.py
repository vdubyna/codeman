"""Ports for repository snapshotting workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

from codeman.contracts.repository import SnapshotRecord


@dataclass(frozen=True, slots=True)
class ResolvedRevision:
    """Resolved immutable revision identity for a repository snapshot."""

    identity: str
    source: Literal["git", "filesystem_fingerprint"]


class RevisionResolverPort(Protocol):
    """Resolve immutable revision identity for snapshot creation."""

    def resolve(self, repository_path: Path) -> ResolvedRevision:
        """Return the best available immutable revision descriptor."""


class SnapshotMetadataStorePort(Protocol):
    """Persistence boundary for snapshot metadata records."""

    def initialize(self) -> None:
        """Prepare snapshot persistence for use."""

    def get_by_snapshot_id(self, snapshot_id: str) -> SnapshotRecord | None:
        """Return a snapshot record if the identifier exists."""

    def get_latest_indexed_snapshot(self, repository_id: str) -> SnapshotRecord | None:
        """Return the latest snapshot with extracted sources and completed chunking."""

    def create_snapshot(
        self,
        *,
        snapshot_id: str,
        repository_id: str,
        revision_identity: str,
        revision_source: Literal["git", "filesystem_fingerprint"],
        manifest_path: Path,
        created_at: datetime,
    ) -> SnapshotRecord:
        """Persist immutable snapshot metadata."""

    def mark_source_inventory_extracted(
        self,
        *,
        snapshot_id: str,
        extracted_at: datetime,
    ) -> None:
        """Record that source inventory extraction completed for a snapshot."""

    def mark_chunks_generated(
        self,
        *,
        snapshot_id: str,
        generated_at: datetime,
        indexing_config_fingerprint: str,
    ) -> None:
        """Record that chunk generation completed for a snapshot."""

"""Ports for runtime artifact persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from codeman.contracts.repository import SnapshotManifestDocument


class ArtifactStorePort(Protocol):
    """Filesystem-backed artifact persistence boundary."""

    def write_snapshot_manifest(self, manifest: SnapshotManifestDocument) -> Path:
        """Persist a normalized snapshot manifest and return its path."""

"""Ports for runtime artifact persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from codeman.contracts.chunking import ChunkPayloadDocument
from codeman.contracts.repository import SnapshotManifestDocument
from codeman.contracts.retrieval import SemanticEmbeddingArtifactDocument


class ArtifactStorePort(Protocol):
    """Filesystem-backed artifact persistence boundary."""

    def write_snapshot_manifest(self, manifest: SnapshotManifestDocument) -> Path:
        """Persist a normalized snapshot manifest and return its path."""

    def write_chunk_payload(self, payload: ChunkPayloadDocument, *, snapshot_id: str) -> Path:
        """Persist a normalized chunk payload artifact and return its path."""

    def read_chunk_payload(self, payload_path: Path) -> ChunkPayloadDocument:
        """Load a previously persisted chunk payload artifact."""

    def write_embedding_documents(
        self,
        artifact: SemanticEmbeddingArtifactDocument,
        *,
        snapshot_id: str,
        semantic_config_fingerprint: str,
    ) -> Path:
        """Persist one semantic embedding artifact and return its path."""

    def read_embedding_documents(
        self,
        artifact_path: Path,
    ) -> SemanticEmbeddingArtifactDocument:
        """Load a previously persisted semantic embedding artifact."""

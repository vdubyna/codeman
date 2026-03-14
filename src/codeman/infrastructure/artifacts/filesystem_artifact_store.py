"""Persist runtime artifacts under the resolved workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.contracts.chunking import ChunkPayloadDocument
from codeman.contracts.repository import SnapshotManifestDocument


@dataclass(slots=True)
class FilesystemArtifactStore(ArtifactStorePort):
    """Persist snapshot manifests under `.codeman/artifacts/`."""

    artifacts_root: Path

    def write_snapshot_manifest(self, manifest: SnapshotManifestDocument) -> Path:
        """Write a normalized JSON manifest for the snapshot."""

        destination = self.artifacts_root / "snapshots" / manifest.snapshot_id / "manifest.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return destination

    def write_chunk_payload(self, payload: ChunkPayloadDocument, *, snapshot_id: str) -> Path:
        """Write a normalized JSON payload artifact for a retrieval chunk."""

        destination = (
            self.artifacts_root
            / "snapshots"
            / snapshot_id
            / "chunks"
            / f"{payload.chunk_id}.json"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
        return destination

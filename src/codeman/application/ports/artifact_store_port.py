"""Ports for runtime artifact persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from codeman.contracts.chunking import ChunkPayloadDocument
from codeman.contracts.evaluation import (
    BenchmarkMetricsArtifactDocument,
    BenchmarkRunArtifactDocument,
)
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

    def write_benchmark_run_artifact(
        self,
        artifact: BenchmarkRunArtifactDocument,
        *,
        run_id: str,
    ) -> Path:
        """Persist one normalized benchmark-run artifact and return its path."""

    def read_benchmark_run_artifact(
        self,
        artifact_path: Path,
    ) -> BenchmarkRunArtifactDocument:
        """Load one previously persisted benchmark-run artifact."""

    def write_benchmark_metrics_artifact(
        self,
        artifact: BenchmarkMetricsArtifactDocument,
        *,
        run_id: str,
    ) -> Path:
        """Persist one normalized benchmark-metrics artifact and return its path."""

    def read_benchmark_metrics_artifact(
        self,
        artifact_path: Path,
    ) -> BenchmarkMetricsArtifactDocument:
        """Load one previously persisted benchmark-metrics artifact."""

    def write_benchmark_report(
        self,
        report_markdown: str,
        *,
        run_id: str,
    ) -> Path:
        """Persist one deterministic benchmark report artifact and return its path."""

    def read_benchmark_report(self, artifact_path: Path) -> str:
        """Load one previously persisted benchmark report artifact."""

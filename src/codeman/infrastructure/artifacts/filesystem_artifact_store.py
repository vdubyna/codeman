"""Persist runtime artifacts under the resolved workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.contracts.chunking import ChunkPayloadDocument
from codeman.contracts.evaluation import (
    BenchmarkMetricsArtifactDocument,
    BenchmarkRunArtifactDocument,
)
from codeman.contracts.repository import SnapshotManifestDocument
from codeman.contracts.retrieval import SemanticEmbeddingArtifactDocument


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
            self.artifacts_root / "snapshots" / snapshot_id / "chunks" / f"{payload.chunk_id}.json"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
        return destination

    def read_chunk_payload(self, payload_path: Path) -> ChunkPayloadDocument:
        """Load a normalized JSON payload artifact for a retrieval chunk."""

        return ChunkPayloadDocument.model_validate_json(
            payload_path.read_text(encoding="utf-8"),
        )

    def write_embedding_documents(
        self,
        artifact: SemanticEmbeddingArtifactDocument,
        *,
        snapshot_id: str,
        semantic_config_fingerprint: str,
    ) -> Path:
        """Write a normalized JSON artifact for semantic embedding documents."""

        destination = (
            self.artifacts_root
            / "snapshots"
            / snapshot_id
            / "embeddings"
            / semantic_config_fingerprint
            / "documents.json"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
        return destination

    def read_embedding_documents(
        self,
        artifact_path: Path,
    ) -> SemanticEmbeddingArtifactDocument:
        """Load a normalized JSON artifact for semantic embedding documents."""

        return SemanticEmbeddingArtifactDocument.model_validate_json(
            artifact_path.read_text(encoding="utf-8"),
        )

    def write_benchmark_run_artifact(
        self,
        artifact: BenchmarkRunArtifactDocument,
        *,
        run_id: str,
    ) -> Path:
        """Write a normalized JSON artifact for one benchmark execution."""

        destination = self.artifacts_root / "benchmarks" / run_id / "run.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
        return destination

    def read_benchmark_run_artifact(
        self,
        artifact_path: Path,
    ) -> BenchmarkRunArtifactDocument:
        """Load a normalized JSON artifact for one benchmark execution."""

        return BenchmarkRunArtifactDocument.model_validate_json(
            artifact_path.read_text(encoding="utf-8"),
        )

    def write_benchmark_metrics_artifact(
        self,
        artifact: BenchmarkMetricsArtifactDocument,
        *,
        run_id: str,
    ) -> Path:
        """Write a normalized JSON artifact for one benchmark metrics summary."""

        destination = self.artifacts_root / "benchmarks" / run_id / "metrics.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
        return destination

    def read_benchmark_metrics_artifact(
        self,
        artifact_path: Path,
    ) -> BenchmarkMetricsArtifactDocument:
        """Load a normalized JSON artifact for one benchmark metrics summary."""

        return BenchmarkMetricsArtifactDocument.model_validate_json(
            artifact_path.read_text(encoding="utf-8"),
        )

    def write_benchmark_report(
        self,
        report_markdown: str,
        *,
        run_id: str,
    ) -> Path:
        """Write one deterministic Markdown report for a benchmark run."""

        destination = self.artifacts_root / "benchmarks" / run_id / "report.md"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(report_markdown, encoding="utf-8")
        return destination

    def read_benchmark_report(self, artifact_path: Path) -> str:
        """Load one persisted Markdown benchmark report."""

        return artifact_path.read_text(encoding="utf-8")

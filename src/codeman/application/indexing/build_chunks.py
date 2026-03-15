"""Generate structure-aware retrieval chunks from extracted source inventory."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from codeman.application.indexing.chunk_materializer import (
    ChunkMaterializer,
    build_chunk_id,
)
from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.application.ports.cache_store_port import CacheStorePort
from codeman.application.ports.chunk_store_port import ChunkStorePort
from codeman.application.ports.chunker_port import ChunkerRegistryPort
from codeman.application.ports.metadata_store_port import RepositoryMetadataStorePort
from codeman.application.ports.parser_port import ParserRegistryPort
from codeman.application.ports.snapshot_port import (
    ResolvedRevision,
    RevisionResolverPort,
    SnapshotMetadataStorePort,
)
from codeman.application.ports.source_inventory_port import SourceInventoryStorePort
from codeman.application.provenance.record_run_provenance import (
    RecordRunConfigurationProvenanceUseCase,
)
from codeman.config.indexing import IndexingConfig, build_indexing_fingerprint
from codeman.contracts.cache import CacheUsageSummary
from codeman.contracts.chunking import (
    BuildChunksRequest,
    BuildChunksResult,
    ChunkFileDiagnostic,
    ChunkGenerationDiagnostics,
    ChunkRecord,
)
from codeman.contracts.configuration import (
    RecordRunConfigurationProvenanceRequest,
    RunProvenanceWorkflowContext,
)
from codeman.contracts.errors import ErrorCode
from codeman.runtime import RuntimePaths, provision_runtime_paths

__all__ = [
    "BuildChunksError",
    "ChunkSnapshotNotFoundError",
    "ChunkSnapshotSourceMismatchError",
    "SourceInventoryMissingError",
    "BuildChunksUseCase",
    "build_chunk_id",
]


class BuildChunksError(Exception):
    """Base exception for chunk-generation failures."""

    exit_code = 30
    error_code = ErrorCode.CHUNK_GENERATION_FAILED

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ChunkSnapshotNotFoundError(BuildChunksError):
    """Raised when chunk generation is requested for an unknown snapshot."""

    exit_code = 26
    error_code = ErrorCode.SNAPSHOT_NOT_FOUND


class ChunkSnapshotSourceMismatchError(BuildChunksError):
    """Raised when the live repository no longer matches the stored snapshot."""

    exit_code = 27
    error_code = ErrorCode.SNAPSHOT_SOURCE_MISMATCH


class SourceInventoryMissingError(BuildChunksError):
    """Raised when chunking is requested before source extraction exists."""

    exit_code = 29
    error_code = ErrorCode.SOURCE_INVENTORY_MISSING


def _count_chunks_by_language(chunks: list[ChunkRecord]) -> dict[str, int]:
    counts = Counter(chunk.language for chunk in chunks)
    return dict(sorted(counts.items()))


def _count_chunks_by_strategy(chunks: list[ChunkRecord]) -> dict[str, int]:
    counts = Counter(chunk.strategy for chunk in chunks)
    return dict(sorted(counts.items()))


def _merge_cache_summaries(*summaries: CacheUsageSummary) -> CacheUsageSummary:
    return CacheUsageSummary(
        parser_entries_reused=sum(summary.parser_entries_reused for summary in summaries),
        parser_entries_regenerated=sum(summary.parser_entries_regenerated for summary in summaries),
        chunk_entries_reused=sum(summary.chunk_entries_reused for summary in summaries),
        chunk_entries_regenerated=sum(summary.chunk_entries_regenerated for summary in summaries),
        embedding_documents_reused=sum(summary.embedding_documents_reused for summary in summaries),
        embedding_documents_regenerated=sum(
            summary.embedding_documents_regenerated for summary in summaries
        ),
    )


@dataclass(slots=True)
class BuildChunksUseCase:
    """Generate and persist retrieval chunks for a snapshot."""

    runtime_paths: RuntimePaths
    repository_store: RepositoryMetadataStorePort
    snapshot_store: SnapshotMetadataStorePort
    source_inventory_store: SourceInventoryStorePort
    chunk_store: ChunkStorePort
    revision_resolver: RevisionResolverPort
    parser_registry: ParserRegistryPort
    chunker_registry: ChunkerRegistryPort
    artifact_store: ArtifactStorePort
    cache_store: CacheStorePort
    indexing_config: IndexingConfig
    record_run_provenance: RecordRunConfigurationProvenanceUseCase | None = None

    def execute(self, request: BuildChunksRequest) -> BuildChunksResult:
        """Generate and persist chunk metadata and payloads for a snapshot."""

        provision_runtime_paths(self.runtime_paths)
        self.snapshot_store.initialize()
        self.source_inventory_store.initialize()
        self.chunk_store.initialize()

        snapshot = self.snapshot_store.get_by_snapshot_id(request.snapshot_id)
        if snapshot is None:
            raise ChunkSnapshotNotFoundError(
                f"Snapshot is not registered: {request.snapshot_id}",
            )

        repository = self.repository_store.get_by_repository_id(snapshot.repository_id)
        if repository is None:
            raise BuildChunksError(
                f"Snapshot points to an unknown repository: {snapshot.repository_id}",
            )

        self._ensure_snapshot_matches_repository(
            snapshot_revision=ResolvedRevision(
                identity=snapshot.revision_identity,
                source=snapshot.revision_source,
            ),
            repository_path=repository.canonical_path,
            snapshot_id=snapshot.snapshot_id,
        )

        source_files = self.source_inventory_store.list_by_snapshot(snapshot.snapshot_id)
        if not source_files and snapshot.source_inventory_extracted_at is None:
            raise SourceInventoryMissingError(
                "Source inventory is missing for snapshot; run "
                f"`codeman index extract-sources {snapshot.snapshot_id}` first.",
            )

        created_at = datetime.now(UTC)
        current_fingerprint = build_indexing_fingerprint(self.indexing_config)
        file_diagnostics: list[ChunkFileDiagnostic] = []
        generated_chunks: list[ChunkRecord] = []
        cache_summaries: list[CacheUsageSummary] = []
        materializer = ChunkMaterializer(
            parser_registry=self.parser_registry,
            chunker_registry=self.chunker_registry,
            artifact_store=self.artifact_store,
            cache_store=self.cache_store,
        )

        try:
            for source_file in source_files:
                source_result = materializer.build_for_source_file(
                    source_file=source_file,
                    repository_path=repository.canonical_path,
                    created_at=created_at,
                    indexing_config_fingerprint=current_fingerprint,
                )
                generated_chunks.extend(source_result.chunk_records)
                file_diagnostics.append(source_result.diagnostic)
                cache_summaries.append(source_result.cache_summary)
            persisted_chunks = self.chunk_store.upsert_chunks(generated_chunks)
            self.snapshot_store.mark_chunks_generated(
                snapshot_id=snapshot.snapshot_id,
                generated_at=created_at,
                indexing_config_fingerprint=current_fingerprint,
            )
        except BuildChunksError:
            raise
        except Exception as exc:
            raise BuildChunksError(
                f"Chunk generation failed for snapshot: {snapshot.snapshot_id}",
            ) from exc

        diagnostics = ChunkGenerationDiagnostics(
            chunks_by_language=_count_chunks_by_language(persisted_chunks),
            chunks_by_strategy=_count_chunks_by_strategy(persisted_chunks),
            total_chunks=len(persisted_chunks),
            fallback_file_count=sum(
                1 for diagnostic in file_diagnostics if diagnostic.mode == "fallback"
            ),
            degraded_file_count=sum(
                1
                for diagnostic in file_diagnostics
                if diagnostic.mode == "fallback" and diagnostic.chunk_count > 0
            ),
            skipped_file_count=sum(
                1 for diagnostic in file_diagnostics if diagnostic.chunk_count == 0
            ),
            file_diagnostics=file_diagnostics,
            cache_summary=_merge_cache_summaries(*cache_summaries),
        )
        snapshot = snapshot.model_copy(
            update={
                "chunk_generation_completed_at": created_at,
                "indexing_config_fingerprint": current_fingerprint,
            }
        )
        provenance_run_id: str | None = None
        if self.record_run_provenance is not None:
            provenance = self.record_run_provenance.execute(
                RecordRunConfigurationProvenanceRequest(
                    workflow_type="index.build-chunks",
                    repository_id=repository.repository_id,
                    snapshot_id=snapshot.snapshot_id,
                    indexing_config_fingerprint=current_fingerprint,
                    workflow_context=RunProvenanceWorkflowContext(
                        cache_summary=diagnostics.cache_summary,
                    ),
                )
            )
            provenance_run_id = provenance.run_id
        return BuildChunksResult(
            run_id=provenance_run_id,
            repository=repository,
            snapshot=snapshot,
            chunks=persisted_chunks,
            diagnostics=diagnostics,
        )

    def _ensure_snapshot_matches_repository(
        self,
        *,
        snapshot_revision: ResolvedRevision,
        repository_path: Path,
        snapshot_id: str,
    ) -> None:
        """Fail safely if the live repository state diverges from the stored snapshot."""

        current_revision = self.revision_resolver.resolve(repository_path)
        if current_revision == snapshot_revision:
            return

        raise ChunkSnapshotSourceMismatchError(
            "Snapshot revision no longer matches the live repository state; "
            f"create a new snapshot before generating chunks: {snapshot_id}",
        )

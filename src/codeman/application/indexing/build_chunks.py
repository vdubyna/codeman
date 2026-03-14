"""Generate structure-aware retrieval chunks from extracted source inventory."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.application.ports.chunk_store_port import ChunkStorePort
from codeman.application.ports.chunker_port import ChunkDraft, ChunkerRegistryPort
from codeman.application.ports.metadata_store_port import RepositoryMetadataStorePort
from codeman.application.ports.parser_port import ParserFailure, ParserRegistryPort
from codeman.application.ports.snapshot_port import (
    ResolvedRevision,
    RevisionResolverPort,
    SnapshotMetadataStorePort,
)
from codeman.application.ports.source_inventory_port import SourceInventoryStorePort
from codeman.contracts.chunking import (
    BuildChunksRequest,
    BuildChunksResult,
    ChunkFileDiagnostic,
    ChunkGenerationDiagnostics,
    ChunkPayloadDocument,
    ChunkRecord,
)
from codeman.contracts.errors import ErrorCode
from codeman.contracts.repository import SourceFileRecord
from codeman.runtime import RuntimePaths, provision_runtime_paths

CHUNK_SERIALIZATION_VERSION = "1"


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


def build_chunk_id(
    *,
    source_file_id: str,
    strategy: str,
    start_line: int,
    end_line: int,
    start_byte: int,
    end_byte: int,
    serialization_version: str = CHUNK_SERIALIZATION_VERSION,
) -> str:
    """Build a deterministic identifier for a chunk span."""

    payload = ":".join(
        [
            source_file_id,
            strategy,
            str(start_line),
            str(end_line),
            str(start_byte),
            str(end_byte),
            serialization_version,
        ],
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _count_chunks_by_language(chunks: list[ChunkRecord]) -> dict[str, int]:
    counts = Counter(chunk.language for chunk in chunks)
    return dict(sorted(counts.items()))


def _count_chunks_by_strategy(chunks: list[ChunkRecord]) -> dict[str, int]:
    counts = Counter(chunk.strategy for chunk in chunks)
    return dict(sorted(counts.items()))


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
        file_diagnostics: list[ChunkFileDiagnostic] = []
        generated_chunks: list[ChunkRecord] = []

        try:
            for source_file in source_files:
                source_text = self._read_source_text(
                    repository_path=repository.canonical_path,
                    relative_path=source_file.relative_path,
                )
                chunk_records, diagnostic = self._build_chunks_for_source_file(
                    source_file=source_file,
                    source_text=source_text,
                    created_at=created_at,
                )
                generated_chunks.extend(chunk_records)
                file_diagnostics.append(diagnostic)
            persisted_chunks = self.chunk_store.upsert_chunks(generated_chunks)
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
        )
        return BuildChunksResult(
            repository=repository,
            snapshot=snapshot,
            chunks=persisted_chunks,
            diagnostics=diagnostics,
        )

    def _build_chunks_for_source_file(
        self,
        *,
        source_file: SourceFileRecord,
        source_text: str,
        created_at: datetime,
    ) -> tuple[list[ChunkRecord], ChunkFileDiagnostic]:
        """Generate chunk records and one per-file diagnostic."""

        parser = self.parser_registry.get(source_file.language)
        structural_chunker = self.chunker_registry.get_structural(source_file.language)
        fallback_chunker = self.chunker_registry.get_fallback(source_file.language)
        preferred_strategy = (
            structural_chunker.strategy_name
            if structural_chunker is not None
            else fallback_chunker.strategy_name
        )
        reason: str | None = None
        message: str | None = None

        try:
            if parser is None or structural_chunker is None:
                raise ParserFailure(
                    "No preferred structural parser is registered for: "
                    f"{source_file.relative_path}",
                )

            drafts = structural_chunker.chunk(
                source_text=source_text,
                relative_path=source_file.relative_path,
                boundaries=parser.parse(
                    source_text=source_text,
                    relative_path=source_file.relative_path,
                ),
            )
            if not drafts:
                raise ParserFailure(
                    f"No structural boundaries detected for: {source_file.relative_path}",
                )
            mode = "structural"
            strategy_used = structural_chunker.strategy_name
        except Exception as exc:
            drafts = fallback_chunker.chunk(
                source_text=source_text,
                relative_path=source_file.relative_path,
            )
            mode = "fallback"
            strategy_used = fallback_chunker.strategy_name
            reason = "preferred_path_unavailable"
            message = str(exc)

        chunk_records = self._persist_chunk_payloads(
            source_file=source_file,
            drafts=drafts,
            created_at=created_at,
        )
        diagnostic = ChunkFileDiagnostic(
            source_file_id=source_file.source_file_id,
            relative_path=source_file.relative_path,
            language=source_file.language,
            preferred_strategy=preferred_strategy,
            strategy_used=strategy_used,
            mode=mode,
            chunk_count=len(chunk_records),
            reason=reason,
            message=message,
        )
        return chunk_records, diagnostic

    def _persist_chunk_payloads(
        self,
        *,
        source_file: SourceFileRecord,
        drafts: tuple[ChunkDraft, ...],
        created_at: datetime,
    ) -> list[ChunkRecord]:
        """Write payload artifacts and convert drafts into persisted records."""

        records: list[ChunkRecord] = []
        for draft in sorted(
            drafts,
            key=lambda item: (
                item.start_line,
                item.start_byte,
                item.end_line,
                item.end_byte,
                item.strategy,
            ),
        ):
            chunk_id = build_chunk_id(
                source_file_id=source_file.source_file_id,
                strategy=draft.strategy,
                start_line=draft.start_line,
                end_line=draft.end_line,
                start_byte=draft.start_byte,
                end_byte=draft.end_byte,
            )
            payload = ChunkPayloadDocument(
                chunk_id=chunk_id,
                snapshot_id=source_file.snapshot_id,
                repository_id=source_file.repository_id,
                source_file_id=source_file.source_file_id,
                relative_path=source_file.relative_path,
                language=source_file.language,
                strategy=draft.strategy,
                serialization_version=CHUNK_SERIALIZATION_VERSION,
                source_content_hash=source_file.content_hash,
                start_line=draft.start_line,
                end_line=draft.end_line,
                start_byte=draft.start_byte,
                end_byte=draft.end_byte,
                content=draft.content,
            )
            payload_path = self.artifact_store.write_chunk_payload(
                payload,
                snapshot_id=source_file.snapshot_id,
            )
            records.append(
                ChunkRecord(
                    chunk_id=chunk_id,
                    snapshot_id=source_file.snapshot_id,
                    repository_id=source_file.repository_id,
                    source_file_id=source_file.source_file_id,
                    relative_path=source_file.relative_path,
                    language=source_file.language,
                    strategy=draft.strategy,
                    serialization_version=CHUNK_SERIALIZATION_VERSION,
                    source_content_hash=source_file.content_hash,
                    start_line=draft.start_line,
                    end_line=draft.end_line,
                    start_byte=draft.start_byte,
                    end_byte=draft.end_byte,
                    payload_path=payload_path,
                    created_at=created_at,
                ),
            )

        return records

    @staticmethod
    def _read_source_text(*, repository_path: Path, relative_path: str) -> str:
        """Load a source file body as text for chunk generation."""

        file_path = repository_path / relative_path
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return file_path.read_text(encoding="utf-8", errors="replace")

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

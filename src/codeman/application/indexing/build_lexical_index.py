"""Build snapshot-scoped lexical index artifacts from persisted chunk payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter_ns
from uuid import uuid4

from pydantic import ValidationError

from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.application.ports.chunk_store_port import ChunkStorePort
from codeman.application.ports.index_build_store_port import IndexBuildStorePort
from codeman.application.ports.lexical_index_port import LexicalIndexPort
from codeman.application.ports.metadata_store_port import RepositoryMetadataStorePort
from codeman.application.ports.snapshot_port import SnapshotMetadataStorePort
from codeman.application.provenance.record_run_provenance import (
    RecordRunConfigurationProvenanceUseCase,
)
from codeman.config.indexing import IndexingConfig, build_indexing_fingerprint
from codeman.contracts.chunking import ChunkPayloadDocument, ChunkRecord
from codeman.contracts.configuration import (
    RecordRunConfigurationProvenanceRequest,
    RunProvenanceWorkflowContext,
)
from codeman.contracts.errors import ErrorCode
from codeman.contracts.retrieval import (
    BuildLexicalIndexRequest,
    BuildLexicalIndexResult,
    LexicalIndexBuildDiagnostics,
    LexicalIndexBuildRecord,
    LexicalIndexDocument,
)
from codeman.runtime import RuntimePaths, provision_runtime_paths

__all__ = [
    "BuildLexicalIndexError",
    "LexicalSnapshotNotFoundError",
    "ChunkBaselineMissingError",
    "ChunkPayloadMissingError",
    "ChunkPayloadCorruptError",
    "BuildLexicalIndexUseCase",
]


class BuildLexicalIndexError(Exception):
    """Base exception for lexical-index build failures."""

    exit_code = 33
    error_code = ErrorCode.LEXICAL_INDEX_BUILD_FAILED

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LexicalSnapshotNotFoundError(BuildLexicalIndexError):
    """Raised when lexical index building is requested for an unknown snapshot."""

    exit_code = 26
    error_code = ErrorCode.SNAPSHOT_NOT_FOUND


class ChunkBaselineMissingError(BuildLexicalIndexError):
    """Raised when chunk generation has not produced a usable baseline yet."""

    exit_code = 34
    error_code = ErrorCode.CHUNK_BASELINE_MISSING


class ChunkPayloadMissingError(BuildLexicalIndexError):
    """Raised when a persisted chunk payload artifact cannot be loaded."""

    exit_code = 35
    error_code = ErrorCode.CHUNK_PAYLOAD_MISSING


class ChunkPayloadCorruptError(BuildLexicalIndexError):
    """Raised when a persisted chunk payload artifact is unreadable or mismatched."""

    exit_code = 36
    error_code = ErrorCode.CHUNK_PAYLOAD_CORRUPT


def _missing_chunk_baseline_message(
    snapshot_id: str,
    *,
    current_configuration: bool = False,
) -> str:
    qualifier = " and current configuration" if current_configuration else ""
    return (
        f"Chunk baseline is missing for snapshot{qualifier}; run "
        f"`codeman index build-chunks {snapshot_id}` first."
    )


def _ordered_chunks(chunks: list[ChunkRecord]) -> list[ChunkRecord]:
    return sorted(
        chunks,
        key=lambda chunk: (
            chunk.relative_path,
            chunk.start_line,
            chunk.start_byte,
            chunk.chunk_id,
        ),
    )


def _payload_matches_chunk(
    *,
    chunk: ChunkRecord,
    payload: ChunkPayloadDocument,
) -> bool:
    return (
        payload.chunk_id == chunk.chunk_id
        and payload.snapshot_id == chunk.snapshot_id
        and payload.repository_id == chunk.repository_id
        and payload.source_file_id == chunk.source_file_id
        and payload.relative_path == chunk.relative_path
        and payload.language == chunk.language
        and payload.strategy == chunk.strategy
        and payload.source_content_hash == chunk.source_content_hash
        and payload.start_line == chunk.start_line
        and payload.end_line == chunk.end_line
        and payload.start_byte == chunk.start_byte
        and payload.end_byte == chunk.end_byte
    )


@dataclass(slots=True)
class BuildLexicalIndexUseCase:
    """Build a snapshot-scoped lexical index from persisted chunk artifacts."""

    runtime_paths: RuntimePaths
    repository_store: RepositoryMetadataStorePort
    snapshot_store: SnapshotMetadataStorePort
    chunk_store: ChunkStorePort
    artifact_store: ArtifactStorePort
    lexical_index: LexicalIndexPort
    index_build_store: IndexBuildStorePort
    indexing_config: IndexingConfig
    record_run_provenance: RecordRunConfigurationProvenanceUseCase | None = None

    def execute(self, request: BuildLexicalIndexRequest) -> BuildLexicalIndexResult:
        """Build and record lexical artifacts for the requested snapshot."""

        provision_runtime_paths(self.runtime_paths)
        self.repository_store.initialize()
        self.snapshot_store.initialize()
        self.chunk_store.initialize()
        self.index_build_store.initialize()

        snapshot = self.snapshot_store.get_by_snapshot_id(request.snapshot_id)
        if snapshot is None:
            raise LexicalSnapshotNotFoundError(
                f"Snapshot is not registered: {request.snapshot_id}",
            )

        repository = self.repository_store.get_by_repository_id(snapshot.repository_id)
        if repository is None:
            raise BuildLexicalIndexError(
                f"Snapshot points to an unknown repository: {snapshot.repository_id}",
            )

        chunks = self.chunk_store.list_by_snapshot(snapshot.snapshot_id)
        if not chunks:
            raise ChunkBaselineMissingError(
                _missing_chunk_baseline_message(snapshot.snapshot_id),
            )
        current_indexing_fingerprint = build_indexing_fingerprint(self.indexing_config)
        if (
            snapshot.indexing_config_fingerprint is not None
            and snapshot.indexing_config_fingerprint != current_indexing_fingerprint
        ):
            raise ChunkBaselineMissingError(
                _missing_chunk_baseline_message(
                    snapshot.snapshot_id,
                    current_configuration=True,
                )
            )

        build_started_ns = perf_counter_ns()
        try:
            documents = [self._load_document(chunk) for chunk in _ordered_chunks(chunks)]
            artifact = self.lexical_index.build(
                repository_id=repository.repository_id,
                snapshot_id=snapshot.snapshot_id,
                documents=documents,
            )
        except BuildLexicalIndexError:
            raise
        except Exception as exc:
            raise BuildLexicalIndexError(
                f"Lexical index build failed for snapshot: {snapshot.snapshot_id}",
            ) from exc
        build_duration_ms = (perf_counter_ns() - build_started_ns) // 1_000_000

        created_at = datetime.now(UTC)
        indexing_config_fingerprint = (
            snapshot.indexing_config_fingerprint or current_indexing_fingerprint
        )
        build_record = self.index_build_store.create_build(
            LexicalIndexBuildRecord(
                build_id=uuid4().hex,
                repository_id=repository.repository_id,
                snapshot_id=snapshot.snapshot_id,
                revision_identity=snapshot.revision_identity,
                revision_source=snapshot.revision_source,
                indexing_config_fingerprint=indexing_config_fingerprint,
                lexical_engine=artifact.lexical_engine,
                tokenizer_spec=artifact.tokenizer_spec,
                indexed_fields=list(artifact.indexed_fields),
                chunks_indexed=artifact.chunks_indexed,
                build_duration_ms=build_duration_ms,
                index_path=artifact.index_path,
                created_at=created_at,
            ),
        )
        provenance_run_id: str | None = None
        if self.record_run_provenance is not None:
            provenance = self.record_run_provenance.execute(
                RecordRunConfigurationProvenanceRequest(
                    workflow_type="index.build-lexical",
                    repository_id=repository.repository_id,
                    snapshot_id=snapshot.snapshot_id,
                    indexing_config_fingerprint=build_record.indexing_config_fingerprint,
                    workflow_context=RunProvenanceWorkflowContext(
                        lexical_build_id=build_record.build_id,
                    ),
                )
            )
            provenance_run_id = provenance.run_id
        return BuildLexicalIndexResult(
            run_id=provenance_run_id,
            repository=repository,
            snapshot=snapshot,
            build=build_record,
            diagnostics=LexicalIndexBuildDiagnostics(
                chunks_indexed=artifact.chunks_indexed,
                refreshed_existing_artifact=artifact.refreshed_existing_artifact,
            ),
        )

    def _load_document(self, chunk: ChunkRecord) -> LexicalIndexDocument:
        try:
            payload = self.artifact_store.read_chunk_payload(chunk.payload_path)
        except FileNotFoundError as exc:
            raise ChunkPayloadMissingError(
                f"Chunk payload artifact is missing for chunk: {chunk.chunk_id}",
            ) from exc
        except ValidationError as exc:
            raise ChunkPayloadCorruptError(
                f"Chunk payload artifact is corrupt for chunk: {chunk.chunk_id}",
            ) from exc
        except OSError as exc:
            raise ChunkPayloadMissingError(
                f"Chunk payload artifact is missing for chunk: {chunk.chunk_id}",
            ) from exc

        if not _payload_matches_chunk(chunk=chunk, payload=payload):
            raise ChunkPayloadCorruptError(
                f"Chunk payload artifact is corrupt for chunk: {chunk.chunk_id}",
            )

        return LexicalIndexDocument(
            chunk_id=chunk.chunk_id,
            snapshot_id=chunk.snapshot_id,
            repository_id=chunk.repository_id,
            relative_path=chunk.relative_path,
            language=chunk.language,
            strategy=chunk.strategy,
            content=payload.content,
        )

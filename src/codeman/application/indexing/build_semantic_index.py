"""Build snapshot-scoped semantic index artifacts from persisted chunk payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError

from codeman.application.indexing.build_embeddings import BuildEmbeddingsStage
from codeman.application.indexing.build_vector_index import BuildVectorIndexStage
from codeman.application.indexing.semantic_index_errors import (
    BuildSemanticIndexError,
    EmbeddingProviderUnavailableError,
    InvalidSemanticConfigurationError,
    SemanticChunkBaselineMissingError,
    SemanticChunkPayloadCorruptError,
    SemanticChunkPayloadMissingError,
    SemanticSnapshotNotFoundError,
    VectorIndexBuildError,
)
from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.application.ports.chunk_store_port import ChunkStorePort
from codeman.application.ports.metadata_store_port import RepositoryMetadataStorePort
from codeman.application.ports.semantic_index_build_store_port import (
    SemanticIndexBuildStorePort,
)
from codeman.application.ports.snapshot_port import SnapshotMetadataStorePort
from codeman.application.provenance.record_run_provenance import (
    RecordRunConfigurationProvenanceUseCase,
)
from codeman.config.embedding_providers import EmbeddingProvidersConfig
from codeman.config.semantic_indexing import (
    SemanticIndexingConfig,
    build_semantic_indexing_fingerprint,
)
from codeman.contracts.chunking import ChunkPayloadDocument, ChunkRecord
from codeman.contracts.configuration import (
    RecordRunConfigurationProvenanceRequest,
    RunProvenanceWorkflowContext,
)
from codeman.contracts.retrieval import (
    BuildSemanticIndexRequest,
    BuildSemanticIndexResult,
    SemanticIndexBuildDiagnostics,
    SemanticIndexBuildRecord,
    SemanticSourceDocument,
)
from codeman.runtime import RuntimePaths, provision_runtime_paths

__all__ = [
    "BuildSemanticIndexUseCase",
    "BuildSemanticIndexError",
    "EmbeddingProviderUnavailableError",
    "InvalidSemanticConfigurationError",
    "SemanticChunkBaselineMissingError",
    "SemanticChunkPayloadCorruptError",
    "SemanticChunkPayloadMissingError",
    "SemanticSnapshotNotFoundError",
    "VectorIndexBuildError",
]


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
        and payload.serialization_version == chunk.serialization_version
        and payload.source_content_hash == chunk.source_content_hash
        and payload.start_line == chunk.start_line
        and payload.end_line == chunk.end_line
        and payload.start_byte == chunk.start_byte
        and payload.end_byte == chunk.end_byte
    )


@dataclass(slots=True)
class BuildSemanticIndexUseCase:
    """Build a snapshot-scoped semantic index from persisted chunk artifacts."""

    runtime_paths: RuntimePaths
    repository_store: RepositoryMetadataStorePort
    snapshot_store: SnapshotMetadataStorePort
    chunk_store: ChunkStorePort
    artifact_store: ArtifactStorePort
    embedding_stage: BuildEmbeddingsStage
    vector_index_stage: BuildVectorIndexStage
    semantic_index_build_store: SemanticIndexBuildStorePort
    semantic_indexing_config: SemanticIndexingConfig
    embedding_providers_config: EmbeddingProvidersConfig
    record_run_provenance: RecordRunConfigurationProvenanceUseCase | None = None

    def execute(self, request: BuildSemanticIndexRequest) -> BuildSemanticIndexResult:
        """Build and record semantic artifacts for the requested snapshot."""

        provision_runtime_paths(self.runtime_paths)
        self.repository_store.initialize()
        self.snapshot_store.initialize()
        self.chunk_store.initialize()
        self.semantic_index_build_store.initialize()

        snapshot = self.snapshot_store.get_by_snapshot_id(request.snapshot_id)
        if snapshot is None:
            raise SemanticSnapshotNotFoundError(
                f"Snapshot is not registered: {request.snapshot_id}",
            )

        repository = self.repository_store.get_by_repository_id(snapshot.repository_id)
        if repository is None:
            raise BuildSemanticIndexError(
                f"Snapshot points to an unknown repository: {snapshot.repository_id}",
            )

        chunks = self.chunk_store.list_by_snapshot(snapshot.snapshot_id)
        if not chunks:
            raise SemanticChunkBaselineMissingError(
                "Chunk baseline is missing for snapshot; run "
                f"`codeman index build-chunks {snapshot.snapshot_id}` first.",
            )

        source_documents = [self._load_document(chunk) for chunk in _ordered_chunks(chunks)]
        try:
            semantic_config_fingerprint = build_semantic_indexing_fingerprint(
                self.semantic_indexing_config,
                self.embedding_providers_config,
            )
        except ValueError as exc:
            raise InvalidSemanticConfigurationError(
                f"Semantic indexing configuration is invalid: {exc}",
            ) from exc
        embeddings_result = self.embedding_stage.execute(
            repository_id=repository.repository_id,
            snapshot_id=snapshot.snapshot_id,
            semantic_config_fingerprint=semantic_config_fingerprint,
            source_documents=source_documents,
        )
        vector_artifact = self.vector_index_stage.execute(
            repository_id=repository.repository_id,
            snapshot_id=snapshot.snapshot_id,
            semantic_config_fingerprint=semantic_config_fingerprint,
            documents=embeddings_result.documents,
        )

        created_at = datetime.now(UTC)
        build_record = self.semantic_index_build_store.create_build(
            SemanticIndexBuildRecord(
                build_id=uuid4().hex,
                repository_id=repository.repository_id,
                snapshot_id=snapshot.snapshot_id,
                revision_identity=snapshot.revision_identity,
                revision_source=snapshot.revision_source,
                semantic_config_fingerprint=semantic_config_fingerprint,
                provider_id=embeddings_result.provider.provider_id,
                model_id=embeddings_result.provider.model_id,
                model_version=embeddings_result.provider.model_version,
                is_external_provider=embeddings_result.provider.is_external_provider,
                vector_engine=vector_artifact.vector_engine,
                document_count=vector_artifact.document_count,
                embedding_dimension=vector_artifact.embedding_dimension,
                artifact_path=vector_artifact.artifact_path,
                created_at=created_at,
            ),
        )
        provenance_run_id: str | None = None
        if self.record_run_provenance is not None:
            provenance = self.record_run_provenance.execute(
                RecordRunConfigurationProvenanceRequest(
                    workflow_type="index.build-semantic",
                    repository_id=repository.repository_id,
                    snapshot_id=snapshot.snapshot_id,
                    semantic_config_fingerprint=build_record.semantic_config_fingerprint,
                    provider_id=build_record.provider_id,
                    model_id=build_record.model_id,
                    model_version=build_record.model_version,
                    workflow_context=RunProvenanceWorkflowContext(
                        semantic_build_id=build_record.build_id,
                    ),
                )
            )
            provenance_run_id = provenance.run_id
        return BuildSemanticIndexResult(
            run_id=provenance_run_id,
            repository=repository,
            snapshot=snapshot,
            build=build_record,
            provider=embeddings_result.provider,
            diagnostics=SemanticIndexBuildDiagnostics(
                document_count=vector_artifact.document_count,
                embedding_dimension=vector_artifact.embedding_dimension,
                embedding_documents_path=embeddings_result.embedding_documents_path,
                refreshed_existing_artifact=vector_artifact.refreshed_existing_artifact,
            ),
        )

    def _load_document(self, chunk: ChunkRecord) -> SemanticSourceDocument:
        try:
            payload = self.artifact_store.read_chunk_payload(chunk.payload_path)
        except FileNotFoundError as exc:
            raise SemanticChunkPayloadMissingError(
                f"Chunk payload artifact is missing for chunk: {chunk.chunk_id}",
            ) from exc
        except ValidationError as exc:
            raise SemanticChunkPayloadCorruptError(
                f"Chunk payload artifact is corrupt for chunk: {chunk.chunk_id}",
            ) from exc
        except OSError as exc:
            raise SemanticChunkPayloadMissingError(
                f"Chunk payload artifact is missing for chunk: {chunk.chunk_id}",
            ) from exc

        if not _payload_matches_chunk(chunk=chunk, payload=payload):
            raise SemanticChunkPayloadCorruptError(
                f"Chunk payload artifact is corrupt for chunk: {chunk.chunk_id}",
            )

        return SemanticSourceDocument(
            chunk_id=chunk.chunk_id,
            snapshot_id=chunk.snapshot_id,
            repository_id=chunk.repository_id,
            source_file_id=chunk.source_file_id,
            relative_path=chunk.relative_path,
            language=chunk.language,
            strategy=chunk.strategy,
            serialization_version=chunk.serialization_version,
            source_content_hash=chunk.source_content_hash,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            start_byte=chunk.start_byte,
            end_byte=chunk.end_byte,
            content=payload.content,
        )

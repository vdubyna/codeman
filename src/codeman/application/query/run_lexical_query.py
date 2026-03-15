"""Run lexical retrieval queries against the current repository build."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.application.ports.chunk_store_port import ChunkStorePort
from codeman.application.ports.index_build_store_port import IndexBuildStorePort
from codeman.application.ports.lexical_query_port import LexicalQueryPort
from codeman.application.ports.metadata_store_port import RepositoryMetadataStorePort
from codeman.application.ports.snapshot_port import SnapshotMetadataStorePort
from codeman.application.provenance.record_run_provenance import (
    RecordRunConfigurationProvenanceUseCase,
)
from codeman.application.query.format_results import (
    ResolvedLexicalMatch,
    RetrievalResultFormatter,
)
from codeman.config.indexing import IndexingConfig, build_indexing_fingerprint
from codeman.contracts.configuration import (
    RecordRunConfigurationProvenanceRequest,
    RunProvenanceWorkflowContext,
)
from codeman.contracts.errors import ErrorCode
from codeman.contracts.retrieval import (
    LexicalIndexBuildRecord,
    LexicalQueryMatch,
    RunLexicalQueryRequest,
    RunLexicalQueryResult,
)
from codeman.runtime import RuntimePaths, provision_runtime_paths

__all__ = [
    "LexicalArtifactMissingError",
    "LexicalBuildBaselineMissingError",
    "LexicalQueryChunkMetadataMissingError",
    "LexicalQueryChunkPayloadCorruptError",
    "LexicalQueryChunkPayloadMissingError",
    "LexicalQueryError",
    "LexicalQueryRepositoryNotRegisteredError",
    "RunLexicalQueryUseCase",
]


class LexicalQueryError(Exception):
    """Base exception for lexical-query failures."""

    exit_code = 39
    error_code = ErrorCode.LEXICAL_QUERY_FAILED

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LexicalQueryRepositoryNotRegisteredError(LexicalQueryError):
    """Raised when querying an unknown repository."""

    exit_code = 24
    error_code = ErrorCode.REPOSITORY_NOT_REGISTERED


class LexicalArtifactMissingError(LexicalQueryError):
    """Raised when lexical build metadata points to a missing artifact."""

    exit_code = 37
    error_code = ErrorCode.LEXICAL_ARTIFACT_MISSING


class LexicalBuildBaselineMissingError(LexicalQueryError):
    """Raised when a repository has no current lexical build to query."""

    exit_code = 38
    error_code = ErrorCode.LEXICAL_BUILD_BASELINE_MISSING


class LexicalQueryChunkMetadataMissingError(LexicalQueryError):
    """Raised when lexical hits cannot be resolved back to persisted chunk metadata."""

    exit_code = 40
    error_code = ErrorCode.CHUNK_METADATA_MISSING


class LexicalQueryChunkPayloadMissingError(LexicalQueryError):
    """Raised when a persisted chunk payload artifact is missing."""

    exit_code = 41
    error_code = ErrorCode.CHUNK_PAYLOAD_MISSING


class LexicalQueryChunkPayloadCorruptError(LexicalQueryError):
    """Raised when a persisted chunk payload artifact cannot be trusted."""

    exit_code = 42
    error_code = ErrorCode.CHUNK_PAYLOAD_CORRUPT


@dataclass(slots=True)
class RunLexicalQueryUseCase:
    """Resolve the current lexical build for a repository and execute one query."""

    runtime_paths: RuntimePaths
    repository_store: RepositoryMetadataStorePort
    snapshot_store: SnapshotMetadataStorePort
    index_build_store: IndexBuildStorePort
    chunk_store: ChunkStorePort
    artifact_store: ArtifactStorePort
    lexical_query: LexicalQueryPort
    formatter: RetrievalResultFormatter
    indexing_config: IndexingConfig
    record_run_provenance: RecordRunConfigurationProvenanceUseCase | None = None

    def execute(self, request: RunLexicalQueryRequest) -> RunLexicalQueryResult:
        """Run a lexical query against the current repository build."""

        provision_runtime_paths(self.runtime_paths)
        self.repository_store.initialize()
        self.snapshot_store.initialize()
        self.index_build_store.initialize()
        self.chunk_store.initialize()

        repository = self.repository_store.get_by_repository_id(request.repository_id)
        if repository is None:
            raise LexicalQueryRepositoryNotRegisteredError(
                f"Repository is not registered: {request.repository_id}",
            )

        build = self._resolve_build(repository_id=repository.repository_id, request=request)
        if build is None:
            raise LexicalBuildBaselineMissingError(
                "No lexical baseline exists yet for this repository and current configuration; "
                "run `codeman index build-lexical <snapshot-id>` first.",
            )
        if not build.index_path.exists():
            raise LexicalArtifactMissingError(
                f"Lexical artifact is missing for build: {build.build_id}",
            )

        snapshot = self.snapshot_store.get_by_snapshot_id(build.snapshot_id)
        if snapshot is None:
            raise LexicalQueryError(
                f"Lexical build points to an unknown snapshot: {build.snapshot_id}",
            )

        try:
            query_result = self.lexical_query.query(
                build=build,
                query_text=request.query_text,
                max_results=request.max_results,
            )
        except LexicalQueryError:
            raise
        except Exception as exc:
            raise LexicalQueryError(
                f"Lexical query failed for repository: {request.repository_id}",
            ) from exc

        resolved_matches = self._resolve_matches(query_result.matches)
        result = self.formatter.format_lexical_results(
            repository=repository,
            snapshot=snapshot,
            build=build,
            query_text=request.query_text,
            diagnostics=query_result.diagnostics,
            matches=resolved_matches,
        )
        if not request.record_provenance or self.record_run_provenance is None:
            return result

        provenance = self.record_run_provenance.execute(
            RecordRunConfigurationProvenanceRequest(
                workflow_type="query.lexical",
                repository_id=repository.repository_id,
                snapshot_id=snapshot.snapshot_id,
                indexing_config_fingerprint=build.indexing_config_fingerprint,
                workflow_context=RunProvenanceWorkflowContext(
                    lexical_build_id=build.build_id,
                    max_results=request.max_results,
                ),
            )
        )
        return result.model_copy(update={"run_id": provenance.run_id})

    def _resolve_build(
        self,
        *,
        repository_id: str,
        request: RunLexicalQueryRequest,
    ) -> LexicalIndexBuildRecord | None:
        if request.build_id is not None:
            build = self.index_build_store.get_by_build_id(request.build_id)
            if build is None or build.repository_id != repository_id:
                return None
            return build

        return self.index_build_store.get_latest_build_for_repository(
            repository_id,
            build_indexing_fingerprint(self.indexing_config),
        )

    def _resolve_matches(
        self,
        matches: list[LexicalQueryMatch],
    ) -> list[ResolvedLexicalMatch]:
        if not matches:
            return []

        chunk_ids = [match.chunk_id for match in matches]
        chunks = self.chunk_store.get_by_chunk_ids(chunk_ids)
        chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        missing_chunk_ids = [chunk_id for chunk_id in chunk_ids if chunk_id not in chunks_by_id]
        if missing_chunk_ids:
            missing_list = ", ".join(missing_chunk_ids)
            raise LexicalQueryChunkMetadataMissingError(
                f"Chunk metadata is missing for ranked retrieval result(s): {missing_list}",
            )

        resolved_matches: list[ResolvedLexicalMatch] = []
        for match in matches:
            chunk = chunks_by_id[match.chunk_id]
            try:
                payload = self.artifact_store.read_chunk_payload(chunk.payload_path)
            except FileNotFoundError as exc:
                raise LexicalQueryChunkPayloadMissingError(
                    f"Chunk payload artifact is missing for retrieval result: {chunk.chunk_id}",
                ) from exc
            except (ValidationError, ValueError) as exc:
                raise LexicalQueryChunkPayloadCorruptError(
                    f"Chunk payload artifact is invalid for retrieval result: {chunk.chunk_id}",
                ) from exc

            if payload.chunk_id != chunk.chunk_id or payload.snapshot_id != chunk.snapshot_id:
                raise LexicalQueryChunkPayloadCorruptError(
                    f"Chunk payload artifact does not match retrieval metadata: {chunk.chunk_id}",
                )

            resolved_matches.append(
                ResolvedLexicalMatch(
                    match=match,
                    chunk=chunk,
                    payload=payload,
                )
            )

        return resolved_matches

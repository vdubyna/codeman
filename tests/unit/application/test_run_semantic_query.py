from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codeman.application.ports.semantic_query_port import SemanticVectorArtifactCorruptError
from codeman.application.query.format_results import RetrievalResultFormatter
from codeman.application.query.run_semantic_query import (
    RunSemanticQueryUseCase,
    SemanticArtifactCorruptError,
    SemanticArtifactMissingError,
    SemanticBuildBaselineMissingError,
    SemanticQueryChunkMetadataMissingError,
    SemanticQueryChunkPayloadMissingError,
    SemanticQueryProviderUnavailableError,
    SemanticQueryRepositoryNotRegisteredError,
)
from codeman.config.embedding_providers import EmbeddingProviderConfig, EmbeddingProvidersConfig
from codeman.config.semantic_indexing import (
    SemanticIndexingConfig,
    build_semantic_indexing_fingerprint,
)
from codeman.contracts.chunking import ChunkPayloadDocument, ChunkRecord
from codeman.contracts.repository import RepositoryRecord, SnapshotRecord
from codeman.contracts.retrieval import (
    EmbeddingProviderDescriptor,
    RunSemanticQueryRequest,
    SemanticIndexBuildRecord,
    SemanticQueryDiagnostics,
    SemanticQueryEmbedding,
    SemanticQueryMatch,
    SemanticQueryResult,
)
from codeman.runtime import build_runtime_paths


@dataclass
class FakeRepositoryStore:
    repository: RepositoryRecord | None
    initialized: int = 0

    def initialize(self) -> None:
        self.initialized += 1

    def get_by_repository_id(self, repository_id: str) -> RepositoryRecord | None:
        if self.repository is None or self.repository.repository_id != repository_id:
            return None
        return self.repository


@dataclass
class FakeSnapshotStore:
    snapshot: SnapshotRecord | None
    initialized: int = 0

    def initialize(self) -> None:
        self.initialized += 1

    def get_by_snapshot_id(self, snapshot_id: str) -> SnapshotRecord | None:
        if self.snapshot is None or self.snapshot.snapshot_id != snapshot_id:
            return None
        return self.snapshot


@dataclass
class FakeSemanticIndexBuildStore:
    build: SemanticIndexBuildRecord | None
    initialized: int = 0
    seen_repository_queries: list[tuple[str, str]] = field(default_factory=list)

    def initialize(self) -> None:
        self.initialized += 1

    def create_build(self, build: SemanticIndexBuildRecord) -> SemanticIndexBuildRecord:
        self.build = build
        return build

    def get_latest_build_for_snapshot(
        self,
        snapshot_id: str,
        semantic_config_fingerprint: str,
    ) -> SemanticIndexBuildRecord | None:
        if (
            self.build is None
            or self.build.snapshot_id != snapshot_id
            or self.build.semantic_config_fingerprint != semantic_config_fingerprint
        ):
            return None
        return self.build

    def get_latest_build_for_repository(
        self,
        repository_id: str,
        semantic_config_fingerprint: str,
    ) -> SemanticIndexBuildRecord | None:
        self.seen_repository_queries.append((repository_id, semantic_config_fingerprint))
        if (
            self.build is None
            or self.build.repository_id != repository_id
            or self.build.semantic_config_fingerprint != semantic_config_fingerprint
        ):
            return None
        return self.build


@dataclass
class FakeChunkStore:
    chunks: list[ChunkRecord]
    initialized: int = 0

    def initialize(self) -> None:
        self.initialized += 1

    def list_by_snapshot(self, snapshot_id: str) -> list[ChunkRecord]:
        return [chunk for chunk in self.chunks if chunk.snapshot_id == snapshot_id]

    def get_by_chunk_ids(self, chunk_ids: list[str]) -> list[ChunkRecord]:
        chunks_by_id = {chunk.chunk_id: chunk for chunk in self.chunks}
        return [chunks_by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in chunks_by_id]


@dataclass
class FakeArtifactStore:
    payloads: dict[Path, ChunkPayloadDocument]

    def read_chunk_payload(self, payload_path: Path) -> ChunkPayloadDocument:
        if payload_path not in self.payloads:
            raise FileNotFoundError(payload_path)
        return self.payloads[payload_path]


@dataclass
class FakeEmbeddingProvider:
    result: SemanticQueryEmbedding | None = None
    error: Exception | None = None
    seen_queries: list[tuple[str, int, str]] = field(default_factory=list)

    def embed(self, **_: object) -> list[object]:
        raise AssertionError("Document embedding path should not be used in semantic query tests.")

    def embed_query(
        self,
        *,
        provider: EmbeddingProviderDescriptor,
        query_text: str,
        vector_dimension: int,
    ) -> SemanticQueryEmbedding:
        self.seen_queries.append((provider.provider_id, vector_dimension, query_text))
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


@dataclass
class FakeSemanticQueryEngine:
    result: SemanticQueryResult | None = None
    error: Exception | None = None
    seen_requests: list[tuple[str, list[float], int]] = field(default_factory=list)

    def query(
        self,
        *,
        build: SemanticIndexBuildRecord,
        query_embedding: SemanticQueryEmbedding,
        max_results: int = 20,
    ) -> SemanticQueryResult:
        self.seen_requests.append((build.build_id, query_embedding.embedding, max_results))
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def build_repository_record(repository_path: Path) -> RepositoryRecord:
    now = datetime.now(UTC)
    return RepositoryRecord(
        repository_id="repo-123",
        repository_name=repository_path.name,
        canonical_path=repository_path,
        requested_path=repository_path,
        created_at=now,
        updated_at=now,
    )


def build_snapshot_record(repository_id: str, workspace: Path) -> SnapshotRecord:
    now = datetime.now(UTC)
    return SnapshotRecord(
        snapshot_id="snapshot-123",
        repository_id=repository_id,
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        manifest_path=workspace / ".codeman" / "artifacts" / "manifest.json",
        created_at=now,
        source_inventory_extracted_at=now,
        chunk_generation_completed_at=now,
        indexing_config_fingerprint="fingerprint-123",
    )


def build_semantic_config(local_model_path: Path) -> SemanticIndexingConfig:
    return SemanticIndexingConfig(
        provider_id="local-hash",
        vector_engine="sqlite-exact",
        vector_dimension=4,
    )


def build_embedding_providers_config(local_model_path: Path) -> EmbeddingProvidersConfig:
    return EmbeddingProvidersConfig(
        local_hash=EmbeddingProviderConfig(
            model_id="fixture-local",
            model_version="2026-03-14",
            local_model_path=local_model_path,
        ),
    )


def build_semantic_build_record(
    *,
    workspace: Path,
    repository_id: str,
    semantic_config_fingerprint: str,
) -> SemanticIndexBuildRecord:
    artifact_path = workspace / ".codeman" / "indexes" / "semantic.sqlite3"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.touch()
    return SemanticIndexBuildRecord(
        build_id="semantic-build-123",
        repository_id=repository_id,
        snapshot_id="snapshot-123",
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        semantic_config_fingerprint=semantic_config_fingerprint,
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="2026-03-14",
        vector_engine="sqlite-exact",
        document_count=3,
        embedding_dimension=4,
        artifact_path=artifact_path,
        created_at=datetime.now(UTC),
    )


def build_query_result() -> SemanticQueryResult:
    return SemanticQueryResult(
        matches=[
            SemanticQueryMatch(chunk_id="chunk-1", score=0.875, rank=1),
            SemanticQueryMatch(chunk_id="chunk-2", score=0.5, rank=2),
        ],
        diagnostics=SemanticQueryDiagnostics(
            match_count=2,
            query_latency_ms=7,
            total_match_count=3,
            truncated=True,
        ),
    )


def build_chunk_records(workspace: Path) -> list[ChunkRecord]:
    now = datetime.now(UTC)
    return [
        ChunkRecord(
            chunk_id="chunk-1",
            snapshot_id="snapshot-123",
            repository_id="repo-123",
            source_file_id="source-1",
            relative_path="assets/app.js",
            language="javascript",
            strategy="javascript_structure",
            serialization_version="1",
            source_content_hash="hash-1",
            start_line=1,
            end_line=3,
            start_byte=0,
            end_byte=48,
            payload_path=workspace / ".codeman" / "artifacts" / "chunk-1.json",
            created_at=now,
        ),
        ChunkRecord(
            chunk_id="chunk-2",
            snapshot_id="snapshot-123",
            repository_id="repo-123",
            source_file_id="source-2",
            relative_path="src/Controller/HomeController.php",
            language="php",
            strategy="php_structure",
            serialization_version="1",
            source_content_hash="hash-2",
            start_line=4,
            end_line=10,
            start_byte=32,
            end_byte=180,
            payload_path=workspace / ".codeman" / "artifacts" / "chunk-2.json",
            created_at=now,
        ),
    ]


def build_payloads(chunks: list[ChunkRecord]) -> dict[Path, ChunkPayloadDocument]:
    return {
        chunk.payload_path: ChunkPayloadDocument(
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
            content=(
                "export function bootValue() { return 'codeman'; }"
                if chunk.chunk_id == "chunk-1"
                else (
                    "final class HomeController { public function __invoke(): "
                    "string { return 'home'; } }"
                )
            ),
        )
        for chunk in chunks
    }


def build_use_case(
    *,
    workspace: Path,
    repository: RepositoryRecord | None,
    snapshot: SnapshotRecord | None,
    build_store: FakeSemanticIndexBuildStore,
    chunks: list[ChunkRecord],
    payloads: dict[Path, ChunkPayloadDocument],
    semantic_config: SemanticIndexingConfig,
    embedding_providers_config: EmbeddingProvidersConfig | None = None,
    embedding_provider: FakeEmbeddingProvider | None = None,
    query_engine: FakeSemanticQueryEngine | None = None,
) -> RunSemanticQueryUseCase:
    runtime_paths = build_runtime_paths(workspace)
    return RunSemanticQueryUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        semantic_index_build_store=build_store,
        chunk_store=FakeChunkStore(chunks=chunks),
        artifact_store=FakeArtifactStore(payloads=payloads),
        embedding_provider=embedding_provider
        or FakeEmbeddingProvider(
            result=SemanticQueryEmbedding(
                provider_id="local-hash",
                model_id="fixture-local",
                model_version="2026-03-14",
                vector_dimension=4,
                embedding=[1.0, 0.0, 0.0, 0.0],
            )
        ),
        semantic_query=query_engine or FakeSemanticQueryEngine(result=build_query_result()),
        formatter=RetrievalResultFormatter(preview_char_limit=80),
        semantic_indexing_config=semantic_config,
        embedding_providers_config=embedding_providers_config or EmbeddingProvidersConfig(),
    )


def test_run_semantic_query_returns_ranked_matches_with_repository_context(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    semantic_config = build_semantic_config(local_model_path)
    embedding_providers_config = build_embedding_providers_config(local_model_path)
    fingerprint = build_semantic_indexing_fingerprint(
        semantic_config,
        embedding_providers_config,
    )
    build_store = FakeSemanticIndexBuildStore(
        build=build_semantic_build_record(
            workspace=workspace,
            repository_id=repository.repository_id,
            semantic_config_fingerprint=fingerprint,
        )
    )
    chunks = build_chunk_records(workspace)
    use_case = build_use_case(
        workspace=workspace,
        repository=repository,
        snapshot=snapshot,
        build_store=build_store,
        chunks=chunks,
        payloads=build_payloads(chunks),
        semantic_config=semantic_config,
        embedding_providers_config=embedding_providers_config,
    )

    result = use_case.execute(
        RunSemanticQueryRequest(
            repository_id=repository.repository_id,
            query_text="controller home route",
        ),
    )

    assert result.repository.repository_id == repository.repository_id
    assert result.snapshot.snapshot_id == snapshot.snapshot_id
    assert result.retrieval_mode == "semantic"
    assert result.build.build_id == "semantic-build-123"
    assert result.build.provider_id == "local-hash"
    assert result.build.model_version == "2026-03-14"
    assert result.results[0].chunk_id == "chunk-1"
    assert result.results[0].content_preview == "export function bootValue() { return 'codeman'; }"
    assert result.results[0].explanation == (
        "Ranked by embedding similarity against the persisted semantic index."
    )
    assert build_store.seen_repository_queries == [(repository.repository_id, fingerprint)]
    assert use_case.embedding_provider.seen_queries == [("local-hash", 4, "controller home route")]
    assert use_case.semantic_query.seen_requests == [
        ("semantic-build-123", [1.0, 0.0, 0.0, 0.0], 20)
    ]


def test_run_semantic_query_raises_when_repository_is_unknown(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    semantic_config = build_semantic_config(local_model_path)
    use_case = build_use_case(
        workspace=workspace,
        repository=None,
        snapshot=None,
        build_store=FakeSemanticIndexBuildStore(build=None),
        chunks=[],
        payloads={},
        semantic_config=semantic_config,
        embedding_providers_config=build_embedding_providers_config(local_model_path),
    )

    with pytest.raises(SemanticQueryRepositoryNotRegisteredError):
        use_case.execute(
            RunSemanticQueryRequest(
                repository_id="missing-repo",
                query_text="controller home route",
            ),
        )


def test_run_semantic_query_raises_when_current_semantic_build_is_missing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    semantic_config = build_semantic_config(local_model_path)
    use_case = build_use_case(
        workspace=workspace,
        repository=repository,
        snapshot=None,
        build_store=FakeSemanticIndexBuildStore(build=None),
        chunks=[],
        payloads={},
        semantic_config=semantic_config,
        embedding_providers_config=build_embedding_providers_config(local_model_path),
    )

    with pytest.raises(SemanticBuildBaselineMissingError):
        use_case.execute(
            RunSemanticQueryRequest(
                repository_id=repository.repository_id,
                query_text="controller home route",
            ),
        )


def test_run_semantic_query_raises_when_semantic_artifact_is_missing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    semantic_config = build_semantic_config(local_model_path)
    embedding_providers_config = build_embedding_providers_config(local_model_path)
    fingerprint = build_semantic_indexing_fingerprint(
        semantic_config,
        embedding_providers_config,
    )
    missing_build = build_semantic_build_record(
        workspace=workspace,
        repository_id=repository.repository_id,
        semantic_config_fingerprint=fingerprint,
    ).model_copy(update={"artifact_path": workspace / ".codeman" / "indexes" / "missing.sqlite3"})
    use_case = build_use_case(
        workspace=workspace,
        repository=repository,
        snapshot=snapshot,
        build_store=FakeSemanticIndexBuildStore(build=missing_build),
        chunks=build_chunk_records(workspace),
        payloads={},
        semantic_config=semantic_config,
        embedding_providers_config=embedding_providers_config,
    )

    with pytest.raises(SemanticArtifactMissingError):
        use_case.execute(
            RunSemanticQueryRequest(
                repository_id=repository.repository_id,
                query_text="controller home route",
            ),
        )


def test_run_semantic_query_raises_when_ranked_chunk_metadata_is_missing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    semantic_config = build_semantic_config(local_model_path)
    embedding_providers_config = build_embedding_providers_config(local_model_path)
    fingerprint = build_semantic_indexing_fingerprint(
        semantic_config,
        embedding_providers_config,
    )
    build_store = FakeSemanticIndexBuildStore(
        build=build_semantic_build_record(
            workspace=workspace,
            repository_id=repository.repository_id,
            semantic_config_fingerprint=fingerprint,
        )
    )
    chunks = build_chunk_records(workspace)[:1]
    use_case = build_use_case(
        workspace=workspace,
        repository=repository,
        snapshot=snapshot,
        build_store=build_store,
        chunks=chunks,
        payloads=build_payloads(chunks),
        semantic_config=semantic_config,
        embedding_providers_config=embedding_providers_config,
    )

    with pytest.raises(SemanticQueryChunkMetadataMissingError):
        use_case.execute(
            RunSemanticQueryRequest(
                repository_id=repository.repository_id,
                query_text="controller home route",
            ),
        )


def test_run_semantic_query_raises_when_chunk_payload_is_missing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    semantic_config = build_semantic_config(local_model_path)
    embedding_providers_config = build_embedding_providers_config(local_model_path)
    fingerprint = build_semantic_indexing_fingerprint(
        semantic_config,
        embedding_providers_config,
    )
    build_store = FakeSemanticIndexBuildStore(
        build=build_semantic_build_record(
            workspace=workspace,
            repository_id=repository.repository_id,
            semantic_config_fingerprint=fingerprint,
        )
    )
    chunks = build_chunk_records(workspace)
    payloads = build_payloads(chunks)
    payloads.pop(chunks[1].payload_path)
    use_case = build_use_case(
        workspace=workspace,
        repository=repository,
        snapshot=snapshot,
        build_store=build_store,
        chunks=chunks,
        payloads=payloads,
        semantic_config=semantic_config,
        embedding_providers_config=embedding_providers_config,
    )

    with pytest.raises(SemanticQueryChunkPayloadMissingError):
        use_case.execute(
            RunSemanticQueryRequest(
                repository_id=repository.repository_id,
                query_text="controller home route",
            ),
        )


def test_run_semantic_query_raises_when_local_provider_is_unavailable(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    semantic_config = SemanticIndexingConfig(
        provider_id="local-hash",
        vector_engine="sqlite-exact",
        vector_dimension=4,
    )
    embedding_providers_config = EmbeddingProvidersConfig(
        local_hash=EmbeddingProviderConfig(
            model_id="fixture-local",
            model_version="2026-03-14",
            local_model_path=tmp_path / "missing-local-model",
        ),
    )
    fingerprint = build_semantic_indexing_fingerprint(
        semantic_config,
        embedding_providers_config,
    )
    use_case = build_use_case(
        workspace=workspace,
        repository=repository,
        snapshot=snapshot,
        build_store=FakeSemanticIndexBuildStore(
            build=build_semantic_build_record(
                workspace=workspace,
                repository_id=repository.repository_id,
                semantic_config_fingerprint=fingerprint,
            )
        ),
        chunks=[],
        payloads={},
        semantic_config=semantic_config,
        embedding_providers_config=embedding_providers_config,
    )

    with pytest.raises(SemanticQueryProviderUnavailableError):
        use_case.execute(
            RunSemanticQueryRequest(
                repository_id=repository.repository_id,
                query_text="controller home route",
            ),
        )


def test_run_semantic_query_raises_when_query_embedding_lineage_does_not_match_build(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    semantic_config = build_semantic_config(local_model_path)
    embedding_providers_config = build_embedding_providers_config(local_model_path)
    fingerprint = build_semantic_indexing_fingerprint(
        semantic_config,
        embedding_providers_config,
    )
    build_store = FakeSemanticIndexBuildStore(
        build=build_semantic_build_record(
            workspace=workspace,
            repository_id=repository.repository_id,
            semantic_config_fingerprint=fingerprint,
        )
    )
    chunks = build_chunk_records(workspace)
    use_case = build_use_case(
        workspace=workspace,
        repository=repository,
        snapshot=snapshot,
        build_store=build_store,
        chunks=chunks,
        payloads=build_payloads(chunks),
        semantic_config=semantic_config,
        embedding_providers_config=embedding_providers_config,
        embedding_provider=FakeEmbeddingProvider(
            result=SemanticQueryEmbedding(
                provider_id="local-hash",
                model_id="fixture-local",
                model_version="999",
                vector_dimension=4,
                embedding=[1.0, 0.0, 0.0, 0.0],
            )
        ),
    )

    with pytest.raises(
        SemanticQueryProviderUnavailableError,
        match="does not match the current semantic build",
    ):
        use_case.execute(
            RunSemanticQueryRequest(
                repository_id=repository.repository_id,
                query_text="controller home route",
            ),
        )


def test_run_semantic_query_maps_corrupt_vector_artifact_to_stable_error(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    semantic_config = build_semantic_config(local_model_path)
    embedding_providers_config = build_embedding_providers_config(local_model_path)
    fingerprint = build_semantic_indexing_fingerprint(
        semantic_config,
        embedding_providers_config,
    )
    build_store = FakeSemanticIndexBuildStore(
        build=build_semantic_build_record(
            workspace=workspace,
            repository_id=repository.repository_id,
            semantic_config_fingerprint=fingerprint,
        )
    )
    chunks = build_chunk_records(workspace)
    use_case = build_use_case(
        workspace=workspace,
        repository=repository,
        snapshot=snapshot,
        build_store=build_store,
        chunks=chunks,
        payloads=build_payloads(chunks),
        semantic_config=semantic_config,
        embedding_providers_config=embedding_providers_config,
        query_engine=FakeSemanticQueryEngine(
            error=SemanticVectorArtifactCorruptError("row count does not match recorded metadata"),
        ),
    )

    with pytest.raises(
        SemanticArtifactCorruptError,
        match="Semantic artifact is invalid for build",
    ):
        use_case.execute(
            RunSemanticQueryRequest(
                repository_id=repository.repository_id,
                query_text="controller home route",
            ),
        )

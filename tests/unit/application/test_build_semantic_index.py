from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codeman.application.indexing.build_embeddings import BuildEmbeddingsStage
from codeman.application.indexing.build_semantic_index import BuildSemanticIndexUseCase
from codeman.application.indexing.build_vector_index import BuildVectorIndexStage
from codeman.application.indexing.semantic_index_errors import (
    EmbeddingProviderUnavailableError,
    SemanticChunkPayloadMissingError,
    SemanticSnapshotNotFoundError,
    VectorIndexBuildError,
)
from codeman.config.embedding_providers import EmbeddingProviderConfig, EmbeddingProvidersConfig
from codeman.config.semantic_indexing import (
    SemanticIndexingConfig,
    build_semantic_indexing_fingerprint,
)
from codeman.contracts.chunking import ChunkPayloadDocument, ChunkRecord
from codeman.contracts.repository import RepositoryRecord, SnapshotRecord
from codeman.contracts.retrieval import (
    BuildSemanticIndexRequest,
    SemanticEmbeddingDocument,
    SemanticIndexArtifact,
    SemanticIndexBuildRecord,
)
from codeman.infrastructure.artifacts.filesystem_artifact_store import (
    FilesystemArtifactStore,
)
from codeman.infrastructure.cache.filesystem_cache_store import FilesystemCacheStore
from codeman.infrastructure.embeddings.local_hash_provider import (
    DeterministicLocalHashEmbeddingProvider,
)
from codeman.infrastructure.indexes.vector.sqlite_exact_builder import (
    SqliteExactVectorIndexBuilder,
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
class FakeChunkStore:
    chunks: list[ChunkRecord]
    initialized: int = 0

    def initialize(self) -> None:
        self.initialized += 1

    def list_by_snapshot(self, snapshot_id: str) -> list[ChunkRecord]:
        return [chunk for chunk in self.chunks if chunk.snapshot_id == snapshot_id]


@dataclass
class FakeSemanticIndexBuildStore:
    initialized: int = 0
    created_builds: list[SemanticIndexBuildRecord] = field(default_factory=list)

    def initialize(self) -> None:
        self.initialized += 1

    def create_build(self, build: SemanticIndexBuildRecord) -> SemanticIndexBuildRecord:
        self.created_builds.append(build)
        return build

    def get_latest_build_for_snapshot(
        self,
        snapshot_id: str,
        semantic_config_fingerprint: str,
    ) -> SemanticIndexBuildRecord | None:
        for build in reversed(self.created_builds):
            if (
                build.snapshot_id == snapshot_id
                and build.semantic_config_fingerprint == semantic_config_fingerprint
            ):
                return build
        return None

    def get_latest_build_for_repository(
        self,
        repository_id: str,
        semantic_config_fingerprint: str,
    ) -> SemanticIndexBuildRecord | None:
        for build in reversed(self.created_builds):
            if (
                build.repository_id == repository_id
                and build.semantic_config_fingerprint == semantic_config_fingerprint
            ):
                return build
        return None


@dataclass
class BrokenVectorIndexBuilder:
    def build(
        self,
        *,
        repository_id: str,
        snapshot_id: str,
        semantic_config_fingerprint: str,
        documents: list[SemanticEmbeddingDocument],
    ) -> SemanticIndexArtifact:
        raise RuntimeError("boom")


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
    return SnapshotRecord(
        snapshot_id="snapshot-123",
        repository_id=repository_id,
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        manifest_path=(
            workspace / ".codeman" / "artifacts" / "snapshots" / "snapshot-123" / "manifest.json"
        ),
        created_at=datetime.now(UTC),
        source_inventory_extracted_at=datetime.now(UTC),
        chunk_generation_completed_at=datetime.now(UTC),
        indexing_config_fingerprint="indexing-fingerprint-123",
    )


def build_chunk_record(
    *,
    snapshot_id: str,
    repository_id: str,
    source_file_id: str,
    relative_path: str,
    language: str,
    strategy: str,
    payload_path: Path,
    start_line: int,
    start_byte: int,
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=f"{source_file_id}:{strategy}:{start_line}",
        snapshot_id=snapshot_id,
        repository_id=repository_id,
        source_file_id=source_file_id,
        relative_path=relative_path,
        language=language,
        strategy=strategy,
        source_content_hash=f"hash-{source_file_id}",
        start_line=start_line,
        end_line=start_line + 2,
        start_byte=start_byte,
        end_byte=start_byte + 42,
        payload_path=payload_path,
        created_at=datetime.now(UTC),
    )


def build_semantic_config(local_model_path: Path) -> SemanticIndexingConfig:
    return SemanticIndexingConfig(
        provider_id="local-hash",
        vector_engine="sqlite-exact",
        vector_dimension=8,
    )


def build_embedding_providers_config(local_model_path: Path) -> EmbeddingProvidersConfig:
    return EmbeddingProvidersConfig(
        local_hash=EmbeddingProviderConfig(
            model_id="fixture-local",
            model_version="2026-03-14",
            local_model_path=local_model_path,
        ),
    )


def build_use_case(
    *,
    workspace: Path,
    repository: RepositoryRecord | None,
    snapshot: SnapshotRecord | None,
    chunks: list[ChunkRecord],
    semantic_config: SemanticIndexingConfig,
    embedding_providers_config: EmbeddingProvidersConfig | None,
    artifact_store: FilesystemArtifactStore,
    semantic_build_store: FakeSemanticIndexBuildStore,
    vector_builder: object | None = None,
) -> BuildSemanticIndexUseCase:
    runtime_paths = build_runtime_paths(workspace)
    return BuildSemanticIndexUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        chunk_store=FakeChunkStore(chunks=chunks),
        artifact_store=artifact_store,
        embedding_stage=BuildEmbeddingsStage(
            artifact_store=artifact_store,
            cache_store=FilesystemCacheStore(runtime_paths.cache),
            embedding_provider=DeterministicLocalHashEmbeddingProvider(),
            semantic_indexing_config=semantic_config,
            embedding_providers_config=embedding_providers_config or EmbeddingProvidersConfig(),
        ),
        vector_index_stage=BuildVectorIndexStage(
            vector_index=vector_builder
            or SqliteExactVectorIndexBuilder(runtime_paths=runtime_paths),
            semantic_indexing_config=semantic_config,
        ),
        semantic_index_build_store=semantic_build_store,
        semantic_indexing_config=semantic_config,
        embedding_providers_config=embedding_providers_config or EmbeddingProvidersConfig(),
    )


def test_build_semantic_index_reads_payloads_in_deterministic_order_and_records_metadata(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)

    second_payload_path = artifact_store.write_chunk_payload(
        ChunkPayloadDocument(
            chunk_id="source-b:php_structure:10",
            snapshot_id=snapshot.snapshot_id,
            repository_id=repository.repository_id,
            source_file_id="source-b",
            relative_path="src/Controller/HomeController.php",
            language="php",
            strategy="php_structure",
            source_content_hash="hash-source-b",
            start_line=10,
            end_line=12,
            start_byte=100,
            end_byte=142,
            content=(
                "final class HomeController { public function __invoke(): string "
                "{ return 'home'; } }"
            ),
        ),
        snapshot_id=snapshot.snapshot_id,
    )
    first_payload_path = artifact_store.write_chunk_payload(
        ChunkPayloadDocument(
            chunk_id="source-a:javascript_structure:1",
            snapshot_id=snapshot.snapshot_id,
            repository_id=repository.repository_id,
            source_file_id="source-a",
            relative_path="assets/app.js",
            language="javascript",
            strategy="javascript_structure",
            source_content_hash="hash-source-a",
            start_line=1,
            end_line=3,
            start_byte=0,
            end_byte=42,
            content='export function boot() { return "codeman"; }',
        ),
        snapshot_id=snapshot.snapshot_id,
    )

    use_case = build_use_case(
        workspace=workspace,
        repository=repository,
        snapshot=snapshot,
        chunks=[
            build_chunk_record(
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                source_file_id="source-b",
                relative_path="src/Controller/HomeController.php",
                language="php",
                strategy="php_structure",
                payload_path=second_payload_path,
                start_line=10,
                start_byte=100,
            ),
            build_chunk_record(
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                source_file_id="source-a",
                relative_path="assets/app.js",
                language="javascript",
                strategy="javascript_structure",
                payload_path=first_payload_path,
                start_line=1,
                start_byte=0,
            ),
        ],
        semantic_config=build_semantic_config(local_model_path),
        embedding_providers_config=build_embedding_providers_config(local_model_path),
        artifact_store=artifact_store,
        semantic_build_store=FakeSemanticIndexBuildStore(),
    )

    result = use_case.execute(BuildSemanticIndexRequest(snapshot_id=snapshot.snapshot_id))
    embedding_artifact = artifact_store.read_embedding_documents(
        result.diagnostics.embedding_documents_path,
    )

    assert [document.chunk_id for document in embedding_artifact.documents] == [
        "source-a:javascript_structure:1",
        "source-b:php_structure:10",
    ]
    assert embedding_artifact.documents[0].content == 'export function boot() { return "codeman"; }'
    assert result.provider.provider_id == "local-hash"
    assert result.build.vector_engine == "sqlite-exact"
    assert result.build.semantic_config_fingerprint == build_semantic_indexing_fingerprint(
        build_semantic_config(local_model_path),
        build_embedding_providers_config(local_model_path),
    )
    assert result.diagnostics.document_count == 2
    assert result.diagnostics.cache_summary.embedding_documents_regenerated == 2
    with sqlite3.connect(result.build.artifact_path) as connection:
        stored_count = connection.execute(
            "SELECT COUNT(*) FROM semantic_vectors",
        ).fetchone()[0]

    assert stored_count == 2


def test_build_semantic_index_requires_registered_snapshot(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    use_case = build_use_case(
        workspace=workspace,
        repository=None,
        snapshot=None,
        chunks=[],
        semantic_config=build_semantic_config(local_model_path),
        embedding_providers_config=build_embedding_providers_config(local_model_path),
        artifact_store=artifact_store,
        semantic_build_store=FakeSemanticIndexBuildStore(),
    )

    with pytest.raises(SemanticSnapshotNotFoundError):
        use_case.execute(BuildSemanticIndexRequest(snapshot_id="missing"))


def test_build_semantic_index_reuses_embedding_cache_on_second_run(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    payload_path = artifact_store.write_chunk_payload(
        ChunkPayloadDocument(
            chunk_id="source-a:javascript_structure:1",
            snapshot_id=snapshot.snapshot_id,
            repository_id=repository.repository_id,
            source_file_id="source-a",
            relative_path="assets/app.js",
            language="javascript",
            strategy="javascript_structure",
            source_content_hash="hash-source-a",
            start_line=1,
            end_line=3,
            start_byte=0,
            end_byte=42,
            content='export function boot() { return "codeman"; }',
        ),
        snapshot_id=snapshot.snapshot_id,
    )
    use_case = build_use_case(
        workspace=workspace,
        repository=repository,
        snapshot=snapshot,
        chunks=[
            build_chunk_record(
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                source_file_id="source-a",
                relative_path="assets/app.js",
                language="javascript",
                strategy="javascript_structure",
                payload_path=payload_path,
                start_line=1,
                start_byte=0,
            ),
        ],
        semantic_config=build_semantic_config(local_model_path),
        embedding_providers_config=build_embedding_providers_config(local_model_path),
        artifact_store=artifact_store,
        semantic_build_store=FakeSemanticIndexBuildStore(),
    )

    first = use_case.execute(BuildSemanticIndexRequest(snapshot_id=snapshot.snapshot_id))
    second = use_case.execute(BuildSemanticIndexRequest(snapshot_id=snapshot.snapshot_id))

    assert first.diagnostics.cache_summary.embedding_documents_regenerated == 1
    assert second.diagnostics.cache_summary.embedding_documents_reused == 1


def test_build_semantic_index_rebuilds_when_embedding_cache_is_corrupt(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    payload_path = artifact_store.write_chunk_payload(
        ChunkPayloadDocument(
            chunk_id="source-a:javascript_structure:1",
            snapshot_id=snapshot.snapshot_id,
            repository_id=repository.repository_id,
            source_file_id="source-a",
            relative_path="assets/app.js",
            language="javascript",
            strategy="javascript_structure",
            source_content_hash="hash-source-a",
            start_line=1,
            end_line=3,
            start_byte=0,
            end_byte=42,
            content='export function boot() { return "codeman"; }',
        ),
        snapshot_id=snapshot.snapshot_id,
    )
    use_case = build_use_case(
        workspace=workspace,
        repository=repository,
        snapshot=snapshot,
        chunks=[
            build_chunk_record(
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                source_file_id="source-a",
                relative_path="assets/app.js",
                language="javascript",
                strategy="javascript_structure",
                payload_path=payload_path,
                start_line=1,
                start_byte=0,
            ),
        ],
        semantic_config=build_semantic_config(local_model_path),
        embedding_providers_config=build_embedding_providers_config(local_model_path),
        artifact_store=artifact_store,
        semantic_build_store=FakeSemanticIndexBuildStore(),
    )

    use_case.execute(BuildSemanticIndexRequest(snapshot_id=snapshot.snapshot_id))
    cache_files = list((workspace / ".codeman" / "cache" / "embedding").glob("*.json"))
    assert cache_files
    cache_files[0].write_text("{invalid", encoding="utf-8")

    result = use_case.execute(BuildSemanticIndexRequest(snapshot_id=snapshot.snapshot_id))

    assert result.diagnostics.cache_summary.embedding_documents_reused == 0
    assert result.diagnostics.cache_summary.embedding_documents_regenerated == 1


def test_build_semantic_index_rebuilds_when_embedding_cache_vector_is_truncated(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    payload_path = artifact_store.write_chunk_payload(
        ChunkPayloadDocument(
            chunk_id="source-a:javascript_structure:1",
            snapshot_id=snapshot.snapshot_id,
            repository_id=repository.repository_id,
            source_file_id="source-a",
            relative_path="assets/app.js",
            language="javascript",
            strategy="javascript_structure",
            source_content_hash="hash-source-a",
            start_line=1,
            end_line=3,
            start_byte=0,
            end_byte=42,
            content='export function boot() { return "codeman"; }',
        ),
        snapshot_id=snapshot.snapshot_id,
    )
    use_case = build_use_case(
        workspace=workspace,
        repository=repository,
        snapshot=snapshot,
        chunks=[
            build_chunk_record(
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                source_file_id="source-a",
                relative_path="assets/app.js",
                language="javascript",
                strategy="javascript_structure",
                payload_path=payload_path,
                start_line=1,
                start_byte=0,
            ),
        ],
        semantic_config=build_semantic_config(local_model_path),
        embedding_providers_config=build_embedding_providers_config(local_model_path),
        artifact_store=artifact_store,
        semantic_build_store=FakeSemanticIndexBuildStore(),
    )

    use_case.execute(BuildSemanticIndexRequest(snapshot_id=snapshot.snapshot_id))
    cache_files = list((workspace / ".codeman" / "cache" / "embedding").glob("*.json"))
    assert cache_files
    payload = json.loads(cache_files[0].read_text(encoding="utf-8"))
    payload["documents"][0]["embedding"] = payload["documents"][0]["embedding"][:-1]
    cache_files[0].write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = use_case.execute(BuildSemanticIndexRequest(snapshot_id=snapshot.snapshot_id))

    assert result.diagnostics.cache_summary.embedding_documents_reused == 0
    assert result.diagnostics.cache_summary.embedding_documents_regenerated == 1


def test_build_semantic_index_requires_explicit_local_provider_configuration(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    payload_path = artifact_store.write_chunk_payload(
        ChunkPayloadDocument(
            chunk_id="source-a:javascript_structure:1",
            snapshot_id=snapshot.snapshot_id,
            repository_id=repository.repository_id,
            source_file_id="source-a",
            relative_path="assets/app.js",
            language="javascript",
            strategy="javascript_structure",
            source_content_hash="hash-source-a",
            start_line=1,
            end_line=3,
            start_byte=0,
            end_byte=42,
            content='export function boot() { return "codeman"; }',
        ),
        snapshot_id=snapshot.snapshot_id,
    )
    use_case = build_use_case(
        workspace=workspace,
        repository=repository,
        snapshot=snapshot,
        chunks=[
            build_chunk_record(
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                source_file_id="source-a",
                relative_path="assets/app.js",
                language="javascript",
                strategy="javascript_structure",
                payload_path=payload_path,
                start_line=1,
                start_byte=0,
            )
        ],
        semantic_config=SemanticIndexingConfig(),
        embedding_providers_config=EmbeddingProvidersConfig(),
        artifact_store=artifact_store,
        semantic_build_store=FakeSemanticIndexBuildStore(),
    )

    with pytest.raises(EmbeddingProviderUnavailableError) as exc_info:
        use_case.execute(BuildSemanticIndexRequest(snapshot_id=snapshot.snapshot_id))

    assert exc_info.value.details["provider_id"] is None


def test_build_semantic_index_fails_when_chunk_payload_artifact_is_missing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    payload_path = (
        runtime_paths.artifacts / "snapshots" / snapshot.snapshot_id / "chunks" / "missing.json"
    )
    use_case = build_use_case(
        workspace=workspace,
        repository=repository,
        snapshot=snapshot,
        chunks=[
            build_chunk_record(
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                source_file_id="source-a",
                relative_path="assets/app.js",
                language="javascript",
                strategy="javascript_structure",
                payload_path=payload_path,
                start_line=1,
                start_byte=0,
            )
        ],
        semantic_config=build_semantic_config(local_model_path),
        embedding_providers_config=build_embedding_providers_config(local_model_path),
        artifact_store=artifact_store,
        semantic_build_store=FakeSemanticIndexBuildStore(),
    )

    with pytest.raises(SemanticChunkPayloadMissingError):
        use_case.execute(BuildSemanticIndexRequest(snapshot_id=snapshot.snapshot_id))


def test_build_semantic_index_maps_vector_backend_failures_to_stable_error(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    payload_path = artifact_store.write_chunk_payload(
        ChunkPayloadDocument(
            chunk_id="source-a:javascript_structure:1",
            snapshot_id=snapshot.snapshot_id,
            repository_id=repository.repository_id,
            source_file_id="source-a",
            relative_path="assets/app.js",
            language="javascript",
            strategy="javascript_structure",
            source_content_hash="hash-source-a",
            start_line=1,
            end_line=3,
            start_byte=0,
            end_byte=42,
            content='export function boot() { return "codeman"; }',
        ),
        snapshot_id=snapshot.snapshot_id,
    )
    use_case = build_use_case(
        workspace=workspace,
        repository=repository,
        snapshot=snapshot,
        chunks=[
            build_chunk_record(
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                source_file_id="source-a",
                relative_path="assets/app.js",
                language="javascript",
                strategy="javascript_structure",
                payload_path=payload_path,
                start_line=1,
                start_byte=0,
            )
        ],
        semantic_config=build_semantic_config(local_model_path),
        embedding_providers_config=build_embedding_providers_config(local_model_path),
        artifact_store=artifact_store,
        semantic_build_store=FakeSemanticIndexBuildStore(),
        vector_builder=BrokenVectorIndexBuilder(),
    )

    with pytest.raises(VectorIndexBuildError):
        use_case.execute(BuildSemanticIndexRequest(snapshot_id=snapshot.snapshot_id))

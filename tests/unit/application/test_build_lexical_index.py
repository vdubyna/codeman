from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

import codeman.application.indexing.build_lexical_index as build_lexical_index_module
from codeman.application.indexing.build_lexical_index import (
    BuildLexicalIndexUseCase,
    ChunkBaselineMissingError,
    ChunkPayloadCorruptError,
    ChunkPayloadMissingError,
    LexicalSnapshotNotFoundError,
)
from codeman.config.indexing import IndexingConfig, build_indexing_fingerprint
from codeman.contracts.chunking import ChunkPayloadDocument, ChunkRecord
from codeman.contracts.repository import RepositoryRecord, SnapshotRecord
from codeman.contracts.retrieval import (
    BuildLexicalIndexRequest,
    LexicalIndexArtifact,
    LexicalIndexBuildRecord,
    LexicalIndexDocument,
)
from codeman.infrastructure.artifacts.filesystem_artifact_store import (
    FilesystemArtifactStore,
)
from codeman.runtime import build_runtime_paths

DEFAULT_INDEXING_FINGERPRINT = build_indexing_fingerprint(IndexingConfig())


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
class FakeLexicalIndexBuilder:
    runtime_root: Path
    seen_documents: list[LexicalIndexDocument] = field(default_factory=list)
    refreshed_existing_artifact: bool = False

    def build(
        self,
        *,
        repository_id: str,
        snapshot_id: str,
        documents: list[LexicalIndexDocument],
    ) -> LexicalIndexArtifact:
        self.seen_documents = list(documents)
        return LexicalIndexArtifact(
            lexical_engine="sqlite-fts5",
            tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
            indexed_fields=["content", "relative_path"],
            chunks_indexed=len(documents),
            index_path=(
                self.runtime_root
                / "indexes"
                / "lexical"
                / repository_id
                / snapshot_id
                / "lexical.sqlite3"
            ),
            refreshed_existing_artifact=self.refreshed_existing_artifact,
        )


@dataclass
class FakeIndexBuildStore:
    initialized: int = 0
    created_builds: list[LexicalIndexBuildRecord] = field(default_factory=list)

    def initialize(self) -> None:
        self.initialized += 1

    def create_build(self, build: LexicalIndexBuildRecord) -> LexicalIndexBuildRecord:
        self.created_builds.append(build)
        return build

    def get_latest_build_for_snapshot(
        self,
        snapshot_id: str,
    ) -> LexicalIndexBuildRecord | None:
        for build in reversed(self.created_builds):
            if build.snapshot_id == snapshot_id:
                return build
        return None

    def get_latest_build_for_repository(
        self,
        repository_id: str,
    ) -> LexicalIndexBuildRecord | None:
        for build in reversed(self.created_builds):
            if build.repository_id == repository_id:
                return build
        return None


@dataclass
class FakeClock:
    current_ns: int = 0

    def __call__(self) -> int:
        return self.current_ns

    def advance_ms(self, duration_ms: int) -> None:
        self.current_ns += duration_ms * 1_000_000


@dataclass
class ClockedArtifactStore:
    delegate: FilesystemArtifactStore
    clock: FakeClock
    read_delay_ms: int

    def __getattr__(self, name: str) -> object:
        return getattr(self.delegate, name)

    def read_chunk_payload(self, payload_path: Path) -> ChunkPayloadDocument:
        self.clock.advance_ms(self.read_delay_ms)
        return self.delegate.read_chunk_payload(payload_path)


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


def build_snapshot_record(
    repository_id: str,
    workspace: Path,
    *,
    chunk_generation_completed_at: datetime | None = None,
    indexing_config_fingerprint: str | None = DEFAULT_INDEXING_FINGERPRINT,
) -> SnapshotRecord:
    return SnapshotRecord(
        snapshot_id="snapshot-123",
        repository_id=repository_id,
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        manifest_path=(
            workspace
            / ".codeman"
            / "artifacts"
            / "snapshots"
            / "snapshot-123"
            / "manifest.json"
        ),
        created_at=datetime.now(UTC),
        source_inventory_extracted_at=datetime.now(UTC),
        chunk_generation_completed_at=chunk_generation_completed_at,
        indexing_config_fingerprint=indexing_config_fingerprint,
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


def test_build_lexical_index_reads_payloads_in_deterministic_order_and_records_metadata(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(
        repository.repository_id,
        workspace,
        chunk_generation_completed_at=datetime.now(UTC),
    )

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
            content="class HomeController { public function snake_case() {} }",
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
            content="export function snake_case() { return 'ok'; }",
        ),
        snapshot_id=snapshot.snapshot_id,
    )

    chunk_store = FakeChunkStore(
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
    )
    lexical_index_builder = FakeLexicalIndexBuilder(runtime_root=runtime_paths.root)
    index_build_store = FakeIndexBuildStore()
    use_case = BuildLexicalIndexUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        chunk_store=chunk_store,
        artifact_store=artifact_store,
        lexical_index=lexical_index_builder,
        index_build_store=index_build_store,
        indexing_config=IndexingConfig(),
    )

    result = use_case.execute(BuildLexicalIndexRequest(snapshot_id=snapshot.snapshot_id))

    assert [document.chunk_id for document in lexical_index_builder.seen_documents] == [
        "source-a:javascript_structure:1",
        "source-b:php_structure:10",
    ]
    assert result.diagnostics.chunks_indexed == 2
    assert result.build.repository_id == repository.repository_id
    assert result.build.snapshot_id == snapshot.snapshot_id
    assert result.build.indexing_config_fingerprint == DEFAULT_INDEXING_FINGERPRINT
    assert result.build.indexed_fields == ["content", "relative_path"]
    assert result.build.build_duration_ms is not None
    assert result.build.build_duration_ms >= 0
    assert index_build_store.created_builds
    assert index_build_store.created_builds[0].index_path == result.build.index_path


def test_build_lexical_index_duration_includes_chunk_payload_loading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    delegate_store = FilesystemArtifactStore(runtime_paths.artifacts)
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(
        repository.repository_id,
        workspace,
        chunk_generation_completed_at=datetime.now(UTC),
    )
    first_payload_path = delegate_store.write_chunk_payload(
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
            content="export function boot() { return 'ok'; }",
        ),
        snapshot_id=snapshot.snapshot_id,
    )
    second_payload_path = delegate_store.write_chunk_payload(
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
            content="class HomeController { public function __invoke() {} }",
        ),
        snapshot_id=snapshot.snapshot_id,
    )
    clock = FakeClock()
    monkeypatch.setattr(build_lexical_index_module, "perf_counter_ns", clock)
    use_case = BuildLexicalIndexUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        chunk_store=FakeChunkStore(
            chunks=[
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
            ],
        ),
        artifact_store=ClockedArtifactStore(
            delegate=delegate_store,
            clock=clock,
            read_delay_ms=5,
        ),
        lexical_index=FakeLexicalIndexBuilder(runtime_root=runtime_paths.root),
        index_build_store=FakeIndexBuildStore(),
        indexing_config=IndexingConfig(),
    )

    result = use_case.execute(BuildLexicalIndexRequest(snapshot_id=snapshot.snapshot_id))

    assert result.build.build_duration_ms == 10


def test_build_lexical_index_requires_chunk_baseline_for_current_configuration(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(
        repository.repository_id,
        workspace,
        chunk_generation_completed_at=datetime.now(UTC),
    )
    runtime_paths = build_runtime_paths(workspace)
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
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
            content="export function boot() { return 'ok'; }",
        ),
        snapshot_id=snapshot.snapshot_id,
    )
    index_build_store = FakeIndexBuildStore()
    use_case = BuildLexicalIndexUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        chunk_store=FakeChunkStore(
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
        ),
        artifact_store=artifact_store,
        lexical_index=FakeLexicalIndexBuilder(runtime_root=runtime_paths.root),
        index_build_store=index_build_store,
        indexing_config=IndexingConfig(fingerprint_salt="profile-v2"),
    )

    with pytest.raises(ChunkBaselineMissingError) as exc_info:
        use_case.execute(BuildLexicalIndexRequest(snapshot_id=snapshot.snapshot_id))

    assert "current configuration" in exc_info.value.message
    assert index_build_store.created_builds == []


def test_build_lexical_index_requires_existing_chunk_baseline(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(
        repository.repository_id,
        workspace,
        chunk_generation_completed_at=None,
    )
    runtime_paths = build_runtime_paths(workspace)
    use_case = BuildLexicalIndexUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        chunk_store=FakeChunkStore(chunks=[]),
        artifact_store=FilesystemArtifactStore(runtime_paths.artifacts),
        lexical_index=FakeLexicalIndexBuilder(runtime_root=runtime_paths.root),
        index_build_store=FakeIndexBuildStore(),
        indexing_config=IndexingConfig(),
    )

    with pytest.raises(ChunkBaselineMissingError):
        use_case.execute(BuildLexicalIndexRequest(snapshot_id=snapshot.snapshot_id))


def test_build_lexical_index_requires_chunk_rows_even_when_snapshot_is_marked_complete(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(
        repository.repository_id,
        workspace,
        chunk_generation_completed_at=datetime.now(UTC),
    )
    runtime_paths = build_runtime_paths(workspace)
    use_case = BuildLexicalIndexUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        chunk_store=FakeChunkStore(chunks=[]),
        artifact_store=FilesystemArtifactStore(runtime_paths.artifacts),
        lexical_index=FakeLexicalIndexBuilder(runtime_root=runtime_paths.root),
        index_build_store=FakeIndexBuildStore(),
        indexing_config=IndexingConfig(),
    )

    with pytest.raises(ChunkBaselineMissingError):
        use_case.execute(BuildLexicalIndexRequest(snapshot_id=snapshot.snapshot_id))


def test_build_lexical_index_fails_for_missing_chunk_payload(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(
        repository.repository_id,
        workspace,
        chunk_generation_completed_at=datetime.now(UTC),
    )
    runtime_paths = build_runtime_paths(workspace)
    missing_payload_path = (
        runtime_paths.artifacts
        / "snapshots"
        / snapshot.snapshot_id
        / "chunks"
        / "missing.json"
    )
    use_case = BuildLexicalIndexUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        chunk_store=FakeChunkStore(
            chunks=[
                build_chunk_record(
                    snapshot_id=snapshot.snapshot_id,
                    repository_id=repository.repository_id,
                    source_file_id="source-a",
                    relative_path="assets/app.js",
                    language="javascript",
                    strategy="javascript_structure",
                    payload_path=missing_payload_path,
                    start_line=1,
                    start_byte=0,
                )
            ],
        ),
        artifact_store=FilesystemArtifactStore(runtime_paths.artifacts),
        lexical_index=FakeLexicalIndexBuilder(runtime_root=runtime_paths.root),
        index_build_store=FakeIndexBuildStore(),
        indexing_config=IndexingConfig(),
    )

    with pytest.raises(ChunkPayloadMissingError):
        use_case.execute(BuildLexicalIndexRequest(snapshot_id=snapshot.snapshot_id))


def test_build_lexical_index_fails_for_corrupt_chunk_payload(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(
        repository.repository_id,
        workspace,
        chunk_generation_completed_at=datetime.now(UTC),
    )
    runtime_paths = build_runtime_paths(workspace)
    payload_path = (
        runtime_paths.artifacts
        / "snapshots"
        / snapshot.snapshot_id
        / "chunks"
        / "corrupt.json"
    )
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text("{not-valid-json", encoding="utf-8")
    use_case = BuildLexicalIndexUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        chunk_store=FakeChunkStore(
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
        ),
        artifact_store=FilesystemArtifactStore(runtime_paths.artifacts),
        lexical_index=FakeLexicalIndexBuilder(runtime_root=runtime_paths.root),
        index_build_store=FakeIndexBuildStore(),
        indexing_config=IndexingConfig(),
    )

    with pytest.raises(ChunkPayloadCorruptError):
        use_case.execute(BuildLexicalIndexRequest(snapshot_id=snapshot.snapshot_id))


def test_build_lexical_index_requires_a_known_snapshot(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    use_case = BuildLexicalIndexUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=None),
        snapshot_store=FakeSnapshotStore(snapshot=None),
        chunk_store=FakeChunkStore(chunks=[]),
        artifact_store=FilesystemArtifactStore(runtime_paths.artifacts),
        lexical_index=FakeLexicalIndexBuilder(runtime_root=runtime_paths.root),
        index_build_store=FakeIndexBuildStore(),
        indexing_config=IndexingConfig(),
    )

    with pytest.raises(LexicalSnapshotNotFoundError):
        use_case.execute(BuildLexicalIndexRequest(snapshot_id="snapshot-missing"))

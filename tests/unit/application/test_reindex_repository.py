from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from codeman.application.ports.snapshot_port import ResolvedRevision
from codeman.application.ports.source_inventory_port import ScanSourceFilesResult
from codeman.application.repo.reindex_repository import (
    ReindexRepositoryUseCase,
    build_inventory_diff,
    classify_change_reason,
    is_reusable_source_file,
)
from codeman.config.indexing import IndexingConfig, build_indexing_fingerprint
from codeman.contracts.chunking import ChunkPayloadDocument, ChunkRecord
from codeman.contracts.reindexing import (
    ChangeReason,
    ReindexRepositoryRequest,
    ReindexRunRecord,
)
from codeman.contracts.repository import RepositoryRecord, SnapshotRecord, SourceFileRecord
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

    def get_latest_indexed_snapshot(self, repository_id: str) -> SnapshotRecord | None:
        if self.snapshot is None or self.snapshot.repository_id != repository_id:
            return None
        return self.snapshot

    def get_by_snapshot_id(self, snapshot_id: str) -> SnapshotRecord | None:
        if self.snapshot is None or self.snapshot.snapshot_id != snapshot_id:
            return None
        return self.snapshot

    def mark_chunks_generated(
        self,
        *,
        snapshot_id: str,
        generated_at: datetime,
        indexing_config_fingerprint: str,
    ) -> None:
        del snapshot_id, generated_at, indexing_config_fingerprint


@dataclass
class FakeSourceInventoryStore:
    source_files: list[SourceFileRecord]
    initialized: int = 0

    def initialize(self) -> None:
        self.initialized += 1

    def list_by_snapshot(self, snapshot_id: str) -> list[SourceFileRecord]:
        return [record for record in self.source_files if record.snapshot_id == snapshot_id]


@dataclass
class FakeSourceScanner:
    result: ScanSourceFilesResult
    seen_paths: list[Path]

    def scan(
        self,
        *,
        repository_path: Path,
        snapshot_id: str,
        repository_id: str,
        discovered_at: datetime,
    ) -> ScanSourceFilesResult:
        del snapshot_id, repository_id, discovered_at
        self.seen_paths.append(repository_path)
        return self.result


@dataclass
class FakeChunkStore:
    chunks: list[ChunkRecord]
    initialized: int = 0

    def initialize(self) -> None:
        self.initialized += 1

    def list_by_snapshot(self, snapshot_id: str) -> list[ChunkRecord]:
        return [chunk for chunk in self.chunks if chunk.snapshot_id == snapshot_id]

    def upsert_chunks(self, chunks: list[ChunkRecord]) -> list[ChunkRecord]:
        self.chunks.extend(chunks)
        return chunks


@dataclass
class FakeReindexRunStore:
    created_runs: list[ReindexRunRecord]
    initialized: int = 0

    def initialize(self) -> None:
        self.initialized += 1

    def create_run(
        self,
        *,
        repository_id: str,
        previous_snapshot_id: str,
        result_snapshot_id: str,
        previous_revision_identity: str,
        result_revision_identity: str,
        previous_config_fingerprint: str,
        current_config_fingerprint: str,
        change_reason: ChangeReason,
        source_files_reused: int,
        source_files_rebuilt: int,
        source_files_removed: int,
        chunks_reused: int,
        chunks_rebuilt: int,
        created_at: datetime,
    ) -> ReindexRunRecord:
        record = ReindexRunRecord(
            run_id="run-123",
            repository_id=repository_id,
            previous_snapshot_id=previous_snapshot_id,
            result_snapshot_id=result_snapshot_id,
            previous_revision_identity=previous_revision_identity,
            result_revision_identity=result_revision_identity,
            previous_config_fingerprint=previous_config_fingerprint,
            current_config_fingerprint=current_config_fingerprint,
            change_reason=change_reason,
            source_files_reused=source_files_reused,
            source_files_rebuilt=source_files_rebuilt,
            source_files_removed=source_files_removed,
            chunks_reused=chunks_reused,
            chunks_rebuilt=chunks_rebuilt,
            created_at=created_at,
        )
        self.created_runs.append(record)
        return record


@dataclass
class FakeRevisionResolver:
    revision: ResolvedRevision

    def resolve(self, repository_path: Path) -> ResolvedRevision:
        del repository_path
        return self.revision


class UnexpectedCreateSnapshotUseCase:
    def execute(self, _request: object) -> object:
        raise AssertionError("create_snapshot should not be called for a noop reindex")


class UnexpectedExtractSourceFilesUseCase:
    def execute(self, _request: object) -> object:
        raise AssertionError("extract_source_files should not be called for a noop reindex")


class FakeArtifactStore:
    def write_snapshot_manifest(self, manifest: object) -> Path:
        raise NotImplementedError

    def write_chunk_payload(self, payload: ChunkPayloadDocument, *, snapshot_id: str) -> Path:
        raise NotImplementedError

    def read_chunk_payload(self, payload_path: Path) -> ChunkPayloadDocument:
        raise NotImplementedError


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
    indexing_config_fingerprint: str | None = None,
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
        chunk_generation_completed_at=datetime.now(UTC),
        indexing_config_fingerprint=indexing_config_fingerprint,
    )


def build_source_file_record(
    *,
    snapshot_id: str,
    repository_id: str,
    relative_path: str,
    language: str,
    content_hash: str,
) -> SourceFileRecord:
    return SourceFileRecord(
        source_file_id=f"{snapshot_id}:{relative_path}",
        snapshot_id=snapshot_id,
        repository_id=repository_id,
        relative_path=relative_path,
        language=language,
        content_hash=content_hash,
        byte_size=42,
        discovered_at=datetime.now(UTC),
    )


def build_chunk_record(
    *,
    snapshot_id: str,
    repository_id: str,
    source_file_id: str,
    relative_path: str,
    strategy: str,
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=f"{source_file_id}:{strategy}",
        snapshot_id=snapshot_id,
        repository_id=repository_id,
        source_file_id=source_file_id,
        relative_path=relative_path,
        language="javascript",
        strategy=strategy,
        source_content_hash="hash-123",
        start_line=1,
        end_line=3,
        start_byte=0,
        end_byte=42,
        payload_path=Path("/tmp") / f"{source_file_id}.json",
        created_at=datetime.now(UTC),
    )


def test_build_indexing_fingerprint_is_stable_for_the_same_config() -> None:
    config = IndexingConfig(fingerprint_salt="stable")

    first = build_indexing_fingerprint(config)
    second = build_indexing_fingerprint(config)

    assert first == second


def test_classify_change_reason_and_reuse_rules_are_stable() -> None:
    source_file = build_source_file_record(
        snapshot_id="snapshot-1",
        repository_id="repo-123",
        relative_path="assets/app.js",
        language="javascript",
        content_hash="hash-123",
    )
    same_source_file = build_source_file_record(
        snapshot_id="snapshot-2",
        repository_id="repo-123",
        relative_path="assets/app.js",
        language="javascript",
        content_hash="hash-123",
    )
    changed_source_file = build_source_file_record(
        snapshot_id="snapshot-2",
        repository_id="repo-123",
        relative_path="assets/app.js",
        language="javascript",
        content_hash="hash-456",
    )

    assert classify_change_reason(source_changed=False, config_changed=False) == "no_change"
    assert classify_change_reason(source_changed=True, config_changed=False) == "source_changed"
    assert classify_change_reason(source_changed=False, config_changed=True) == "config_changed"
    assert (
        classify_change_reason(source_changed=True, config_changed=True)
        == "source_and_config_changed"
    )
    assert is_reusable_source_file(
        previous_source_file=source_file,
        current_source_file=same_source_file,
        previous_config_fingerprint="fp-1",
        current_config_fingerprint="fp-1",
    )
    assert not is_reusable_source_file(
        previous_source_file=source_file,
        current_source_file=changed_source_file,
        previous_config_fingerprint="fp-1",
        current_config_fingerprint="fp-1",
    )


def test_build_inventory_diff_detects_removed_and_newly_unsupported_files(
    tmp_path: Path,
) -> None:
    repository_path = tmp_path / "repo"
    (repository_path / "assets").mkdir(parents=True)
    (repository_path / "templates").mkdir(parents=True)
    (repository_path / "assets" / "app.js").write_bytes(b"\x00\x01\x02\x03")

    baseline_source_files = [
        build_source_file_record(
            snapshot_id="snapshot-1",
            repository_id="repo-123",
            relative_path="assets/app.js",
            language="javascript",
            content_hash="hash-123",
        ),
        build_source_file_record(
            snapshot_id="snapshot-1",
            repository_id="repo-123",
            relative_path="templates/old.html",
            language="html",
            content_hash="hash-456",
        ),
    ]

    diff = build_inventory_diff(
        baseline_source_files=baseline_source_files,
        current_source_files=[],
        repository_path=repository_path,
    )

    assert [record.relative_path for record in diff.newly_unsupported] == ["assets/app.js"]
    assert [record.relative_path for record in diff.removed] == ["templates/old.html"]


def test_reindex_returns_noop_without_creating_new_snapshot(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    (repository_path / "assets").mkdir(parents=True)
    (repository_path / "README.md").write_text("new docs only\n", encoding="utf-8")
    repository = build_repository_record(repository_path.resolve())
    fingerprint = build_indexing_fingerprint(IndexingConfig())
    snapshot = build_snapshot_record(
        repository.repository_id,
        workspace,
        indexing_config_fingerprint=fingerprint,
    )
    source_file = build_source_file_record(
        snapshot_id=snapshot.snapshot_id,
        repository_id=repository.repository_id,
        relative_path="assets/app.js",
        language="javascript",
        content_hash="hash-123",
    )
    chunk = build_chunk_record(
        snapshot_id=snapshot.snapshot_id,
        repository_id=repository.repository_id,
        source_file_id=source_file.source_file_id,
        relative_path=source_file.relative_path,
        strategy="javascript_structure",
    )
    reindex_run_store = FakeReindexRunStore(created_runs=[])
    source_scanner = FakeSourceScanner(
        result=ScanSourceFilesResult(source_files=(source_file,), skipped_by_reason={}),
        seen_paths=[],
    )
    use_case = ReindexRepositoryUseCase(
        runtime_paths=build_runtime_paths(workspace),
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        source_inventory_store=FakeSourceInventoryStore(source_files=[source_file]),
        source_scanner=source_scanner,
        chunk_store=FakeChunkStore(chunks=[chunk]),
        reindex_run_store=reindex_run_store,
        revision_resolver=FakeRevisionResolver(
            revision=ResolvedRevision(
                identity="revision-with-readme-change",
                source=snapshot.revision_source,
            ),
        ),
        create_snapshot=UnexpectedCreateSnapshotUseCase(),
        extract_source_files=UnexpectedExtractSourceFilesUseCase(),
        parser_registry=object(),  # pragma: no cover - noop path never reaches this
        chunker_registry=object(),  # pragma: no cover - noop path never reaches this
        artifact_store=FakeArtifactStore(),
        indexing_config=IndexingConfig(),
    )

    result = use_case.execute(
        ReindexRepositoryRequest(repository_id=repository.repository_id),
    )

    assert result.noop is True
    assert result.previous_snapshot_id == snapshot.snapshot_id
    assert result.result_snapshot_id == snapshot.snapshot_id
    assert result.previous_revision_identity == snapshot.revision_identity
    assert result.result_revision_identity == "revision-with-readme-change"
    assert result.source_files_reused == 1
    assert result.chunks_reused == 1
    assert reindex_run_store.created_runs[0].change_reason == "no_change"
    assert source_scanner.seen_paths == [repository_path.resolve()]

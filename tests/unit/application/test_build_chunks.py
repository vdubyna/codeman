from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codeman.application.indexing.build_chunks import (
    BuildChunksUseCase,
    SourceInventoryMissingError,
    build_chunk_id,
)
from codeman.application.ports.snapshot_port import ResolvedRevision
from codeman.config.cache_identity import build_chunk_cache_key
from codeman.config.indexing import IndexingConfig, build_indexing_fingerprint
from codeman.contracts.chunking import BuildChunksRequest, ChunkPayloadDocument, ChunkRecord
from codeman.contracts.repository import RepositoryRecord, SnapshotRecord, SourceFileRecord
from codeman.infrastructure.cache.filesystem_cache_store import FilesystemCacheStore
from codeman.infrastructure.chunkers.chunker_registry import ChunkerRegistry
from codeman.infrastructure.parsers.parser_registry import ParserRegistry
from codeman.runtime import build_runtime_paths


@dataclass
class FakeRepositoryStore:
    repository: RepositoryRecord | None

    def get_by_repository_id(self, repository_id: str) -> RepositoryRecord | None:
        if self.repository is None or self.repository.repository_id != repository_id:
            return None
        return self.repository


@dataclass
class FakeSnapshotStore:
    snapshot: SnapshotRecord | None
    initialized: int = 0
    marked_chunks: list[tuple[str, datetime, str]] | None = None

    def initialize(self) -> None:
        self.initialized += 1

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
        if self.marked_chunks is None:
            self.marked_chunks = []
        self.marked_chunks.append(
            (snapshot_id, generated_at, indexing_config_fingerprint),
        )


@dataclass
class FakeSourceInventoryStore:
    source_files: list[SourceFileRecord]
    initialized: int = 0

    def initialize(self) -> None:
        self.initialized += 1

    def list_by_snapshot(self, snapshot_id: str) -> list[SourceFileRecord]:
        return [record for record in self.source_files if record.snapshot_id == snapshot_id]


@dataclass
class FakeChunkStore:
    initialized: int = 0
    persisted: list[ChunkRecord] | None = None

    def initialize(self) -> None:
        self.initialized += 1

    def upsert_chunks(self, chunks: list[ChunkRecord]) -> list[ChunkRecord]:
        self.persisted = list(chunks)
        return list(chunks)


@dataclass
class FakeRevisionResolver:
    revision: ResolvedRevision
    seen_paths: list[Path]

    def resolve(self, repository_path: Path) -> ResolvedRevision:
        self.seen_paths.append(repository_path)
        return self.revision


@dataclass
class FakeArtifactStore:
    artifacts_root: Path
    payloads: list[Path]

    def write_snapshot_manifest(self, manifest: object) -> Path:
        raise NotImplementedError

    def write_chunk_payload(self, payload: ChunkPayloadDocument, *, snapshot_id: str) -> Path:
        destination = (
            self.artifacts_root / "snapshots" / snapshot_id / "chunks" / f"{payload.chunk_id}.json"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
        self.payloads.append(destination)
        return destination

    def read_chunk_payload(self, payload_path: Path) -> ChunkPayloadDocument:
        return ChunkPayloadDocument.model_validate_json(
            payload_path.read_text(encoding="utf-8"),
        )


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
    source_inventory_extracted_at: datetime | None = None,
) -> SnapshotRecord:
    return SnapshotRecord(
        snapshot_id="snapshot-123",
        repository_id=repository_id,
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        manifest_path=(
            workspace / ".codeman" / "artifacts" / "snapshots" / "snapshot-123" / "manifest.json"
        ),
        created_at=datetime.now(UTC),
        source_inventory_extracted_at=source_inventory_extracted_at,
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


def test_build_chunk_id_is_stable_for_the_same_span() -> None:
    first = build_chunk_id(
        source_file_id="source-123",
        strategy="javascript_structure",
        start_line=1,
        end_line=3,
        start_byte=0,
        end_byte=42,
    )
    second = build_chunk_id(
        source_file_id="source-123",
        strategy="javascript_structure",
        start_line=1,
        end_line=3,
        start_byte=0,
        end_byte=42,
    )

    assert first == second


def test_build_chunks_falls_back_per_file_and_writes_payload_artifacts(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    (repository_path / "assets").mkdir(parents=True)
    (repository_path / "assets" / "app.js").write_text(
        'export function boot() {\n  return "ok";\n}\n',
        encoding="utf-8",
    )
    (repository_path / "assets" / "broken.js").write_text(
        'export function broken() {\n  return "missing";\n',
        encoding="utf-8",
    )

    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    source_inventory_store = FakeSourceInventoryStore(
        source_files=[
            build_source_file_record(
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                relative_path="assets/app.js",
                language="javascript",
                content_hash="hash-app",
            ),
            build_source_file_record(
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                relative_path="assets/broken.js",
                language="javascript",
                content_hash="hash-broken",
            ),
        ],
    )
    chunk_store = FakeChunkStore()
    artifact_store = FakeArtifactStore(
        artifacts_root=workspace / ".codeman" / "artifacts",
        payloads=[],
    )
    use_case = BuildChunksUseCase(
        runtime_paths=build_runtime_paths(workspace),
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        source_inventory_store=source_inventory_store,
        chunk_store=chunk_store,
        revision_resolver=FakeRevisionResolver(
            revision=ResolvedRevision(
                identity=snapshot.revision_identity,
                source=snapshot.revision_source,
            ),
            seen_paths=[],
        ),
        parser_registry=ParserRegistry(),
        chunker_registry=ChunkerRegistry(),
        artifact_store=artifact_store,
        cache_store=FilesystemCacheStore(workspace / ".codeman" / "cache"),
        indexing_config=IndexingConfig(),
    )

    result = use_case.execute(BuildChunksRequest(snapshot_id=snapshot.snapshot_id))

    assert chunk_store.persisted is not None
    assert result.diagnostics.total_chunks == 2
    assert result.diagnostics.fallback_file_count == 1
    assert result.diagnostics.chunks_by_strategy == {
        "javascript_fallback": 1,
        "javascript_structure": 1,
    }
    assert result.diagnostics.cache_summary.chunk_entries_regenerated == 2
    broken_diagnostic = next(
        diagnostic
        for diagnostic in result.diagnostics.file_diagnostics
        if diagnostic.relative_path == "assets/broken.js"
    )
    assert broken_diagnostic.mode == "fallback"
    assert artifact_store.payloads and all(path.exists() for path in artifact_store.payloads)

    payload = json.loads(artifact_store.payloads[0].read_text(encoding="utf-8"))
    assert payload["relative_path"] == "assets/app.js"
    assert "content" in payload


def test_build_chunks_requires_extracted_source_inventory(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    use_case = BuildChunksUseCase(
        runtime_paths=build_runtime_paths(workspace),
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        source_inventory_store=FakeSourceInventoryStore(source_files=[]),
        chunk_store=FakeChunkStore(),
        revision_resolver=FakeRevisionResolver(
            revision=ResolvedRevision(
                identity=snapshot.revision_identity,
                source=snapshot.revision_source,
            ),
            seen_paths=[],
        ),
        parser_registry=ParserRegistry(),
        chunker_registry=ChunkerRegistry(),
        artifact_store=FakeArtifactStore(
            artifacts_root=workspace / ".codeman" / "artifacts",
            payloads=[],
        ),
        cache_store=FilesystemCacheStore(workspace / ".codeman" / "cache"),
        indexing_config=IndexingConfig(),
    )

    with pytest.raises(SourceInventoryMissingError):
        use_case.execute(BuildChunksRequest(snapshot_id=snapshot.snapshot_id))


def test_build_chunks_returns_zero_chunks_for_extracted_snapshot_with_no_supported_files(
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
        source_inventory_extracted_at=datetime.now(UTC),
    )
    chunk_store = FakeChunkStore()
    use_case = BuildChunksUseCase(
        runtime_paths=build_runtime_paths(workspace),
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        source_inventory_store=FakeSourceInventoryStore(source_files=[]),
        chunk_store=chunk_store,
        revision_resolver=FakeRevisionResolver(
            revision=ResolvedRevision(
                identity=snapshot.revision_identity,
                source=snapshot.revision_source,
            ),
            seen_paths=[],
        ),
        parser_registry=ParserRegistry(),
        chunker_registry=ChunkerRegistry(),
        artifact_store=FakeArtifactStore(
            artifacts_root=workspace / ".codeman" / "artifacts",
            payloads=[],
        ),
        cache_store=FilesystemCacheStore(workspace / ".codeman" / "cache"),
        indexing_config=IndexingConfig(),
    )

    result = use_case.execute(BuildChunksRequest(snapshot_id=snapshot.snapshot_id))

    assert result.diagnostics.total_chunks == 0
    assert result.chunks == []
    assert chunk_store.persisted == []


def test_build_chunks_falls_back_when_preferred_path_raises_unexpected_exception(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    (repository_path / "assets").mkdir(parents=True)
    (repository_path / "assets" / "app.js").write_text(
        'export function boot() {\n  return "ok";\n}\n',
        encoding="utf-8",
    )
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(
        repository.repository_id,
        workspace,
        source_inventory_extracted_at=datetime.now(UTC),
    )

    class ExplodingParser:
        def parse(self, *, source_text: str, relative_path: str) -> tuple[()]:
            del source_text, relative_path
            raise ValueError("boom")

    class ExplodingParserRegistry:
        def get(self, language: str) -> ExplodingParser:
            del language
            return ExplodingParser()

    class DelegatingChunkerRegistry:
        def __init__(self) -> None:
            self.registry = ChunkerRegistry()

        def get_structural(self, language: str) -> object:
            return self.registry.get_structural(language)

        def get_fallback(self, language: str) -> object:
            return self.registry.get_fallback(language)

    source_inventory_store = FakeSourceInventoryStore(
        source_files=[
            build_source_file_record(
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                relative_path="assets/app.js",
                language="javascript",
                content_hash="hash-app",
            ),
        ],
    )
    use_case = BuildChunksUseCase(
        runtime_paths=build_runtime_paths(workspace),
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        source_inventory_store=source_inventory_store,
        chunk_store=FakeChunkStore(),
        revision_resolver=FakeRevisionResolver(
            revision=ResolvedRevision(
                identity=snapshot.revision_identity,
                source=snapshot.revision_source,
            ),
            seen_paths=[],
        ),
        parser_registry=ExplodingParserRegistry(),
        chunker_registry=DelegatingChunkerRegistry(),
        artifact_store=FakeArtifactStore(
            artifacts_root=workspace / ".codeman" / "artifacts",
            payloads=[],
        ),
        cache_store=FilesystemCacheStore(workspace / ".codeman" / "cache"),
        indexing_config=IndexingConfig(),
    )

    result = use_case.execute(BuildChunksRequest(snapshot_id=snapshot.snapshot_id))

    assert result.diagnostics.fallback_file_count == 1
    assert result.diagnostics.chunks_by_strategy == {"javascript_fallback": 1}
    assert result.diagnostics.file_diagnostics[0].mode == "fallback"


def test_build_chunks_reuses_chunk_cache_on_second_run(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    (repository_path / "assets").mkdir(parents=True)
    (repository_path / "assets" / "app.js").write_text(
        'export function boot() {\n  return "ok";\n}\n',
        encoding="utf-8",
    )

    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    source_file = build_source_file_record(
        snapshot_id=snapshot.snapshot_id,
        repository_id=repository.repository_id,
        relative_path="assets/app.js",
        language="javascript",
        content_hash="hash-app",
    )
    use_case = BuildChunksUseCase(
        runtime_paths=build_runtime_paths(workspace),
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        source_inventory_store=FakeSourceInventoryStore(source_files=[source_file]),
        chunk_store=FakeChunkStore(),
        revision_resolver=FakeRevisionResolver(
            revision=ResolvedRevision(
                identity=snapshot.revision_identity,
                source=snapshot.revision_source,
            ),
            seen_paths=[],
        ),
        parser_registry=ParserRegistry(),
        chunker_registry=ChunkerRegistry(),
        artifact_store=FakeArtifactStore(
            artifacts_root=workspace / ".codeman" / "artifacts",
            payloads=[],
        ),
        cache_store=FilesystemCacheStore(workspace / ".codeman" / "cache"),
        indexing_config=IndexingConfig(),
    )

    first = use_case.execute(BuildChunksRequest(snapshot_id=snapshot.snapshot_id))
    second = use_case.execute(BuildChunksRequest(snapshot_id=snapshot.snapshot_id))

    assert first.diagnostics.cache_summary.chunk_entries_regenerated == 1
    assert second.diagnostics.cache_summary.chunk_entries_reused == 1
    assert second.diagnostics.cache_summary.chunk_entries_regenerated == 0
    assert second.diagnostics.cache_summary.parser_entries_reused == 0


def test_build_chunks_rebuilds_fallback_cache_when_structural_path_recovers(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    (repository_path / "assets").mkdir(parents=True)
    (repository_path / "assets" / "app.js").write_text(
        'export function boot() {\n  return "ok";\n}\n',
        encoding="utf-8",
    )

    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    source_file = build_source_file_record(
        snapshot_id=snapshot.snapshot_id,
        repository_id=repository.repository_id,
        relative_path="assets/app.js",
        language="javascript",
        content_hash="hash-app",
    )

    class ExplodingParser:
        def parse(self, *, source_text: str, relative_path: str) -> tuple[()]:
            del source_text, relative_path
            raise ValueError("boom")

    class ExplodingParserRegistry:
        def get(self, language: str) -> ExplodingParser:
            del language
            return ExplodingParser()

    first = BuildChunksUseCase(
        runtime_paths=build_runtime_paths(workspace),
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        source_inventory_store=FakeSourceInventoryStore(source_files=[source_file]),
        chunk_store=FakeChunkStore(),
        revision_resolver=FakeRevisionResolver(
            revision=ResolvedRevision(
                identity=snapshot.revision_identity,
                source=snapshot.revision_source,
            ),
            seen_paths=[],
        ),
        parser_registry=ExplodingParserRegistry(),
        chunker_registry=ChunkerRegistry(),
        artifact_store=FakeArtifactStore(
            artifacts_root=workspace / ".codeman" / "artifacts",
            payloads=[],
        ),
        cache_store=FilesystemCacheStore(workspace / ".codeman" / "cache"),
        indexing_config=IndexingConfig(),
    ).execute(BuildChunksRequest(snapshot_id=snapshot.snapshot_id))

    second = BuildChunksUseCase(
        runtime_paths=build_runtime_paths(workspace),
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        source_inventory_store=FakeSourceInventoryStore(source_files=[source_file]),
        chunk_store=FakeChunkStore(),
        revision_resolver=FakeRevisionResolver(
            revision=ResolvedRevision(
                identity=snapshot.revision_identity,
                source=snapshot.revision_source,
            ),
            seen_paths=[],
        ),
        parser_registry=ParserRegistry(),
        chunker_registry=ChunkerRegistry(),
        artifact_store=FakeArtifactStore(
            artifacts_root=workspace / ".codeman" / "artifacts",
            payloads=[],
        ),
        cache_store=FilesystemCacheStore(workspace / ".codeman" / "cache"),
        indexing_config=IndexingConfig(),
    ).execute(BuildChunksRequest(snapshot_id=snapshot.snapshot_id))

    assert first.diagnostics.file_diagnostics[0].mode == "fallback"
    assert second.diagnostics.file_diagnostics[0].mode == "structural"
    assert second.diagnostics.chunks_by_strategy == {"javascript_structure": 1}
    assert second.diagnostics.cache_summary.chunk_entries_reused == 0
    assert second.diagnostics.cache_summary.chunk_entries_regenerated == 1
    assert second.diagnostics.cache_summary.parser_entries_regenerated == 1


def test_build_chunks_rebuilds_when_chunk_cache_is_corrupt_but_reuses_parser_cache(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    (repository_path / "assets").mkdir(parents=True)
    (repository_path / "assets" / "app.js").write_text(
        'export function boot() {\n  return "ok";\n}\n',
        encoding="utf-8",
    )

    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    source_file = build_source_file_record(
        snapshot_id=snapshot.snapshot_id,
        repository_id=repository.repository_id,
        relative_path="assets/app.js",
        language="javascript",
        content_hash="hash-app",
    )
    use_case = BuildChunksUseCase(
        runtime_paths=build_runtime_paths(workspace),
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        source_inventory_store=FakeSourceInventoryStore(source_files=[source_file]),
        chunk_store=FakeChunkStore(),
        revision_resolver=FakeRevisionResolver(
            revision=ResolvedRevision(
                identity=snapshot.revision_identity,
                source=snapshot.revision_source,
            ),
            seen_paths=[],
        ),
        parser_registry=ParserRegistry(),
        chunker_registry=ChunkerRegistry(),
        artifact_store=FakeArtifactStore(
            artifacts_root=workspace / ".codeman" / "artifacts",
            payloads=[],
        ),
        cache_store=FilesystemCacheStore(workspace / ".codeman" / "cache"),
        indexing_config=IndexingConfig(),
    )

    use_case.execute(BuildChunksRequest(snapshot_id=snapshot.snapshot_id))
    chunk_cache_path = (
        workspace
        / ".codeman"
        / "cache"
        / "chunk"
        / (
            build_chunk_cache_key(
                language=source_file.language,
                relative_path=source_file.relative_path,
                source_content_hash=source_file.content_hash,
                indexing_config_fingerprint=build_indexing_fingerprint(IndexingConfig()),
            )
            + ".json"
        )
    )
    chunk_cache_path.write_text("{invalid", encoding="utf-8")

    result = use_case.execute(BuildChunksRequest(snapshot_id=snapshot.snapshot_id))

    assert result.diagnostics.cache_summary.chunk_entries_reused == 0
    assert result.diagnostics.cache_summary.chunk_entries_regenerated == 1
    assert result.diagnostics.cache_summary.parser_entries_reused == 1

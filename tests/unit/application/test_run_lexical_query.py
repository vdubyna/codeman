from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codeman.application.query.format_results import RetrievalResultFormatter
from codeman.application.query.run_lexical_query import (
    LexicalArtifactMissingError,
    LexicalBuildBaselineMissingError,
    LexicalQueryChunkMetadataMissingError,
    LexicalQueryChunkPayloadMissingError,
    LexicalQueryError,
    LexicalQueryRepositoryNotRegisteredError,
    RunLexicalQueryUseCase,
)
from codeman.contracts.chunking import ChunkPayloadDocument, ChunkRecord
from codeman.contracts.repository import RepositoryRecord, SnapshotRecord
from codeman.contracts.retrieval import (
    LexicalIndexBuildRecord,
    LexicalQueryDiagnostics,
    LexicalQueryMatch,
    LexicalQueryResult,
    RunLexicalQueryRequest,
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
class FakeIndexBuildStore:
    build: LexicalIndexBuildRecord | None
    initialized: int = 0

    def initialize(self) -> None:
        self.initialized += 1

    def create_build(self, build: LexicalIndexBuildRecord) -> LexicalIndexBuildRecord:
        self.build = build
        return build

    def get_latest_build_for_snapshot(
        self,
        snapshot_id: str,
    ) -> LexicalIndexBuildRecord | None:
        if self.build is None or self.build.snapshot_id != snapshot_id:
            return None
        return self.build

    def get_latest_build_for_repository(
        self,
        repository_id: str,
    ) -> LexicalIndexBuildRecord | None:
        if self.build is None or self.build.repository_id != repository_id:
            return None
        return self.build


@dataclass
class FakeLexicalQueryEngine:
    result: LexicalQueryResult | None = None
    error: Exception | None = None
    initialized: list[tuple[str, str, int]] = field(default_factory=list)

    def query(
        self,
        *,
        build: LexicalIndexBuildRecord,
        query_text: str,
        max_results: int = 20,
    ) -> LexicalQueryResult:
        self.initialized.append((build.build_id, query_text, max_results))
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


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


def build_index_record(workspace: Path, repository_id: str) -> LexicalIndexBuildRecord:
    return LexicalIndexBuildRecord(
        build_id="build-123",
        repository_id=repository_id,
        snapshot_id="snapshot-123",
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        indexing_config_fingerprint="fingerprint-123",
        lexical_engine="sqlite-fts5",
        tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
        indexed_fields=["content", "relative_path"],
        chunks_indexed=3,
        index_path=workspace / ".codeman" / "indexes" / "lexical.sqlite3",
        created_at=datetime.now(UTC),
    )


def build_query_result() -> LexicalQueryResult:
    return LexicalQueryResult(
        matches=[
            LexicalQueryMatch(
                chunk_id="chunk-1",
                relative_path="assets/app.js",
                language="javascript",
                strategy="javascript_structure",
                score=-1.25,
                rank=1,
                content_match_context="export function [bootValue]() { ... }",
                content_match_highlighted=True,
            ),
            LexicalQueryMatch(
                chunk_id="chunk-2",
                relative_path="src/Controller/HomeController.php",
                language="php",
                strategy="php_structure",
                score=-0.5,
                rank=2,
                path_match_context="src/Controller/[HomeController].php",
                path_match_highlighted=True,
            ),
        ],
        diagnostics=LexicalQueryDiagnostics(
            match_count=2,
            query_latency_ms=4,
            total_match_count=2,
            truncated=False,
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


def test_run_lexical_query_returns_ranked_matches_with_repository_context(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    build = build_index_record(workspace, repository.repository_id)
    build.index_path.parent.mkdir(parents=True, exist_ok=True)
    build.index_path.touch()
    chunks = build_chunk_records(workspace)
    query_result = build_query_result()
    use_case = RunLexicalQueryUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        index_build_store=FakeIndexBuildStore(build=build),
        chunk_store=FakeChunkStore(chunks=chunks),
        artifact_store=FakeArtifactStore(payloads=build_payloads(chunks)),
        lexical_query=FakeLexicalQueryEngine(result=query_result),
        formatter=RetrievalResultFormatter(preview_char_limit=80),
    )

    result = use_case.execute(
        RunLexicalQueryRequest(
            repository_id=repository.repository_id,
            query_text="bootValue",
        ),
    )

    assert result.repository.repository_id == repository.repository_id
    assert result.snapshot.snapshot_id == snapshot.snapshot_id
    assert result.build.build_id == build.build_id
    assert result.query.text == "bootValue"
    assert result.retrieval_mode == "lexical"
    assert [match.chunk_id for match in result.results] == ["chunk-1", "chunk-2"]
    assert result.results[0].content_preview == "export function bootValue() { return 'codeman'; }"
    assert "path src/Controller/[HomeController].php" in result.results[1].explanation
    assert use_case.lexical_query.initialized == [("build-123", "bootValue", 20)]
    assert result.diagnostics.match_count == 2
    assert result.diagnostics.query_latency_ms == 4
    assert result.diagnostics.total_match_count == 2
    assert result.diagnostics.truncated is False


def test_run_lexical_query_raises_when_repository_is_unknown(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    use_case = RunLexicalQueryUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=None),
        snapshot_store=FakeSnapshotStore(snapshot=None),
        index_build_store=FakeIndexBuildStore(build=None),
        chunk_store=FakeChunkStore(chunks=[]),
        artifact_store=FakeArtifactStore(payloads={}),
        lexical_query=FakeLexicalQueryEngine(result=build_query_result()),
        formatter=RetrievalResultFormatter(),
    )

    with pytest.raises(LexicalQueryRepositoryNotRegisteredError):
        use_case.execute(
            RunLexicalQueryRequest(
                repository_id="missing-repo",
                query_text="bootValue",
            ),
        )


def test_run_lexical_query_raises_when_current_lexical_build_is_missing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    repository = build_repository_record(repository_path.resolve())
    use_case = RunLexicalQueryUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=None),
        index_build_store=FakeIndexBuildStore(build=None),
        chunk_store=FakeChunkStore(chunks=[]),
        artifact_store=FakeArtifactStore(payloads={}),
        lexical_query=FakeLexicalQueryEngine(result=build_query_result()),
        formatter=RetrievalResultFormatter(),
    )

    with pytest.raises(LexicalBuildBaselineMissingError):
        use_case.execute(
            RunLexicalQueryRequest(
                repository_id=repository.repository_id,
                query_text="bootValue",
            ),
        )


def test_run_lexical_query_propagates_missing_artifact_failure(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    build = build_index_record(workspace, repository.repository_id)
    chunks = build_chunk_records(workspace)
    use_case = RunLexicalQueryUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        index_build_store=FakeIndexBuildStore(build=build),
        chunk_store=FakeChunkStore(chunks=chunks),
        artifact_store=FakeArtifactStore(payloads=build_payloads(chunks)),
        lexical_query=FakeLexicalQueryEngine(result=build_query_result()),
        formatter=RetrievalResultFormatter(),
    )

    with pytest.raises(LexicalArtifactMissingError):
        use_case.execute(
            RunLexicalQueryRequest(
                repository_id=repository.repository_id,
                query_text="bootValue",
            ),
        )


def test_run_lexical_query_wraps_unexpected_adapter_failures(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    build = build_index_record(workspace, repository.repository_id)
    build.index_path.parent.mkdir(parents=True, exist_ok=True)
    build.index_path.touch()
    chunks = build_chunk_records(workspace)
    use_case = RunLexicalQueryUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        index_build_store=FakeIndexBuildStore(build=build),
        chunk_store=FakeChunkStore(chunks=chunks),
        artifact_store=FakeArtifactStore(payloads=build_payloads(chunks)),
        lexical_query=FakeLexicalQueryEngine(error=RuntimeError("sqlite exploded")),
        formatter=RetrievalResultFormatter(),
    )

    with pytest.raises(LexicalQueryError):
        use_case.execute(
            RunLexicalQueryRequest(
                repository_id=repository.repository_id,
                query_text="bootValue",
            ),
        )


def test_run_lexical_query_raises_when_ranked_chunk_metadata_is_missing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    build = build_index_record(workspace, repository.repository_id)
    build.index_path.parent.mkdir(parents=True, exist_ok=True)
    build.index_path.touch()
    chunks = build_chunk_records(workspace)[:1]
    use_case = RunLexicalQueryUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        index_build_store=FakeIndexBuildStore(build=build),
        chunk_store=FakeChunkStore(chunks=chunks),
        artifact_store=FakeArtifactStore(payloads=build_payloads(chunks)),
        lexical_query=FakeLexicalQueryEngine(result=build_query_result()),
        formatter=RetrievalResultFormatter(),
    )

    with pytest.raises(LexicalQueryChunkMetadataMissingError):
        use_case.execute(
            RunLexicalQueryRequest(
                repository_id=repository.repository_id,
                query_text="bootValue",
            ),
        )


def test_run_lexical_query_raises_when_chunk_payload_is_missing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    build = build_index_record(workspace, repository.repository_id)
    build.index_path.parent.mkdir(parents=True, exist_ok=True)
    build.index_path.touch()
    chunks = build_chunk_records(workspace)
    payloads = build_payloads(chunks)
    payloads.pop(chunks[1].payload_path)
    use_case = RunLexicalQueryUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        index_build_store=FakeIndexBuildStore(build=build),
        chunk_store=FakeChunkStore(chunks=chunks),
        artifact_store=FakeArtifactStore(payloads=payloads),
        lexical_query=FakeLexicalQueryEngine(result=build_query_result()),
        formatter=RetrievalResultFormatter(),
    )

    with pytest.raises(LexicalQueryChunkPayloadMissingError):
        use_case.execute(
            RunLexicalQueryRequest(
                repository_id=repository.repository_id,
                query_text="bootValue",
            ),
        )

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codeman.application.query.run_lexical_query import (
    LexicalArtifactMissingError,
    LexicalBuildBaselineMissingError,
    LexicalQueryError,
    LexicalQueryRepositoryNotRegisteredError,
    RunLexicalQueryUseCase,
)
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
    initialized: list[tuple[str, str]] = field(default_factory=list)

    def query(
        self,
        *,
        build: LexicalIndexBuildRecord,
        query_text: str,
    ) -> LexicalQueryResult:
        self.initialized.append((build.build_id, query_text))
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
            ),
            LexicalQueryMatch(
                chunk_id="chunk-2",
                relative_path="src/Controller/HomeController.php",
                language="php",
                strategy="php_structure",
                score=-0.5,
                rank=2,
            ),
        ],
        diagnostics=LexicalQueryDiagnostics(
            match_count=2,
            query_latency_ms=4,
        ),
    )


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
    query_result = build_query_result()
    use_case = RunLexicalQueryUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        index_build_store=FakeIndexBuildStore(build=build),
        lexical_query=FakeLexicalQueryEngine(result=query_result),
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
    assert result.query == "bootValue"
    assert [match.chunk_id for match in result.matches] == ["chunk-1", "chunk-2"]
    assert result.diagnostics.match_count == 2
    assert result.diagnostics.query_latency_ms == 4


def test_run_lexical_query_raises_when_repository_is_unknown(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    use_case = RunLexicalQueryUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=None),
        snapshot_store=FakeSnapshotStore(snapshot=None),
        index_build_store=FakeIndexBuildStore(build=None),
        lexical_query=FakeLexicalQueryEngine(result=build_query_result()),
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
        lexical_query=FakeLexicalQueryEngine(result=build_query_result()),
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
    use_case = RunLexicalQueryUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        index_build_store=FakeIndexBuildStore(build=build),
        lexical_query=FakeLexicalQueryEngine(
            error=LexicalArtifactMissingError(
                f"Lexical artifact is missing for build: {build.build_id}",
            ),
        ),
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
    use_case = RunLexicalQueryUseCase(
        runtime_paths=runtime_paths,
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        index_build_store=FakeIndexBuildStore(build=build),
        lexical_query=FakeLexicalQueryEngine(error=RuntimeError("sqlite exploded")),
    )

    with pytest.raises(LexicalQueryError):
        use_case.execute(
            RunLexicalQueryRequest(
                repository_id=repository.repository_id,
                query_text="bootValue",
            ),
        )

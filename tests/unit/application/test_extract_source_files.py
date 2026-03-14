from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codeman.application.indexing.extract_source_files import (
    ExtractSourceFilesUseCase,
    SnapshotNotFoundError,
    SnapshotSourceMismatchError,
)
from codeman.application.ports.snapshot_port import ResolvedRevision
from codeman.application.ports.source_inventory_port import ScanSourceFilesResult
from codeman.contracts.repository import (
    ExtractSourceFilesRequest,
    RepositoryRecord,
    SnapshotRecord,
    SourceFileRecord,
)
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

    def initialize(self) -> None:
        self.initialized += 1

    def get_by_snapshot_id(self, snapshot_id: str) -> SnapshotRecord | None:
        if self.snapshot is None or self.snapshot.snapshot_id != snapshot_id:
            return None
        return self.snapshot


@dataclass
class FakeSourceInventoryStore:
    initialized: int = 0
    persisted: list[SourceFileRecord] | None = None

    def initialize(self) -> None:
        self.initialized += 1

    def upsert_source_files(
        self,
        source_files: tuple[SourceFileRecord, ...],
    ) -> list[SourceFileRecord]:
        self.persisted = list(source_files)
        return list(source_files)


@dataclass
class FakeRevisionResolver:
    revision: ResolvedRevision
    seen_paths: list[Path]

    def resolve(self, repository_path: Path) -> ResolvedRevision:
        self.seen_paths.append(repository_path)
        return self.revision


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
        self.seen_paths.append(repository_path)
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


def build_snapshot_record(repository_id: str, manifest_path: Path) -> SnapshotRecord:
    return SnapshotRecord(
        snapshot_id="snapshot-123",
        repository_id=repository_id,
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        manifest_path=manifest_path,
        created_at=datetime.now(UTC),
    )


def build_source_file_record(
    *,
    snapshot_id: str,
    repository_id: str,
    relative_path: str,
    language: str,
) -> SourceFileRecord:
    return SourceFileRecord(
        source_file_id=f"{snapshot_id}-{relative_path}",
        snapshot_id=snapshot_id,
        repository_id=repository_id,
        relative_path=relative_path,
        language=language,
        content_hash=f"hash-{relative_path}",
        byte_size=42,
        discovered_at=datetime.now(UTC),
    )


def test_extract_source_files_returns_persisted_inventory_and_diagnostics(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(
        repository.repository_id,
        workspace / ".codeman" / "artifacts" / "snapshots" / "snapshot-123" / "manifest.json",
    )
    scanner = FakeSourceScanner(
        result=ScanSourceFilesResult(
            source_files=(
                build_source_file_record(
                    snapshot_id=snapshot.snapshot_id,
                    repository_id=repository.repository_id,
                    relative_path="assets/app.js",
                    language="javascript",
                ),
                build_source_file_record(
                    snapshot_id=snapshot.snapshot_id,
                    repository_id=repository.repository_id,
                    relative_path="templates/page.html.twig",
                    language="twig",
                ),
            ),
            skipped_by_reason={"unsupported_extension": 1},
        ),
        seen_paths=[],
    )
    source_inventory_store = FakeSourceInventoryStore()
    revision_resolver = FakeRevisionResolver(
        revision=ResolvedRevision(
            identity=snapshot.revision_identity,
            source=snapshot.revision_source,
        ),
        seen_paths=[],
    )
    use_case = ExtractSourceFilesUseCase(
        runtime_paths=build_runtime_paths(workspace),
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        source_inventory_store=source_inventory_store,
        revision_resolver=revision_resolver,
        source_scanner=scanner,
    )

    result = use_case.execute(
        ExtractSourceFilesRequest(snapshot_id=snapshot.snapshot_id),
    )

    assert revision_resolver.seen_paths == [repository_path.resolve()]
    assert scanner.seen_paths == [repository_path.resolve()]
    assert source_inventory_store.persisted is not None
    assert result.diagnostics.persisted_total == 2
    assert result.diagnostics.persisted_by_language == {
        "javascript": 1,
        "twig": 1,
    }
    assert result.diagnostics.skipped_by_reason == {"unsupported_extension": 1}


def test_extract_source_files_rejects_unknown_snapshot(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    use_case = ExtractSourceFilesUseCase(
        runtime_paths=build_runtime_paths(workspace),
        repository_store=FakeRepositoryStore(repository=None),
        snapshot_store=FakeSnapshotStore(snapshot=None),
        source_inventory_store=FakeSourceInventoryStore(),
        revision_resolver=FakeRevisionResolver(
            revision=ResolvedRevision(identity="unused", source="git"),
            seen_paths=[],
        ),
        source_scanner=FakeSourceScanner(
            result=ScanSourceFilesResult(source_files=(), skipped_by_reason={}),
            seen_paths=[],
        ),
    )

    with pytest.raises(SnapshotNotFoundError):
        use_case.execute(ExtractSourceFilesRequest(snapshot_id="missing-snapshot"))


def test_extract_source_files_rejects_snapshot_source_mismatch(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(
        repository.repository_id,
        workspace / ".codeman" / "artifacts" / "snapshots" / "snapshot-123" / "manifest.json",
    )
    scanner = FakeSourceScanner(
        result=ScanSourceFilesResult(source_files=(), skipped_by_reason={}),
        seen_paths=[],
    )
    use_case = ExtractSourceFilesUseCase(
        runtime_paths=build_runtime_paths(workspace),
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=FakeSnapshotStore(snapshot=snapshot),
        source_inventory_store=FakeSourceInventoryStore(),
        revision_resolver=FakeRevisionResolver(
            revision=ResolvedRevision(identity="changed", source="filesystem_fingerprint"),
            seen_paths=[],
        ),
        source_scanner=scanner,
    )

    with pytest.raises(SnapshotSourceMismatchError):
        use_case.execute(ExtractSourceFilesRequest(snapshot_id=snapshot.snapshot_id))

    assert scanner.seen_paths == []

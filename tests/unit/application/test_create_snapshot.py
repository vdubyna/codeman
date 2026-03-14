from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codeman.application.ports.snapshot_port import ResolvedRevision
from codeman.application.repo.create_snapshot import (
    CreateSnapshotUseCase,
    RepositoryNotRegisteredError,
)
from codeman.contracts.repository import (
    CreateSnapshotRequest,
    RepositoryRecord,
    SnapshotManifestDocument,
    SnapshotRecord,
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
    initialized: int = 0
    created_snapshot: SnapshotRecord | None = None

    def initialize(self) -> None:
        self.initialized += 1

    def create_snapshot(
        self,
        *,
        snapshot_id: str,
        repository_id: str,
        revision_identity: str,
        revision_source: str,
        manifest_path: Path,
        created_at: datetime,
    ) -> SnapshotRecord:
        self.created_snapshot = SnapshotRecord(
            snapshot_id=snapshot_id,
            repository_id=repository_id,
            revision_identity=revision_identity,
            revision_source=revision_source,
            manifest_path=manifest_path,
            created_at=created_at,
        )
        return self.created_snapshot


@dataclass
class FakeRevisionResolver:
    revision: ResolvedRevision
    seen_paths: list[Path]

    def resolve(self, repository_path: Path) -> ResolvedRevision:
        self.seen_paths.append(repository_path)
        return self.revision


@dataclass
class FakeArtifactStore:
    runtime_root: Path
    manifest: SnapshotManifestDocument | None = None

    def write_snapshot_manifest(self, manifest: SnapshotManifestDocument) -> Path:
        self.manifest = manifest
        destination = (
            self.runtime_root / "artifacts" / "snapshots" / manifest.snapshot_id / "manifest.json"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return destination


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


def test_create_snapshot_returns_snapshot_and_manifest_for_registered_repository(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot_store = FakeSnapshotStore()
    artifact_store = FakeArtifactStore(runtime_root=workspace / ".codeman")
    revision_resolver = FakeRevisionResolver(
        revision=ResolvedRevision(identity="abc123", source="git"),
        seen_paths=[],
    )
    use_case = CreateSnapshotUseCase(
        runtime_paths=build_runtime_paths(workspace),
        repository_store=FakeRepositoryStore(repository=repository),
        snapshot_store=snapshot_store,
        revision_resolver=revision_resolver,
        artifact_store=artifact_store,
    )

    result = use_case.execute(CreateSnapshotRequest(repository_id=repository.repository_id))

    assert snapshot_store.initialized == 1
    assert revision_resolver.seen_paths == [repository_path.resolve()]
    assert result.repository.repository_id == repository.repository_id
    assert result.snapshot.repository_id == repository.repository_id
    assert result.snapshot.revision_identity == "abc123"
    assert result.snapshot.revision_source == "git"
    assert result.snapshot.manifest_path.exists()
    assert artifact_store.manifest is not None
    assert artifact_store.manifest.snapshot_id == result.snapshot.snapshot_id
    assert artifact_store.manifest.revision_source == "git"


def test_create_snapshot_rejects_unknown_repository_id(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    use_case = CreateSnapshotUseCase(
        runtime_paths=build_runtime_paths(workspace),
        repository_store=FakeRepositoryStore(repository=None),
        snapshot_store=FakeSnapshotStore(),
        revision_resolver=FakeRevisionResolver(
            revision=ResolvedRevision(identity="unused", source="git"),
            seen_paths=[],
        ),
        artifact_store=FakeArtifactStore(runtime_root=workspace / ".codeman"),
    )

    with pytest.raises(RepositoryNotRegisteredError):
        use_case.execute(CreateSnapshotRequest(repository_id="missing-repository"))

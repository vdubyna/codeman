"""Create immutable repository snapshots for later indexing and evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.application.ports.metadata_store_port import RepositoryMetadataStorePort
from codeman.application.ports.snapshot_port import (
    RevisionResolverPort,
    SnapshotMetadataStorePort,
)
from codeman.contracts.errors import ErrorCode
from codeman.contracts.repository import (
    CreateSnapshotRequest,
    CreateSnapshotResult,
    SnapshotManifestDocument,
)
from codeman.runtime import RuntimePaths, provision_runtime_paths


class CreateSnapshotError(Exception):
    """Base exception for snapshot creation failures."""

    exit_code = 25
    error_code = ErrorCode.SNAPSHOT_CREATION_FAILED

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RepositoryNotRegisteredError(CreateSnapshotError):
    """Raised when a snapshot is requested for an unknown repository."""

    exit_code = 24
    error_code = ErrorCode.REPOSITORY_NOT_REGISTERED


@dataclass(slots=True)
class CreateSnapshotUseCase:
    """Create immutable repository snapshots and their manifest artifacts."""

    runtime_paths: RuntimePaths
    repository_store: RepositoryMetadataStorePort
    snapshot_store: SnapshotMetadataStorePort
    revision_resolver: RevisionResolverPort
    artifact_store: ArtifactStorePort

    def execute(self, request: CreateSnapshotRequest) -> CreateSnapshotResult:
        """Create a repository snapshot using the registered repository metadata."""

        provision_runtime_paths(self.runtime_paths)
        self.snapshot_store.initialize()

        repository = self.repository_store.get_by_repository_id(request.repository_id)
        if repository is None:
            raise RepositoryNotRegisteredError(
                f"Repository is not registered: {request.repository_id}",
            )

        resolved_revision = self.revision_resolver.resolve(repository.canonical_path)
        created_at = datetime.now(UTC)
        snapshot_id = uuid4().hex
        manifest = SnapshotManifestDocument(
            snapshot_id=snapshot_id,
            repository_id=repository.repository_id,
            repository_name=repository.repository_name,
            canonical_path=repository.canonical_path,
            created_at=created_at,
            revision_identity=resolved_revision.identity,
            revision_source=resolved_revision.source,
        )

        manifest_path: Path | None = None
        try:
            manifest_path = self.artifact_store.write_snapshot_manifest(manifest)
            snapshot = self.snapshot_store.create_snapshot(
                snapshot_id=snapshot_id,
                repository_id=repository.repository_id,
                revision_identity=resolved_revision.identity,
                revision_source=resolved_revision.source,
                manifest_path=manifest_path,
                created_at=created_at,
            )
        except CreateSnapshotError:
            raise
        except Exception as exc:
            self._cleanup_manifest(manifest_path)
            raise CreateSnapshotError(
                f"Snapshot creation failed for repository: {repository.repository_id}",
            ) from exc

        return CreateSnapshotResult(repository=repository, snapshot=snapshot)

    @staticmethod
    def _cleanup_manifest(manifest_path: Path | None) -> None:
        """Remove a partially written manifest if later persistence fails."""

        if manifest_path is None or not manifest_path.exists():
            return

        manifest_path.unlink(missing_ok=True)
        parent = manifest_path.parent
        while parent.name and parent.name != "artifacts":
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

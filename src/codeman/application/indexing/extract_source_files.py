"""Extract supported source files from a registered snapshot."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from codeman.application.ports.metadata_store_port import RepositoryMetadataStorePort
from codeman.application.ports.snapshot_port import (
    ResolvedRevision,
    RevisionResolverPort,
    SnapshotMetadataStorePort,
)
from codeman.application.ports.source_inventory_port import (
    SourceInventoryStorePort,
    SourceScannerPort,
)
from codeman.contracts.errors import ErrorCode
from codeman.contracts.repository import (
    ExtractSourceFilesRequest,
    ExtractSourceFilesResult,
    SourceFileRecord,
    SourceInventoryDiagnostics,
)
from codeman.runtime import RuntimePaths, provision_runtime_paths


class ExtractSourceFilesError(Exception):
    """Base exception for source extraction failures."""

    exit_code = 28
    error_code = ErrorCode.SOURCE_EXTRACTION_FAILED

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class SnapshotNotFoundError(ExtractSourceFilesError):
    """Raised when extraction is requested for an unknown snapshot."""

    exit_code = 26
    error_code = ErrorCode.SNAPSHOT_NOT_FOUND


class SnapshotSourceMismatchError(ExtractSourceFilesError):
    """Raised when the live repository no longer matches the stored snapshot."""

    exit_code = 27
    error_code = ErrorCode.SNAPSHOT_SOURCE_MISMATCH


def _count_persisted_languages(source_files: list[SourceFileRecord]) -> dict[str, int]:
    """Build a stable per-language summary for extracted source files."""

    counts = Counter(record.language for record in source_files)
    return dict(sorted(counts.items()))


@dataclass(slots=True)
class ExtractSourceFilesUseCase:
    """Create a persisted source inventory from a previously captured snapshot."""

    runtime_paths: RuntimePaths
    repository_store: RepositoryMetadataStorePort
    snapshot_store: SnapshotMetadataStorePort
    source_inventory_store: SourceInventoryStorePort
    revision_resolver: RevisionResolverPort
    source_scanner: SourceScannerPort

    def execute(self, request: ExtractSourceFilesRequest) -> ExtractSourceFilesResult:
        """Validate the snapshot, scan supported files, and persist source metadata."""

        provision_runtime_paths(self.runtime_paths)
        self.snapshot_store.initialize()
        self.source_inventory_store.initialize()

        snapshot = self.snapshot_store.get_by_snapshot_id(request.snapshot_id)
        if snapshot is None:
            raise SnapshotNotFoundError(
                f"Snapshot is not registered: {request.snapshot_id}",
            )

        repository = self.repository_store.get_by_repository_id(snapshot.repository_id)
        if repository is None:
            raise ExtractSourceFilesError(
                f"Snapshot points to an unknown repository: {snapshot.repository_id}",
            )

        self._ensure_snapshot_matches_repository(
            snapshot_revision=ResolvedRevision(
                identity=snapshot.revision_identity,
                source=snapshot.revision_source,
            ),
            repository_path=repository.canonical_path,
            snapshot_id=snapshot.snapshot_id,
        )

        discovered_at = datetime.now(UTC)
        try:
            scan_result = self.source_scanner.scan(
                repository_path=repository.canonical_path,
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                discovered_at=discovered_at,
            )
            persisted_files = self.source_inventory_store.upsert_source_files(
                scan_result.source_files,
            )
        except ExtractSourceFilesError:
            raise
        except Exception as exc:
            raise ExtractSourceFilesError(
                f"Source extraction failed for snapshot: {snapshot.snapshot_id}",
            ) from exc

        diagnostics = SourceInventoryDiagnostics(
            persisted_by_language=_count_persisted_languages(persisted_files),
            skipped_by_reason=dict(sorted(scan_result.skipped_by_reason.items())),
            persisted_total=len(persisted_files),
            skipped_total=sum(scan_result.skipped_by_reason.values()),
        )
        return ExtractSourceFilesResult(
            repository=repository,
            snapshot=snapshot,
            source_files=persisted_files,
            diagnostics=diagnostics,
        )

    def _ensure_snapshot_matches_repository(
        self,
        *,
        snapshot_revision: ResolvedRevision,
        repository_path: Path,
        snapshot_id: str,
    ) -> None:
        """Fail safely if the live repository state diverges from the stored snapshot."""

        current_revision = self.revision_resolver.resolve(repository_path)
        if current_revision == snapshot_revision:
            return

        raise SnapshotSourceMismatchError(
            "Snapshot revision no longer matches the live repository state; "
            f"create a new snapshot before extracting sources: {snapshot_id}",
        )

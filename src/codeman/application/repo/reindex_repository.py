"""Re-index a repository using the latest indexed snapshot as a reusable baseline."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from codeman.application.indexing.chunk_materializer import ChunkMaterializer
from codeman.application.indexing.extract_source_files import ExtractSourceFilesUseCase
from codeman.application.ports.artifact_store_port import ArtifactStorePort
from codeman.application.ports.cache_store_port import CacheStorePort
from codeman.application.ports.chunk_store_port import ChunkStorePort
from codeman.application.ports.chunker_port import ChunkerRegistryPort
from codeman.application.ports.metadata_store_port import RepositoryMetadataStorePort
from codeman.application.ports.parser_port import ParserRegistryPort
from codeman.application.ports.reindex_run_store_port import ReindexRunStorePort
from codeman.application.ports.snapshot_port import (
    RevisionResolverPort,
    SnapshotMetadataStorePort,
)
from codeman.application.ports.source_inventory_port import (
    SourceInventoryStorePort,
    SourceScannerPort,
)
from codeman.application.provenance.record_run_provenance import (
    RecordRunConfigurationProvenanceUseCase,
)
from codeman.application.repo.create_snapshot import (
    CreateSnapshotRequest,
    CreateSnapshotUseCase,
)
from codeman.config.indexing import IndexingConfig, build_indexing_fingerprint
from codeman.contracts.cache import CacheUsageSummary
from codeman.contracts.configuration import (
    RecordRunConfigurationProvenanceRequest,
    RunProvenanceWorkflowContext,
)
from codeman.contracts.errors import ErrorCode
from codeman.contracts.reindexing import (
    ChangeReason,
    ReindexDiagnostics,
    ReindexRepositoryRequest,
    ReindexRepositoryResult,
)
from codeman.contracts.repository import ExtractSourceFilesRequest, SourceFileRecord
from codeman.infrastructure.snapshotting.local_repository_scanner import (
    classify_source_language,
    inspect_file,
)
from codeman.runtime import RuntimePaths, provision_runtime_paths


class ReindexRepositoryError(Exception):
    """Base exception for re-index failures."""

    exit_code = 31
    error_code = ErrorCode.REINDEX_FAILED

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class IndexedBaselineMissingError(ReindexRepositoryError):
    """Raised when a repository has no usable indexed baseline yet."""

    exit_code = 32
    error_code = ErrorCode.INDEXED_BASELINE_MISSING


class ReindexRepositoryNotRegisteredError(ReindexRepositoryError):
    """Raised when re-indexing is requested for an unknown repository."""

    exit_code = 24
    error_code = ErrorCode.REPOSITORY_NOT_REGISTERED


@dataclass(frozen=True, slots=True)
class InventoryDiff:
    """Normalized comparison between one baseline and one current inventory."""

    unchanged: tuple[SourceFileRecord, ...]
    added: tuple[SourceFileRecord, ...]
    changed: tuple[SourceFileRecord, ...]
    removed: tuple[SourceFileRecord, ...]
    newly_unsupported: tuple[SourceFileRecord, ...]


def classify_change_reason(
    *,
    source_changed: bool,
    config_changed: bool,
) -> ChangeReason:
    """Map source/config change booleans to one stable classification."""

    if source_changed and config_changed:
        return "source_and_config_changed"
    if source_changed:
        return "source_changed"
    if config_changed:
        return "config_changed"
    return "no_change"


def is_reusable_source_file(
    *,
    previous_source_file: SourceFileRecord,
    current_source_file: SourceFileRecord,
    previous_config_fingerprint: str,
    current_config_fingerprint: str,
) -> bool:
    """Return whether a baseline source file is safe for chunk reuse."""

    return (
        previous_source_file.relative_path == current_source_file.relative_path
        and previous_source_file.language == current_source_file.language
        and previous_source_file.content_hash == current_source_file.content_hash
        and previous_config_fingerprint == current_config_fingerprint
    )


def build_inventory_diff(
    *,
    baseline_source_files: list[SourceFileRecord],
    current_source_files: list[SourceFileRecord],
    repository_path: Path,
) -> InventoryDiff:
    """Compare baseline/current inventories using normalized path and content data."""

    baseline_by_path = {
        source_file.relative_path: source_file for source_file in baseline_source_files
    }
    current_by_path = {
        source_file.relative_path: source_file for source_file in current_source_files
    }
    unchanged: list[SourceFileRecord] = []
    added: list[SourceFileRecord] = []
    changed: list[SourceFileRecord] = []
    removed: list[SourceFileRecord] = []
    newly_unsupported: list[SourceFileRecord] = []

    for relative_path, current_source_file in sorted(current_by_path.items()):
        previous_source_file = baseline_by_path.get(relative_path)
        if previous_source_file is None:
            added.append(current_source_file)
            continue
        if (
            previous_source_file.language == current_source_file.language
            and previous_source_file.content_hash == current_source_file.content_hash
        ):
            unchanged.append(current_source_file)
            continue
        changed.append(current_source_file)

    for relative_path, previous_source_file in sorted(baseline_by_path.items()):
        if relative_path in current_by_path:
            continue
        if _is_now_unsupported(repository_path / relative_path, relative_path):
            newly_unsupported.append(previous_source_file)
            continue
        removed.append(previous_source_file)

    return InventoryDiff(
        unchanged=tuple(unchanged),
        added=tuple(added),
        changed=tuple(changed),
        removed=tuple(removed),
        newly_unsupported=tuple(newly_unsupported),
    )


def _is_now_unsupported(file_path: Path, relative_path: str) -> bool:
    """Return whether a previously indexed file still exists but is no longer supported."""

    if not file_path.exists() or file_path.is_dir():
        return False
    if file_path.is_symlink():
        return True

    try:
        inspection = inspect_file(file_path)
    except OSError:
        return True

    return inspection.is_binary or classify_source_language(relative_path) is None


def _merge_cache_summaries(*summaries: CacheUsageSummary) -> CacheUsageSummary:
    return CacheUsageSummary(
        parser_entries_reused=sum(summary.parser_entries_reused for summary in summaries),
        parser_entries_regenerated=sum(summary.parser_entries_regenerated for summary in summaries),
        chunk_entries_reused=sum(summary.chunk_entries_reused for summary in summaries),
        chunk_entries_regenerated=sum(summary.chunk_entries_regenerated for summary in summaries),
        embedding_documents_reused=sum(summary.embedding_documents_reused for summary in summaries),
        embedding_documents_regenerated=sum(
            summary.embedding_documents_regenerated for summary in summaries
        ),
    )


@dataclass(slots=True)
class ReindexRepositoryUseCase:
    """Create attributable re-index outcomes using a prior indexed baseline."""

    runtime_paths: RuntimePaths
    repository_store: RepositoryMetadataStorePort
    snapshot_store: SnapshotMetadataStorePort
    source_inventory_store: SourceInventoryStorePort
    source_scanner: SourceScannerPort
    chunk_store: ChunkStorePort
    reindex_run_store: ReindexRunStorePort
    revision_resolver: RevisionResolverPort
    create_snapshot: CreateSnapshotUseCase
    extract_source_files: ExtractSourceFilesUseCase
    parser_registry: ParserRegistryPort
    chunker_registry: ChunkerRegistryPort
    artifact_store: ArtifactStorePort
    cache_store: CacheStorePort
    indexing_config: IndexingConfig
    record_run_provenance: RecordRunConfigurationProvenanceUseCase | None = None

    def execute(self, request: ReindexRepositoryRequest) -> ReindexRepositoryResult:
        """Re-index a repository by reusing baseline artifacts whenever safe."""

        provision_runtime_paths(self.runtime_paths)
        self.repository_store.initialize()
        self.snapshot_store.initialize()
        self.source_inventory_store.initialize()
        self.chunk_store.initialize()
        self.reindex_run_store.initialize()

        repository = self.repository_store.get_by_repository_id(request.repository_id)
        if repository is None:
            raise ReindexRepositoryNotRegisteredError(
                f"Repository is not registered: {request.repository_id}",
            )

        baseline_snapshot = self.snapshot_store.get_latest_indexed_snapshot(
            repository.repository_id,
        )
        if baseline_snapshot is None:
            raise IndexedBaselineMissingError(
                "No indexed baseline exists yet for this repository; complete the initial "
                "`repo snapshot -> index extract-sources -> index build-chunks` flow first.",
            )

        baseline_source_files = self.source_inventory_store.list_by_snapshot(
            baseline_snapshot.snapshot_id,
        )
        baseline_chunks = self.chunk_store.list_by_snapshot(baseline_snapshot.snapshot_id)
        current_revision = self.revision_resolver.resolve(repository.canonical_path)
        current_config_fingerprint = build_indexing_fingerprint(self.indexing_config)
        previous_config_fingerprint = (
            baseline_snapshot.indexing_config_fingerprint or current_config_fingerprint
        )
        now = datetime.now(UTC)
        try:
            preview_scan = self.source_scanner.scan(
                repository_path=repository.canonical_path,
                snapshot_id="preview",
                repository_id=repository.repository_id,
                discovered_at=now,
            )
        except Exception as exc:
            raise ReindexRepositoryError(
                f"Re-index failed for repository: {request.repository_id}",
            ) from exc
        preview_source_files = list(preview_scan.source_files)
        preview_diff = build_inventory_diff(
            baseline_source_files=baseline_source_files,
            current_source_files=preview_source_files,
            repository_path=repository.canonical_path,
        )
        source_changed = bool(
            preview_diff.added
            or preview_diff.changed
            or preview_diff.removed
            or preview_diff.newly_unsupported
        )
        config_changed = current_config_fingerprint != previous_config_fingerprint
        change_reason = classify_change_reason(
            source_changed=source_changed,
            config_changed=config_changed,
        )

        if change_reason == "no_change":
            run_record = self.reindex_run_store.create_run(
                repository_id=repository.repository_id,
                previous_snapshot_id=baseline_snapshot.snapshot_id,
                result_snapshot_id=baseline_snapshot.snapshot_id,
                previous_revision_identity=baseline_snapshot.revision_identity,
                result_revision_identity=current_revision.identity,
                previous_config_fingerprint=previous_config_fingerprint,
                current_config_fingerprint=current_config_fingerprint,
                change_reason="no_change",
                source_files_reused=len(preview_diff.unchanged),
                source_files_rebuilt=0,
                source_files_removed=0,
                chunks_reused=len(baseline_chunks),
                chunks_rebuilt=0,
                created_at=now,
            )
            diagnostics = ReindexDiagnostics(
                source_files_scanned=len(preview_source_files),
                source_files_skipped=sum(preview_scan.skipped_by_reason.values()),
                source_files_unchanged=len(preview_diff.unchanged),
                source_files_reused=len(preview_diff.unchanged),
                chunks_reused=len(baseline_chunks),
                cache_summary=CacheUsageSummary(),
            )
            if self.record_run_provenance is not None:
                self.record_run_provenance.execute(
                    RecordRunConfigurationProvenanceRequest(
                        run_id=run_record.run_id,
                        workflow_type="index.reindex",
                        repository_id=repository.repository_id,
                        snapshot_id=baseline_snapshot.snapshot_id,
                        indexing_config_fingerprint=current_config_fingerprint,
                        workflow_context=RunProvenanceWorkflowContext(
                            previous_snapshot_id=baseline_snapshot.snapshot_id,
                            result_snapshot_id=baseline_snapshot.snapshot_id,
                            noop=True,
                            source_files_reused=len(preview_diff.unchanged),
                            source_files_rebuilt=0,
                            source_files_removed=0,
                            chunks_reused=len(baseline_chunks),
                            chunks_rebuilt=0,
                            chunks_removed=0,
                            cache_summary=diagnostics.cache_summary,
                        ),
                    )
                )
            return ReindexRepositoryResult(
                run_id=run_record.run_id,
                repository=repository,
                previous_snapshot_id=baseline_snapshot.snapshot_id,
                result_snapshot_id=baseline_snapshot.snapshot_id,
                change_reason="no_change",
                previous_revision_identity=baseline_snapshot.revision_identity,
                result_revision_identity=current_revision.identity,
                previous_config_fingerprint=previous_config_fingerprint,
                current_config_fingerprint=current_config_fingerprint,
                source_files_reused=len(preview_diff.unchanged),
                source_files_rebuilt=0,
                source_files_removed=0,
                chunks_reused=len(baseline_chunks),
                chunks_rebuilt=0,
                noop=True,
                diagnostics=diagnostics,
            )

        try:
            snapshot_result = self.create_snapshot.execute(
                CreateSnapshotRequest(repository_id=repository.repository_id),
            )
            extract_result = self.extract_source_files.execute(
                ExtractSourceFilesRequest(snapshot_id=snapshot_result.snapshot.snapshot_id),
            )
        except ReindexRepositoryError:
            raise
        except Exception as exc:
            raise ReindexRepositoryError(
                f"Re-index failed for repository: {request.repository_id}",
            ) from exc

        current_snapshot = snapshot_result.snapshot
        current_source_files = list(extract_result.source_files)
        diff = build_inventory_diff(
            baseline_source_files=baseline_source_files,
            current_source_files=current_source_files,
            repository_path=repository.canonical_path,
        )

        materializer = ChunkMaterializer(
            parser_registry=self.parser_registry,
            chunker_registry=self.chunker_registry,
            artifact_store=self.artifact_store,
            cache_store=self.cache_store,
        )
        baseline_by_path = {
            source_file.relative_path: source_file for source_file in baseline_source_files
        }
        baseline_chunks_by_path: dict[str, list] = defaultdict(list)
        for chunk in baseline_chunks:
            baseline_chunks_by_path[chunk.relative_path].append(chunk)

        reused_chunks: list = []
        built_chunks: list = []
        cache_summaries: list[CacheUsageSummary] = []
        reused_files = 0
        rebuilt_files = 0
        reused_chunk_count = 0
        files_to_build: list[SourceFileRecord]

        if config_changed:
            files_to_build = sorted(
                current_source_files,
                key=lambda source_file: source_file.relative_path,
            )
        else:
            files_to_build = sorted(
                [*diff.added, *diff.changed],
                key=lambda source_file: source_file.relative_path,
            )
            for current_source_file in diff.unchanged:
                previous_source_file = baseline_by_path[current_source_file.relative_path]
                if not is_reusable_source_file(
                    previous_source_file=previous_source_file,
                    current_source_file=current_source_file,
                    previous_config_fingerprint=previous_config_fingerprint,
                    current_config_fingerprint=current_config_fingerprint,
                ):
                    files_to_build.append(current_source_file)
                    continue
                try:
                    cloned_chunks = materializer.clone_for_source_file(
                        source_file=current_source_file,
                        baseline_chunks=baseline_chunks_by_path.get(
                            current_source_file.relative_path,
                            [],
                        ),
                        created_at=now,
                    )
                except Exception:
                    files_to_build.append(current_source_file)
                    continue
                reused_chunks.extend(cloned_chunks)
                reused_files += 1
                reused_chunk_count += len(cloned_chunks)

        try:
            for source_file in files_to_build:
                source_result = materializer.build_for_source_file(
                    source_file=source_file,
                    repository_path=repository.canonical_path,
                    created_at=now,
                    indexing_config_fingerprint=current_config_fingerprint,
                )
                built_chunks.extend(source_result.chunk_records)
                cache_summaries.append(source_result.cache_summary)
                rebuilt_files += 1
            self.chunk_store.upsert_chunks([*reused_chunks, *built_chunks])
            self.snapshot_store.mark_chunks_generated(
                snapshot_id=current_snapshot.snapshot_id,
                generated_at=now,
                indexing_config_fingerprint=current_config_fingerprint,
            )
        except ReindexRepositoryError:
            raise
        except Exception as exc:
            raise ReindexRepositoryError(
                f"Re-index failed for repository: {request.repository_id}",
            ) from exc

        removed_paths = {
            source_file.relative_path for source_file in diff.removed + diff.newly_unsupported
        }
        chunks_removed = sum(
            len(baseline_chunks_by_path.get(relative_path, []))
            for relative_path in sorted(removed_paths)
        )
        invalidated_paths = {
            relative_path
            for relative_path in baseline_by_path
            if relative_path not in removed_paths
        }
        chunks_invalidated_by_config = 0
        if config_changed:
            chunks_invalidated_by_config = sum(
                len(baseline_chunks_by_path.get(relative_path, []))
                for relative_path in sorted(invalidated_paths)
            )

        run_record = self.reindex_run_store.create_run(
            repository_id=repository.repository_id,
            previous_snapshot_id=baseline_snapshot.snapshot_id,
            result_snapshot_id=current_snapshot.snapshot_id,
            previous_revision_identity=baseline_snapshot.revision_identity,
            result_revision_identity=current_snapshot.revision_identity,
            previous_config_fingerprint=previous_config_fingerprint,
            current_config_fingerprint=current_config_fingerprint,
            change_reason=change_reason,
            source_files_reused=reused_files,
            source_files_rebuilt=rebuilt_files,
            source_files_removed=len(diff.removed) + len(diff.newly_unsupported),
            chunks_reused=reused_chunk_count,
            chunks_rebuilt=len(built_chunks),
            created_at=now,
        )
        diagnostics = ReindexDiagnostics(
            source_files_scanned=len(current_source_files),
            source_files_skipped=extract_result.diagnostics.skipped_total,
            source_files_unchanged=len(diff.unchanged),
            source_files_added=len(diff.added),
            source_files_changed=len(diff.changed),
            source_files_reused=reused_files,
            source_files_rebuilt=rebuilt_files,
            source_files_removed=len(diff.removed),
            source_files_newly_unsupported=len(diff.newly_unsupported),
            source_files_invalidated_by_config=len(current_source_files) if config_changed else 0,
            chunks_reused=reused_chunk_count,
            chunks_rebuilt=len(built_chunks),
            chunks_removed=chunks_removed,
            chunks_invalidated_by_config=chunks_invalidated_by_config,
            cache_summary=_merge_cache_summaries(*cache_summaries),
        )
        if self.record_run_provenance is not None:
            self.record_run_provenance.execute(
                RecordRunConfigurationProvenanceRequest(
                    run_id=run_record.run_id,
                    workflow_type="index.reindex",
                    repository_id=repository.repository_id,
                    snapshot_id=current_snapshot.snapshot_id,
                    indexing_config_fingerprint=current_config_fingerprint,
                    workflow_context=RunProvenanceWorkflowContext(
                        previous_snapshot_id=baseline_snapshot.snapshot_id,
                        result_snapshot_id=current_snapshot.snapshot_id,
                        noop=False,
                        source_files_reused=reused_files,
                        source_files_rebuilt=rebuilt_files,
                        source_files_removed=len(diff.removed) + len(diff.newly_unsupported),
                        chunks_reused=reused_chunk_count,
                        chunks_rebuilt=len(built_chunks),
                        chunks_removed=chunks_removed,
                        cache_summary=diagnostics.cache_summary,
                    ),
                )
            )
        return ReindexRepositoryResult(
            run_id=run_record.run_id,
            repository=repository,
            previous_snapshot_id=baseline_snapshot.snapshot_id,
            result_snapshot_id=current_snapshot.snapshot_id,
            change_reason=change_reason,
            previous_revision_identity=baseline_snapshot.revision_identity,
            result_revision_identity=current_snapshot.revision_identity,
            previous_config_fingerprint=previous_config_fingerprint,
            current_config_fingerprint=current_config_fingerprint,
            source_files_reused=reused_files,
            source_files_rebuilt=rebuilt_files,
            source_files_removed=len(diff.removed) + len(diff.newly_unsupported),
            chunks_reused=reused_chunk_count,
            chunks_rebuilt=len(built_chunks),
            noop=False,
            diagnostics=diagnostics,
        )

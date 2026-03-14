"""Composition root for CLI and tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codeman.application.indexing.extract_source_files import ExtractSourceFilesUseCase
from codeman.application.repo.create_snapshot import CreateSnapshotUseCase
from codeman.application.repo.register_repository import RegisterRepositoryUseCase
from codeman.config.models import AppConfig
from codeman.infrastructure.artifacts.filesystem_artifact_store import (
    FilesystemArtifactStore,
)
from codeman.infrastructure.persistence.sqlite.engine import create_sqlite_engine
from codeman.infrastructure.persistence.sqlite.repositories.repository_repository import (
    SqliteRepositoryMetadataStore,
)
from codeman.infrastructure.persistence.sqlite.repositories.snapshot_repository import (
    SqliteSnapshotMetadataStore,
)
from codeman.infrastructure.persistence.sqlite.repositories.source_file_repository import (
    SqliteSourceInventoryStore,
)
from codeman.infrastructure.snapshotting.git_revision_resolver import GitRevisionResolver
from codeman.infrastructure.snapshotting.local_repository_scanner import (
    LocalRepositoryScanner,
)
from codeman.runtime import RuntimePaths, build_runtime_paths


@dataclass(slots=True)
class BootstrapContainer:
    """Minimal container shared by CLI entrypoints and tests."""

    config: AppConfig
    runtime_paths: RuntimePaths
    metadata_store: SqliteRepositoryMetadataStore
    snapshot_store: SqliteSnapshotMetadataStore
    source_inventory_store: SqliteSourceInventoryStore
    register_repository: RegisterRepositoryUseCase
    create_snapshot: CreateSnapshotUseCase
    extract_source_files: ExtractSourceFilesUseCase


def bootstrap(workspace_root: Path | None = None) -> BootstrapContainer:
    """Build the minimal container required by the current scaffold."""

    config = AppConfig()
    if workspace_root is not None:
        config.runtime.workspace_root = workspace_root.resolve()

    selected_workspace = config.runtime.workspace_root
    runtime_paths = build_runtime_paths(
        workspace_root=selected_workspace,
        root_dir_name=config.runtime.root_dir_name,
        metadata_database_name=config.runtime.metadata_database_name,
    )
    metadata_store = SqliteRepositoryMetadataStore(
        engine=create_sqlite_engine(runtime_paths.metadata_database_path),
        database_path=runtime_paths.metadata_database_path,
    )
    snapshot_engine = create_sqlite_engine(runtime_paths.metadata_database_path)
    snapshot_store = SqliteSnapshotMetadataStore(
        engine=snapshot_engine,
        database_path=runtime_paths.metadata_database_path,
    )
    source_inventory_store = SqliteSourceInventoryStore(
        engine=snapshot_engine,
        database_path=runtime_paths.metadata_database_path,
    )
    revision_resolver = GitRevisionResolver()
    register_repository = RegisterRepositoryUseCase(
        runtime_paths=runtime_paths,
        metadata_store=metadata_store,
    )
    create_snapshot = CreateSnapshotUseCase(
        runtime_paths=runtime_paths,
        repository_store=metadata_store,
        snapshot_store=snapshot_store,
        revision_resolver=revision_resolver,
        artifact_store=FilesystemArtifactStore(runtime_paths.artifacts),
    )
    extract_source_files = ExtractSourceFilesUseCase(
        runtime_paths=runtime_paths,
        repository_store=metadata_store,
        snapshot_store=snapshot_store,
        source_inventory_store=source_inventory_store,
        revision_resolver=revision_resolver,
        source_scanner=LocalRepositoryScanner(),
    )
    return BootstrapContainer(
        config=config,
        runtime_paths=runtime_paths,
        metadata_store=metadata_store,
        snapshot_store=snapshot_store,
        source_inventory_store=source_inventory_store,
        register_repository=register_repository,
        create_snapshot=create_snapshot,
        extract_source_files=extract_source_files,
    )

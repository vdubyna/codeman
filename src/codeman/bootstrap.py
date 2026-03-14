"""Composition root for CLI and tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from codeman.application.indexing.build_chunks import BuildChunksUseCase
from codeman.application.indexing.build_embeddings import BuildEmbeddingsStage
from codeman.application.indexing.build_lexical_index import BuildLexicalIndexUseCase
from codeman.application.indexing.build_semantic_index import BuildSemanticIndexUseCase
from codeman.application.indexing.build_vector_index import BuildVectorIndexStage
from codeman.application.indexing.extract_source_files import ExtractSourceFilesUseCase
from codeman.application.query.compare_retrieval_modes import CompareRetrievalModesUseCase
from codeman.application.query.format_results import RetrievalResultFormatter
from codeman.application.query.run_hybrid_query import RunHybridQueryUseCase
from codeman.application.query.run_lexical_query import RunLexicalQueryUseCase
from codeman.application.query.run_semantic_query import RunSemanticQueryUseCase
from codeman.application.repo.create_snapshot import CreateSnapshotUseCase
from codeman.application.repo.register_repository import RegisterRepositoryUseCase
from codeman.application.repo.reindex_repository import ReindexRepositoryUseCase
from codeman.config.loader import ConfigOverrides, load_app_config
from codeman.config.models import AppConfig
from codeman.infrastructure.artifacts.filesystem_artifact_store import (
    FilesystemArtifactStore,
)
from codeman.infrastructure.chunkers.chunker_registry import ChunkerRegistry
from codeman.infrastructure.embeddings.local_hash_provider import (
    DeterministicLocalHashEmbeddingProvider,
)
from codeman.infrastructure.indexes.lexical.sqlite_fts5_builder import (
    SqliteFts5LexicalIndexBuilder,
)
from codeman.infrastructure.indexes.lexical.sqlite_fts5_query_engine import (
    SqliteFts5LexicalQueryEngine,
)
from codeman.infrastructure.indexes.vector.sqlite_exact_builder import (
    SqliteExactVectorIndexBuilder,
)
from codeman.infrastructure.indexes.vector.sqlite_exact_query_engine import (
    SqliteExactVectorQueryEngine,
)
from codeman.infrastructure.parsers.parser_registry import ParserRegistry
from codeman.infrastructure.persistence.sqlite.engine import create_sqlite_engine
from codeman.infrastructure.persistence.sqlite.repositories.chunk_repository import (
    SqliteChunkStore,
)
from codeman.infrastructure.persistence.sqlite.repositories.index_build_repository import (
    SqliteIndexBuildStore,
)
from codeman.infrastructure.persistence.sqlite.repositories.reindex_run_repository import (
    SqliteReindexRunStore,
)
from codeman.infrastructure.persistence.sqlite.repositories.repository_repository import (
    SqliteRepositoryMetadataStore,
)
from codeman.infrastructure.persistence.sqlite.repositories.semantic_index_build_repository import (
    SqliteSemanticIndexBuildStore,
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
    chunk_store: SqliteChunkStore
    index_build_store: SqliteIndexBuildStore
    semantic_index_build_store: SqliteSemanticIndexBuildStore
    register_repository: RegisterRepositoryUseCase
    create_snapshot: CreateSnapshotUseCase
    extract_source_files: ExtractSourceFilesUseCase
    build_chunks: BuildChunksUseCase
    build_lexical_index: BuildLexicalIndexUseCase
    build_semantic_index: BuildSemanticIndexUseCase
    run_lexical_query: RunLexicalQueryUseCase
    run_semantic_query: RunSemanticQueryUseCase
    run_hybrid_query: RunHybridQueryUseCase
    compare_retrieval_modes: CompareRetrievalModesUseCase
    reindex_repository: ReindexRepositoryUseCase


def bootstrap(
    workspace_root: Path | None = None,
    *,
    cli_overrides: ConfigOverrides | None = None,
    allow_missing_local_config: bool = True,
    environ: Mapping[str, str] | None = None,
) -> BootstrapContainer:
    """Build the minimal container required by the current scaffold."""

    resolved_overrides = cli_overrides or ConfigOverrides()
    if workspace_root is not None:
        resolved_overrides = replace(
            resolved_overrides,
            workspace_root=workspace_root.resolve(),
        )

    config = load_app_config(
        cli_overrides=resolved_overrides,
        allow_missing_local_config=allow_missing_local_config,
        environ=environ,
    )

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
    chunk_store = SqliteChunkStore(
        engine=snapshot_engine,
        database_path=runtime_paths.metadata_database_path,
    )
    index_build_store = SqliteIndexBuildStore(
        engine=snapshot_engine,
        database_path=runtime_paths.metadata_database_path,
    )
    semantic_index_build_store = SqliteSemanticIndexBuildStore(
        engine=snapshot_engine,
        database_path=runtime_paths.metadata_database_path,
    )
    reindex_run_store = SqliteReindexRunStore(
        engine=snapshot_engine,
        database_path=runtime_paths.metadata_database_path,
    )
    revision_resolver = GitRevisionResolver()
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    source_scanner = LocalRepositoryScanner()
    register_repository = RegisterRepositoryUseCase(
        runtime_paths=runtime_paths,
        metadata_store=metadata_store,
    )
    create_snapshot = CreateSnapshotUseCase(
        runtime_paths=runtime_paths,
        repository_store=metadata_store,
        snapshot_store=snapshot_store,
        revision_resolver=revision_resolver,
        artifact_store=artifact_store,
    )
    extract_source_files = ExtractSourceFilesUseCase(
        runtime_paths=runtime_paths,
        repository_store=metadata_store,
        snapshot_store=snapshot_store,
        source_inventory_store=source_inventory_store,
        revision_resolver=revision_resolver,
        source_scanner=source_scanner,
    )
    build_chunks = BuildChunksUseCase(
        runtime_paths=runtime_paths,
        repository_store=metadata_store,
        snapshot_store=snapshot_store,
        source_inventory_store=source_inventory_store,
        chunk_store=chunk_store,
        revision_resolver=revision_resolver,
        parser_registry=ParserRegistry(),
        chunker_registry=ChunkerRegistry(),
        artifact_store=artifact_store,
        indexing_config=config.indexing,
    )
    build_lexical_index = BuildLexicalIndexUseCase(
        runtime_paths=runtime_paths,
        repository_store=metadata_store,
        snapshot_store=snapshot_store,
        chunk_store=chunk_store,
        artifact_store=artifact_store,
        lexical_index=SqliteFts5LexicalIndexBuilder(runtime_paths=runtime_paths),
        index_build_store=index_build_store,
        indexing_config=config.indexing,
    )
    build_semantic_index = BuildSemanticIndexUseCase(
        runtime_paths=runtime_paths,
        repository_store=metadata_store,
        snapshot_store=snapshot_store,
        chunk_store=chunk_store,
        artifact_store=artifact_store,
        embedding_stage=BuildEmbeddingsStage(
            artifact_store=artifact_store,
            embedding_provider=DeterministicLocalHashEmbeddingProvider(),
            semantic_indexing_config=config.semantic_indexing,
            embedding_providers_config=config.embedding_providers,
        ),
        vector_index_stage=BuildVectorIndexStage(
            vector_index=SqliteExactVectorIndexBuilder(runtime_paths=runtime_paths),
            semantic_indexing_config=config.semantic_indexing,
        ),
        semantic_index_build_store=semantic_index_build_store,
        semantic_indexing_config=config.semantic_indexing,
        embedding_providers_config=config.embedding_providers,
    )
    run_lexical_query = RunLexicalQueryUseCase(
        runtime_paths=runtime_paths,
        repository_store=metadata_store,
        snapshot_store=snapshot_store,
        index_build_store=index_build_store,
        chunk_store=chunk_store,
        artifact_store=artifact_store,
        lexical_query=SqliteFts5LexicalQueryEngine(),
        formatter=RetrievalResultFormatter(),
    )
    run_semantic_query = RunSemanticQueryUseCase(
        runtime_paths=runtime_paths,
        repository_store=metadata_store,
        snapshot_store=snapshot_store,
        semantic_index_build_store=semantic_index_build_store,
        chunk_store=chunk_store,
        artifact_store=artifact_store,
        embedding_provider=DeterministicLocalHashEmbeddingProvider(),
        semantic_query=SqliteExactVectorQueryEngine(),
        formatter=RetrievalResultFormatter(),
        semantic_indexing_config=config.semantic_indexing,
        embedding_providers_config=config.embedding_providers,
    )
    run_hybrid_query = RunHybridQueryUseCase(
        run_lexical_query=run_lexical_query,
        run_semantic_query=run_semantic_query,
        formatter=RetrievalResultFormatter(),
    )
    compare_retrieval_modes = CompareRetrievalModesUseCase(
        run_lexical_query=run_lexical_query,
        run_semantic_query=run_semantic_query,
        formatter=RetrievalResultFormatter(),
    )
    reindex_repository = ReindexRepositoryUseCase(
        runtime_paths=runtime_paths,
        repository_store=metadata_store,
        snapshot_store=snapshot_store,
        source_inventory_store=source_inventory_store,
        source_scanner=source_scanner,
        chunk_store=chunk_store,
        reindex_run_store=reindex_run_store,
        revision_resolver=revision_resolver,
        create_snapshot=create_snapshot,
        extract_source_files=extract_source_files,
        parser_registry=ParserRegistry(),
        chunker_registry=ChunkerRegistry(),
        artifact_store=artifact_store,
        indexing_config=config.indexing,
    )
    return BootstrapContainer(
        config=config,
        runtime_paths=runtime_paths,
        metadata_store=metadata_store,
        snapshot_store=snapshot_store,
        source_inventory_store=source_inventory_store,
        chunk_store=chunk_store,
        index_build_store=index_build_store,
        semantic_index_build_store=semantic_index_build_store,
        register_repository=register_repository,
        create_snapshot=create_snapshot,
        extract_source_files=extract_source_files,
        build_chunks=build_chunks,
        build_lexical_index=build_lexical_index,
        build_semantic_index=build_semantic_index,
        run_lexical_query=run_lexical_query,
        run_semantic_query=run_semantic_query,
        run_hybrid_query=run_hybrid_query,
        compare_retrieval_modes=compare_retrieval_modes,
        reindex_repository=reindex_repository,
    )

"""Composition root for CLI and tests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from codeman.application.config.list_retrieval_strategy_profiles import (
    ListRetrievalStrategyProfilesUseCase,
)
from codeman.application.config.retrieval_profile_selection import (
    resolve_retrieval_strategy_profile_selector,
)
from codeman.application.config.save_retrieval_strategy_profile import (
    SaveRetrievalStrategyProfileUseCase,
)
from codeman.application.config.show_retrieval_strategy_profile import (
    ShowRetrievalStrategyProfileUseCase,
)
from codeman.application.indexing.build_chunks import BuildChunksUseCase
from codeman.application.indexing.build_embeddings import BuildEmbeddingsStage
from codeman.application.indexing.build_lexical_index import BuildLexicalIndexUseCase
from codeman.application.indexing.build_semantic_index import BuildSemanticIndexUseCase
from codeman.application.indexing.build_vector_index import BuildVectorIndexStage
from codeman.application.indexing.extract_source_files import ExtractSourceFilesUseCase
from codeman.application.provenance.record_run_provenance import (
    RecordRunConfigurationProvenanceUseCase,
)
from codeman.application.provenance.show_run_provenance import (
    ShowRunConfigurationProvenanceUseCase,
)
from codeman.application.query.compare_retrieval_modes import CompareRetrievalModesUseCase
from codeman.application.query.format_results import RetrievalResultFormatter
from codeman.application.query.run_hybrid_query import RunHybridQueryUseCase
from codeman.application.query.run_lexical_query import RunLexicalQueryUseCase
from codeman.application.query.run_semantic_query import RunSemanticQueryUseCase
from codeman.application.repo.create_snapshot import CreateSnapshotUseCase
from codeman.application.repo.register_repository import RegisterRepositoryUseCase
from codeman.application.repo.reindex_repository import ReindexRepositoryUseCase
from codeman.config.loader import ConfigOverrides, ConfigurationResolutionError, load_app_config
from codeman.config.models import AppConfig
from codeman.config.retrieval_profiles import normalize_retrieval_profile_selector
from codeman.contracts.configuration import RetrievalStrategyProfileRecord
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
from codeman.infrastructure.persistence.sqlite.repositories.retrieval_profile_repository import (
    SqliteRetrievalStrategyProfileStore,
)
from codeman.infrastructure.persistence.sqlite.repositories.run_provenance_repository import (
    SqliteRunProvenanceStore,
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
    selected_profile: RetrievalStrategyProfileRecord | None
    runtime_paths: RuntimePaths
    metadata_store: SqliteRepositoryMetadataStore
    snapshot_store: SqliteSnapshotMetadataStore
    source_inventory_store: SqliteSourceInventoryStore
    chunk_store: SqliteChunkStore
    index_build_store: SqliteIndexBuildStore
    semantic_index_build_store: SqliteSemanticIndexBuildStore
    retrieval_profile_store: SqliteRetrievalStrategyProfileStore
    run_provenance_store: SqliteRunProvenanceStore
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
    save_retrieval_strategy_profile: SaveRetrievalStrategyProfileUseCase
    list_retrieval_strategy_profiles: ListRetrievalStrategyProfilesUseCase
    show_retrieval_strategy_profile: ShowRetrievalStrategyProfileUseCase
    record_run_provenance: RecordRunConfigurationProvenanceUseCase
    show_run_provenance: ShowRunConfigurationProvenanceUseCase


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

    selected_profile: RetrievalStrategyProfileRecord | None = None
    if resolved_overrides.profile is not None:
        try:
            normalized_profile_selector = normalize_retrieval_profile_selector(
                resolved_overrides.profile,
                field_name="selector",
            )
        except ValueError as exc:
            raise ConfigurationResolutionError(str(exc)) from exc

        base_config = load_app_config(
            cli_overrides=replace(resolved_overrides, profile=None),
            allow_missing_local_config=allow_missing_local_config,
            environ=environ,
        )
        base_runtime_paths = build_runtime_paths(
            workspace_root=base_config.runtime.workspace_root,
            root_dir_name=base_config.runtime.root_dir_name,
            metadata_database_name=base_config.runtime.metadata_database_name,
        )
        selection_store = SqliteRetrievalStrategyProfileStore(
            engine=create_sqlite_engine(base_runtime_paths.metadata_database_path),
            database_path=base_runtime_paths.metadata_database_path,
        )
        selected_profile = resolve_retrieval_strategy_profile_selector(
            selection_store,
            normalized_profile_selector,
        )
        config = load_app_config(
            cli_overrides=replace(resolved_overrides, profile=normalized_profile_selector),
            selected_profile_payload=selected_profile.payload.to_loader_payload(),
            allow_missing_local_config=allow_missing_local_config,
            environ=environ,
        )
    else:
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
    retrieval_profile_store = SqliteRetrievalStrategyProfileStore(
        engine=snapshot_engine,
        database_path=runtime_paths.metadata_database_path,
    )
    run_provenance_store = SqliteRunProvenanceStore(
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
    record_run_provenance = RecordRunConfigurationProvenanceUseCase(
        config=config,
        provenance_store=run_provenance_store,
        selected_profile=selected_profile,
    )
    show_run_provenance = ShowRunConfigurationProvenanceUseCase(
        provenance_store=run_provenance_store,
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
        record_run_provenance=record_run_provenance,
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
        record_run_provenance=record_run_provenance,
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
        record_run_provenance=record_run_provenance,
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
        indexing_config=config.indexing,
        record_run_provenance=record_run_provenance,
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
        record_run_provenance=record_run_provenance,
    )
    run_hybrid_query = RunHybridQueryUseCase(
        run_lexical_query=run_lexical_query,
        run_semantic_query=run_semantic_query,
        record_run_provenance=record_run_provenance,
        formatter=RetrievalResultFormatter(),
    )
    compare_retrieval_modes = CompareRetrievalModesUseCase(
        run_lexical_query=run_lexical_query,
        run_semantic_query=run_semantic_query,
        record_run_provenance=record_run_provenance,
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
        record_run_provenance=record_run_provenance,
    )
    save_retrieval_strategy_profile = SaveRetrievalStrategyProfileUseCase(
        config=config,
        profile_store=retrieval_profile_store,
    )
    list_retrieval_strategy_profiles = ListRetrievalStrategyProfilesUseCase(
        profile_store=retrieval_profile_store,
    )
    show_retrieval_strategy_profile = ShowRetrievalStrategyProfileUseCase(
        profile_store=retrieval_profile_store,
    )
    return BootstrapContainer(
        config=config,
        selected_profile=selected_profile,
        runtime_paths=runtime_paths,
        metadata_store=metadata_store,
        snapshot_store=snapshot_store,
        source_inventory_store=source_inventory_store,
        chunk_store=chunk_store,
        index_build_store=index_build_store,
        semantic_index_build_store=semantic_index_build_store,
        retrieval_profile_store=retrieval_profile_store,
        run_provenance_store=run_provenance_store,
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
        save_retrieval_strategy_profile=save_retrieval_strategy_profile,
        list_retrieval_strategy_profiles=list_retrieval_strategy_profiles,
        show_retrieval_strategy_profile=show_retrieval_strategy_profile,
        record_run_provenance=record_run_provenance,
        show_run_provenance=show_run_provenance,
    )

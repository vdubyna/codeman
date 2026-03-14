from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from codeman.application.query.run_hybrid_query import HybridSnapshotMismatchError
from codeman.bootstrap import bootstrap
from codeman.config.semantic_indexing import build_semantic_indexing_fingerprint
from codeman.contracts.chunking import BuildChunksRequest
from codeman.contracts.reindexing import ReindexRepositoryRequest
from codeman.contracts.repository import (
    CreateSnapshotRequest,
    ExtractSourceFilesRequest,
    RegisterRepositoryRequest,
)
from codeman.contracts.retrieval import (
    BuildLexicalIndexRequest,
    BuildSemanticIndexRequest,
    RunHybridQueryRequest,
)

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parents[2] / "fixtures" / "repositories" / "mixed_stack_fixture"
)


def prepare_hybrid_repository(
    *,
    workspace: Path,
    repository_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[object, str, str]:
    local_model_path = workspace / "local-model"
    local_model_path.mkdir()
    monkeypatch.setenv("CODEMAN_SEMANTIC_PROVIDER_ID", "local-hash")
    monkeypatch.setenv("CODEMAN_SEMANTIC_LOCAL_MODEL_PATH", str(local_model_path))
    monkeypatch.setenv("CODEMAN_SEMANTIC_MODEL_ID", "fixture-local")
    monkeypatch.setenv("CODEMAN_SEMANTIC_MODEL_VERSION", "2026-03-14")

    container = bootstrap(workspace_root=workspace)
    registration = container.register_repository.execute(
        RegisterRepositoryRequest(repository_path=repository_path),
    )
    snapshot = container.create_snapshot.execute(
        CreateSnapshotRequest(repository_id=registration.repository.repository_id),
    )
    container.extract_source_files.execute(
        ExtractSourceFilesRequest(snapshot_id=snapshot.snapshot.snapshot_id),
    )
    container.build_chunks.execute(
        BuildChunksRequest(snapshot_id=snapshot.snapshot.snapshot_id),
    )
    container.build_lexical_index.execute(
        BuildLexicalIndexRequest(snapshot_id=snapshot.snapshot.snapshot_id),
    )
    container.build_semantic_index.execute(
        BuildSemanticIndexRequest(snapshot_id=snapshot.snapshot.snapshot_id),
    )
    return (
        container,
        registration.repository.repository_id,
        snapshot.snapshot.snapshot_id,
    )


def test_run_hybrid_query_uses_persisted_artifacts_not_live_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, _ = prepare_hybrid_repository(
        workspace=workspace,
        repository_path=repository_path,
        monkeypatch=monkeypatch,
    )
    (repository_path / "assets" / "app.js").write_text(
        'export function boot() {\n  return "fresh-live";\n}\n',
        encoding="utf-8",
    )

    result = container.run_hybrid_query.execute(
        RunHybridQueryRequest(
            repository_id=repository_id,
            query_text="boot()",
        ),
    )

    app_result = next(item for item in result.results if item.relative_path == "assets/app.js")
    assert "codeman" in app_result.content_preview
    assert "fresh-live" not in app_result.content_preview


def test_run_hybrid_query_requires_matching_component_snapshots_after_reindex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, initial_snapshot_id = prepare_hybrid_repository(
        workspace=workspace,
        repository_path=repository_path,
        monkeypatch=monkeypatch,
    )
    semantic_fingerprint = build_semantic_indexing_fingerprint(
        container.config.semantic_indexing,
        container.config.embedding_providers,
    )
    initial_semantic_build = container.semantic_index_build_store.get_latest_build_for_snapshot(
        initial_snapshot_id,
        semantic_fingerprint,
    )
    assert initial_semantic_build is not None
    (repository_path / "assets" / "app.js").write_text(
        'export function boot() {\n  return "fresh";\n}\n',
        encoding="utf-8",
    )

    reindex_result = container.reindex_repository.execute(
        ReindexRepositoryRequest(repository_id=repository_id),
    )
    container.build_lexical_index.execute(
        BuildLexicalIndexRequest(snapshot_id=reindex_result.result_snapshot_id),
    )

    with monkeypatch.context() as drift_patch:
        drift_patch.setattr(
            container.run_semantic_query.semantic_index_build_store,
            "get_latest_build_for_repository",
            lambda repository_id, semantic_config_fingerprint: initial_semantic_build,
        )
        with pytest.raises(HybridSnapshotMismatchError):
            container.run_hybrid_query.execute(
                RunHybridQueryRequest(
                    repository_id=repository_id,
                    query_text="fresh",
                ),
            )

    container.build_semantic_index.execute(
        BuildSemanticIndexRequest(snapshot_id=reindex_result.result_snapshot_id),
    )
    result = container.run_hybrid_query.execute(
        RunHybridQueryRequest(
            repository_id=repository_id,
            query_text="fresh",
        ),
    )

    assert initial_snapshot_id != reindex_result.result_snapshot_id
    assert result.snapshot.snapshot_id == reindex_result.result_snapshot_id
    assert result.build.lexical_build.build_id != result.build.semantic_build.build_id


def test_run_hybrid_query_treats_zero_lexical_matches_as_valid_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, _ = prepare_hybrid_repository(
        workspace=workspace,
        repository_path=repository_path,
        monkeypatch=monkeypatch,
    )

    result = container.run_hybrid_query.execute(
        RunHybridQueryRequest(
            repository_id=repository_id,
            query_text="velociraptor nebula quasar",
        ),
    )

    assert result.diagnostics.degraded is False
    assert result.diagnostics.lexical.match_count == 0
    assert len(result.results) > 0
    assert "semantic evidence only" in result.results[0].explanation

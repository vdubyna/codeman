from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from codeman.application.query.compare_retrieval_modes import (
    CompareRetrievalModesBaselineMissingError,
    CompareRetrievalModesSnapshotMismatchError,
)
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
    CompareRetrievalModesRequest,
)

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parents[2] / "fixtures" / "repositories" / "mixed_stack_fixture"
)


def prepare_compare_repository(
    *,
    workspace: Path,
    repository_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    build_semantic: bool = True,
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
    if build_semantic:
        container.build_semantic_index.execute(
            BuildSemanticIndexRequest(snapshot_id=snapshot.snapshot.snapshot_id),
        )
    return (
        container,
        registration.repository.repository_id,
        snapshot.snapshot.snapshot_id,
    )


def test_compare_retrieval_modes_uses_persisted_artifacts_not_live_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, _ = prepare_compare_repository(
        workspace=workspace,
        repository_path=repository_path,
        monkeypatch=monkeypatch,
    )
    (repository_path / "assets" / "app.js").write_text(
        'export function boot() {\n  return "fresh-live";\n}\n',
        encoding="utf-8",
    )

    result = container.compare_retrieval_modes.execute(
        CompareRetrievalModesRequest(
            repository_id=repository_id,
            query_text="boot()",
        ),
    )

    lexical_entry = next(entry for entry in result.entries if entry.retrieval_mode == "lexical")
    app_result = next(
        item for item in lexical_entry.results if item.relative_path == "assets/app.js"
    )
    assert "codeman" in app_result.content_preview
    assert "fresh-live" not in app_result.content_preview


def test_compare_retrieval_modes_fails_when_component_baseline_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, _ = prepare_compare_repository(
        workspace=workspace,
        repository_path=repository_path,
        monkeypatch=monkeypatch,
        build_semantic=False,
    )

    with pytest.raises(CompareRetrievalModesBaselineMissingError) as exc_info:
        container.compare_retrieval_modes.execute(
            CompareRetrievalModesRequest(
                repository_id=repository_id,
                query_text="controller home route",
            ),
        )

    assert exc_info.value.details == {
        "mode": "semantic",
        "mode_error_code": "semantic_build_baseline_missing",
    }


def test_compare_retrieval_modes_requires_matching_component_snapshots_after_reindex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, initial_snapshot_id = prepare_compare_repository(
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
        with pytest.raises(CompareRetrievalModesSnapshotMismatchError):
            container.compare_retrieval_modes.execute(
                CompareRetrievalModesRequest(
                    repository_id=repository_id,
                    query_text="fresh",
                ),
            )

    container.build_semantic_index.execute(
        BuildSemanticIndexRequest(snapshot_id=reindex_result.result_snapshot_id),
    )
    result = container.compare_retrieval_modes.execute(
        CompareRetrievalModesRequest(
            repository_id=repository_id,
            query_text="fresh",
        ),
    )

    assert initial_snapshot_id != reindex_result.result_snapshot_id
    assert result.snapshot.snapshot_id == reindex_result.result_snapshot_id
    assert [entry.retrieval_mode for entry in result.entries] == [
        "lexical",
        "semantic",
        "hybrid",
    ]

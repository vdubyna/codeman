from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from codeman.application.query.run_semantic_query import SemanticBuildBaselineMissingError
from codeman.bootstrap import bootstrap
from codeman.contracts.chunking import BuildChunksRequest
from codeman.contracts.reindexing import ReindexRepositoryRequest
from codeman.contracts.repository import (
    CreateSnapshotRequest,
    ExtractSourceFilesRequest,
    RegisterRepositoryRequest,
)
from codeman.contracts.retrieval import BuildSemanticIndexRequest, RunSemanticQueryRequest

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parents[2] / "fixtures" / "repositories" / "mixed_stack_fixture"
)


def prepare_queryable_repository(
    *,
    workspace: Path,
    repository_path: Path,
) -> tuple[object, str, str]:
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
    return (
        container,
        registration.repository.repository_id,
        snapshot.snapshot.snapshot_id,
    )


def test_run_semantic_query_uses_persisted_chunk_artifacts_not_live_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    monkeypatch.setenv("CODEMAN_SEMANTIC_PROVIDER_ID", "local-hash")
    monkeypatch.setenv("CODEMAN_SEMANTIC_LOCAL_MODEL_PATH", str(local_model_path))
    monkeypatch.setenv("CODEMAN_SEMANTIC_MODEL_ID", "fixture-local")
    monkeypatch.setenv("CODEMAN_SEMANTIC_MODEL_VERSION", "2026-03-14")

    container, repository_id, snapshot_id = prepare_queryable_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    container.build_semantic_index.execute(
        BuildSemanticIndexRequest(snapshot_id=snapshot_id),
    )
    (repository_path / "assets" / "app.js").write_text(
        'export function boot() {\n  return "fresh-live";\n}\n',
        encoding="utf-8",
    )

    result = container.run_semantic_query.execute(
        RunSemanticQueryRequest(
            repository_id=repository_id,
            query_text="controller home route",
        ),
    )
    app_result = next(item for item in result.results if item.relative_path == "assets/app.js")

    assert "codeman" in app_result.content_preview
    assert "fresh-live" not in app_result.content_preview
    assert result.build.provider_id == "local-hash"
    assert result.build.model_version == "2026-03-14"


def test_run_semantic_query_requires_matching_rebuild_after_reindex(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    monkeypatch.setenv("CODEMAN_SEMANTIC_PROVIDER_ID", "local-hash")
    monkeypatch.setenv("CODEMAN_SEMANTIC_LOCAL_MODEL_PATH", str(local_model_path))

    container, repository_id, snapshot_id = prepare_queryable_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    baseline = container.build_semantic_index.execute(
        BuildSemanticIndexRequest(snapshot_id=snapshot_id),
    )
    (repository_path / "assets" / "app.js").write_text(
        'export function boot() {\n  return "fresh";\n}\n',
        encoding="utf-8",
    )

    reindex_result = container.reindex_repository.execute(
        ReindexRepositoryRequest(repository_id=repository_id),
    )

    with pytest.raises(SemanticBuildBaselineMissingError):
        container.run_semantic_query.execute(
            RunSemanticQueryRequest(
                repository_id=repository_id,
                query_text="controller home route",
            ),
        )

    refreshed = container.build_semantic_index.execute(
        BuildSemanticIndexRequest(snapshot_id=reindex_result.result_snapshot_id),
    )
    result = container.run_semantic_query.execute(
        RunSemanticQueryRequest(
            repository_id=repository_id,
            query_text="controller home route",
        ),
    )

    assert result.snapshot.snapshot_id == reindex_result.result_snapshot_id
    assert result.build.build_id == refreshed.build.build_id
    assert result.build.build_id != baseline.build.build_id


def test_run_semantic_query_is_configuration_aware(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    monkeypatch.setenv("CODEMAN_SEMANTIC_PROVIDER_ID", "local-hash")
    monkeypatch.setenv("CODEMAN_SEMANTIC_LOCAL_MODEL_PATH", str(local_model_path))
    monkeypatch.setenv("CODEMAN_SEMANTIC_MODEL_VERSION", "1")

    first_container, repository_id, snapshot_id = prepare_queryable_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    first_container.build_semantic_index.execute(
        BuildSemanticIndexRequest(snapshot_id=snapshot_id),
    )

    monkeypatch.setenv("CODEMAN_SEMANTIC_MODEL_VERSION", "2")
    second_container = bootstrap(workspace_root=workspace)

    with pytest.raises(SemanticBuildBaselineMissingError):
        second_container.run_semantic_query.execute(
            RunSemanticQueryRequest(
                repository_id=repository_id,
                query_text="controller home route",
            ),
        )

    rebuilt = second_container.build_semantic_index.execute(
        BuildSemanticIndexRequest(snapshot_id=snapshot_id),
    )
    result = second_container.run_semantic_query.execute(
        RunSemanticQueryRequest(
            repository_id=repository_id,
            query_text="controller home route",
        ),
    )

    assert result.build.semantic_config_fingerprint == rebuilt.build.semantic_config_fingerprint
    assert result.build.model_version == "2"

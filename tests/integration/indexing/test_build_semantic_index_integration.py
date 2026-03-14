from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from codeman.bootstrap import bootstrap
from codeman.config.semantic_indexing import build_semantic_indexing_fingerprint
from codeman.contracts.chunking import BuildChunksRequest
from codeman.contracts.reindexing import ReindexRepositoryRequest
from codeman.contracts.repository import (
    CreateSnapshotRequest,
    ExtractSourceFilesRequest,
    RegisterRepositoryRequest,
)
from codeman.contracts.retrieval import BuildSemanticIndexRequest
from codeman.infrastructure.artifacts.filesystem_artifact_store import (
    FilesystemArtifactStore,
)

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parents[2] / "fixtures" / "repositories" / "mixed_stack_fixture"
)


def prepare_chunked_repository(
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


def test_build_semantic_index_uses_persisted_chunk_artifacts_not_live_repository(
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

    container, _, snapshot_id = prepare_chunked_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    (repository_path / "assets" / "app.js").write_text(
        'export function boot() {\n  return "fresh-live";\n}\n',
        encoding="utf-8",
    )

    result = container.build_semantic_index.execute(
        BuildSemanticIndexRequest(snapshot_id=snapshot_id),
    )
    artifact_store = FilesystemArtifactStore(container.runtime_paths.artifacts)
    embedding_artifact = artifact_store.read_embedding_documents(
        result.diagnostics.embedding_documents_path,
    )
    app_document = next(
        document
        for document in embedding_artifact.documents
        if document.relative_path == "assets/app.js"
    )
    with sqlite3.connect(result.build.artifact_path) as connection:
        stored_count = connection.execute(
            "SELECT COUNT(*) FROM semantic_vectors",
        ).fetchone()[0]

    assert "codeman" in app_document.content
    assert "fresh-live" not in app_document.content
    assert stored_count == 8


def test_build_semantic_index_prefers_current_snapshot_after_reindex(
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

    container, repository_id, snapshot_id = prepare_chunked_repository(
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
    stale_lookup = container.semantic_index_build_store.get_latest_build_for_repository(
        repository_id,
        baseline.build.semantic_config_fingerprint,
    )
    refreshed = container.build_semantic_index.execute(
        BuildSemanticIndexRequest(snapshot_id=reindex_result.result_snapshot_id),
    )
    latest_lookup = container.semantic_index_build_store.get_latest_build_for_repository(
        repository_id,
        baseline.build.semantic_config_fingerprint,
    )

    assert stale_lookup is None
    assert refreshed.build.snapshot_id == reindex_result.result_snapshot_id
    assert refreshed.build.snapshot_id != baseline.build.snapshot_id
    assert refreshed.build.artifact_path != baseline.build.artifact_path
    assert latest_lookup is not None
    assert latest_lookup.snapshot_id == refreshed.build.snapshot_id


def test_build_semantic_index_is_configuration_aware_for_same_snapshot(
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

    first_container, _, snapshot_id = prepare_chunked_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    first_build = first_container.build_semantic_index.execute(
        BuildSemanticIndexRequest(snapshot_id=snapshot_id),
    )
    first_fingerprint = first_build.build.semantic_config_fingerprint

    monkeypatch.setenv("CODEMAN_SEMANTIC_MODEL_VERSION", "2")
    second_container = bootstrap(workspace_root=workspace)
    second_fingerprint = build_semantic_indexing_fingerprint(
        second_container.config.semantic_indexing,
        second_container.config.embedding_providers,
    )
    stale_lookup = second_container.semantic_index_build_store.get_latest_build_for_snapshot(
        snapshot_id,
        second_fingerprint,
    )
    second_build = second_container.build_semantic_index.execute(
        BuildSemanticIndexRequest(snapshot_id=snapshot_id),
    )
    latest_lookup = second_container.semantic_index_build_store.get_latest_build_for_snapshot(
        snapshot_id,
        second_fingerprint,
    )
    original_lookup = second_container.semantic_index_build_store.get_latest_build_for_snapshot(
        snapshot_id,
        first_fingerprint,
    )

    assert stale_lookup is None
    assert first_fingerprint != second_fingerprint
    assert second_build.build.artifact_path != first_build.build.artifact_path
    assert latest_lookup is not None
    assert latest_lookup.semantic_config_fingerprint == second_fingerprint
    assert original_lookup is not None
    assert original_lookup.semantic_config_fingerprint == first_fingerprint

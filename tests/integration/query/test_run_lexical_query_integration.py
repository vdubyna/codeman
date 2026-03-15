from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from codeman.application.query.run_lexical_query import (
    LexicalArtifactMissingError,
    LexicalBuildBaselineMissingError,
    LexicalQueryChunkMetadataMissingError,
    LexicalQueryChunkPayloadMissingError,
)
from codeman.bootstrap import bootstrap
from codeman.config.indexing import IndexingConfig, build_indexing_fingerprint
from codeman.contracts.chunking import BuildChunksRequest
from codeman.contracts.reindexing import ReindexRepositoryRequest
from codeman.contracts.repository import (
    CreateSnapshotRequest,
    ExtractSourceFilesRequest,
    RegisterRepositoryRequest,
)
from codeman.contracts.retrieval import (
    BuildLexicalIndexRequest,
    RunLexicalQueryRequest,
)

FIXTURE_REPOSITORY = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "repositories"
    / "mixed_stack_fixture"
)


def prepare_lexical_repository(
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
    container.build_lexical_index.execute(
        BuildLexicalIndexRequest(snapshot_id=snapshot.snapshot.snapshot_id),
    )
    return (
        container,
        registration.repository.repository_id,
        snapshot.snapshot.snapshot_id,
    )


def test_run_lexical_query_uses_current_repository_build_after_reindex(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, initial_snapshot_id = prepare_lexical_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    initial_result = container.run_lexical_query.execute(
        RunLexicalQueryRequest(
            repository_id=repository_id,
            query_text="boot()",
        ),
    )
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
    latest_result = container.run_lexical_query.execute(
        RunLexicalQueryRequest(
            repository_id=repository_id,
            query_text="fresh",
        ),
    )

    assert initial_result.snapshot.snapshot_id == initial_snapshot_id
    assert [match.relative_path for match in initial_result.results] == ["assets/app.js"]
    assert latest_result.snapshot.snapshot_id == reindex_result.result_snapshot_id
    assert latest_result.snapshot.snapshot_id != initial_snapshot_id
    assert [match.relative_path for match in latest_result.results] == ["assets/app.js"]


def test_run_lexical_query_formats_from_persisted_artifacts_not_live_repository(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, _ = prepare_lexical_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    (repository_path / "assets" / "app.js").write_text(
        'export function boot() {\n  return "fresh-live";\n}\n',
        encoding="utf-8",
    )

    result = container.run_lexical_query.execute(
        RunLexicalQueryRequest(
            repository_id=repository_id,
            query_text="boot()",
        ),
    )

    assert [item.relative_path for item in result.results] == ["assets/app.js"]
    assert "codeman" in result.results[0].content_preview
    assert "fresh-live" not in result.results[0].content_preview


def test_run_lexical_query_fails_when_build_artifact_is_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, _ = prepare_lexical_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    build = container.index_build_store.get_latest_build_for_repository(
        repository_id,
        build_indexing_fingerprint(IndexingConfig()),
    )
    assert build is not None
    build.index_path.unlink()

    with pytest.raises(LexicalArtifactMissingError):
        container.run_lexical_query.execute(
            RunLexicalQueryRequest(
                repository_id=repository_id,
                query_text="HomeController",
            ),
        )


def test_run_lexical_query_fails_when_ranked_chunk_metadata_is_missing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, snapshot_id = prepare_lexical_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    target_chunk = next(
        chunk
        for chunk in container.chunk_store.list_by_snapshot(snapshot_id)
        if chunk.relative_path == "src/Controller/HomeController.php"
    )

    with sqlite3.connect(container.runtime_paths.metadata_database_path) as connection:
        connection.execute("DELETE FROM chunks WHERE id = ?", (target_chunk.chunk_id,))
        connection.commit()

    with pytest.raises(LexicalQueryChunkMetadataMissingError):
        container.run_lexical_query.execute(
            RunLexicalQueryRequest(
                repository_id=repository_id,
                query_text="HomeController",
            ),
        )


def test_run_lexical_query_fails_when_ranked_chunk_payload_is_missing(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, snapshot_id = prepare_lexical_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    target_chunk = next(
        chunk
        for chunk in container.chunk_store.list_by_snapshot(snapshot_id)
        if chunk.relative_path == "src/Controller/HomeController.php"
    )
    target_chunk.payload_path.unlink()

    with pytest.raises(LexicalQueryChunkPayloadMissingError):
        container.run_lexical_query.execute(
            RunLexicalQueryRequest(
                repository_id=repository_id,
                query_text="HomeController",
            ),
        )


def test_run_lexical_query_fails_when_latest_snapshot_has_no_matching_config_baseline(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    baseline_container, repository_id, _ = prepare_lexical_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    (repository_path / "assets" / "app.js").write_text(
        'export function boot() {\n  return "fresh";\n}\n',
        encoding="utf-8",
    )

    reindex_result = baseline_container.reindex_repository.execute(
        ReindexRepositoryRequest(repository_id=repository_id),
    )
    baseline_container.build_lexical_index.execute(
        BuildLexicalIndexRequest(snapshot_id=reindex_result.result_snapshot_id),
    )

    profiled_container = bootstrap(
        workspace_root=workspace,
        environ={"CODEMAN_INDEXING_FINGERPRINT_SALT": "profile-v2"},
    )

    with pytest.raises(LexicalBuildBaselineMissingError) as exc_info:
        profiled_container.run_lexical_query.execute(
            RunLexicalQueryRequest(
                repository_id=repository_id,
                query_text="fresh",
            ),
        )

    assert "current configuration" in exc_info.value.message

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from codeman.application.query.run_lexical_query import LexicalArtifactMissingError
from codeman.bootstrap import bootstrap
from codeman.contracts.chunking import BuildChunksRequest
from codeman.contracts.reindexing import ReindexRepositoryRequest
from codeman.contracts.repository import (
    CreateSnapshotRequest,
    ExtractSourceFilesRequest,
    RegisterRepositoryRequest,
)
from codeman.contracts.retrieval import BuildLexicalIndexRequest, RunLexicalQueryRequest

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
    assert [match.relative_path for match in initial_result.matches] == ["assets/app.js"]
    assert latest_result.snapshot.snapshot_id == reindex_result.result_snapshot_id
    assert latest_result.snapshot.snapshot_id != initial_snapshot_id
    assert [match.relative_path for match in latest_result.matches] == ["assets/app.js"]


def test_run_lexical_query_fails_when_build_artifact_is_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    shutil.copytree(FIXTURE_REPOSITORY, repository_path)

    container, repository_id, _ = prepare_lexical_repository(
        workspace=workspace,
        repository_path=repository_path,
    )
    build = container.index_build_store.get_latest_build_for_repository(repository_id)
    assert build is not None
    build.index_path.unlink()

    with pytest.raises(LexicalArtifactMissingError):
        container.run_lexical_query.execute(
            RunLexicalQueryRequest(
                repository_id=repository_id,
                query_text="HomeController",
            ),
        )

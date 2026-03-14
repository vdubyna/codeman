from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from codeman.application.query.run_lexical_query import LexicalBuildBaselineMissingError
from codeman.bootstrap import bootstrap
from codeman.cli.app import app
from codeman.contracts.repository import RepositoryRecord, SnapshotRecord
from codeman.contracts.retrieval import (
    LexicalIndexBuildRecord,
    LexicalQueryDiagnostics,
    LexicalQueryMatch,
    RunLexicalQueryResult,
)

runner = CliRunner()


def build_query_result(
    repository_path: Path,
    *,
    query: str = "bootValue",
) -> RunLexicalQueryResult:
    now = datetime.now(UTC)
    repository = RepositoryRecord(
        repository_id="repo-123",
        repository_name=repository_path.name,
        canonical_path=repository_path,
        requested_path=repository_path,
        created_at=now,
        updated_at=now,
    )
    snapshot = SnapshotRecord(
        snapshot_id="snapshot-123",
        repository_id=repository.repository_id,
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        manifest_path=repository_path / "manifest.json",
        created_at=now,
        source_inventory_extracted_at=now,
        chunk_generation_completed_at=now,
        indexing_config_fingerprint="fingerprint-123",
    )
    return RunLexicalQueryResult(
        repository=repository,
        snapshot=snapshot,
        build=LexicalIndexBuildRecord(
            build_id="build-123",
            repository_id=repository.repository_id,
            snapshot_id=snapshot.snapshot_id,
            revision_identity=snapshot.revision_identity,
            revision_source=snapshot.revision_source,
            indexing_config_fingerprint="fingerprint-123",
            lexical_engine="sqlite-fts5",
            tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
            indexed_fields=["content", "relative_path"],
            chunks_indexed=2,
            index_path=(
                repository_path
                / ".codeman"
                / "indexes"
                / "lexical"
                / repository.repository_id
                / snapshot.snapshot_id
                / "lexical.sqlite3"
            ),
            created_at=now,
        ),
        query=query,
        matches=[
            LexicalQueryMatch(
                chunk_id="chunk-123",
                relative_path="assets/app.js",
                language="javascript",
                strategy="javascript_structure",
                score=-1.0,
                rank=1,
            )
        ],
        diagnostics=LexicalQueryDiagnostics(
            match_count=1,
            query_latency_ms=3,
        ),
    )


def test_query_lexical_command_renders_text_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubRunLexicalQueryUseCase:
        def execute(self, _request: object) -> RunLexicalQueryResult:
            return build_query_result(target_repo.resolve())

    container.run_lexical_query = StubRunLexicalQueryUseCase()

    result = runner.invoke(
        app,
        ["query", "lexical", "repo-123", "bootValue"],
        obj=container,
    )

    assert result.exit_code == 0, result.stdout
    assert "Lexical query matched 1 chunks" in result.stdout
    assert "Query: bootValue" in result.stdout
    assert "assets/app.js" in result.stdout


def test_query_lexical_command_accepts_option_like_query_via_explicit_flag(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)
    seen_requests: list[object] = []

    class StubRunLexicalQueryUseCase:
        def execute(self, request: object) -> RunLexicalQueryResult:
            seen_requests.append(request)
            return build_query_result(
                target_repo.resolve(),
                query="--output-format",
            )

    container.run_lexical_query = StubRunLexicalQueryUseCase()

    result = runner.invoke(
        app,
        [
            "query",
            "lexical",
            "repo-123",
            "--query=--output-format",
            "--output-format",
            "json",
        ],
        obj=container,
    )

    payload = json.loads(result.stdout.splitlines()[-1])

    assert result.exit_code == 0, result.stdout
    assert seen_requests[0].query_text == "--output-format"
    assert payload["ok"] is True
    assert payload["data"]["query"] == "--output-format"


def test_query_lexical_command_returns_json_failure_for_missing_baseline(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubRunLexicalQueryUseCase:
        def execute(self, _request: object) -> object:
            raise LexicalBuildBaselineMissingError(
                "No lexical baseline exists yet for this repository; "
                "run `codeman index build-lexical <snapshot-id>` first.",
            )

    container.run_lexical_query = StubRunLexicalQueryUseCase()

    result = runner.invoke(
        app,
        [
            "query",
            "lexical",
            "repo-123",
            "bootValue",
            "--output-format",
            "json",
        ],
        obj=container,
    )

    payload = json.loads(result.stdout.splitlines()[-1])

    assert result.exit_code == 38
    assert payload["ok"] is False
    assert payload["error"]["code"] == "lexical_build_baseline_missing"
    assert payload["meta"]["command"] == "query.lexical"

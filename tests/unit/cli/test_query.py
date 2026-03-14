from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codeman.application.query.run_lexical_query import LexicalBuildBaselineMissingError
from codeman.application.query.run_semantic_query import (
    SemanticArtifactCorruptError,
    SemanticBuildBaselineMissingError,
)
from codeman.bootstrap import bootstrap
from codeman.cli.app import app
from codeman.contracts.retrieval import (
    LexicalRetrievalBuildContext,
    RetrievalQueryDiagnostics,
    RetrievalQueryMetadata,
    RetrievalRepositoryContext,
    RetrievalResultItem,
    RetrievalSnapshotContext,
    RunLexicalQueryResult,
    RunSemanticQueryResult,
    SemanticRetrievalBuildContext,
)

runner = CliRunner()


def build_query_result(
    repository_path: Path,
    *,
    query: str = "bootValue",
) -> RunLexicalQueryResult:
    repository = RetrievalRepositoryContext(
        repository_id="repo-123",
        repository_name=repository_path.name,
    )
    snapshot = RetrievalSnapshotContext(
        snapshot_id="snapshot-123",
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
    )
    return RunLexicalQueryResult(
        repository=repository,
        snapshot=snapshot,
        build=LexicalRetrievalBuildContext(
            build_id="build-123",
            lexical_engine="sqlite-fts5",
            tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
            indexed_fields=["content", "relative_path"],
        ),
        query=RetrievalQueryMetadata(text=query),
        results=[
            RetrievalResultItem(
                chunk_id="chunk-123",
                relative_path="assets/app.js",
                language="javascript",
                strategy="javascript_structure",
                score=-1.0,
                rank=1,
                start_line=1,
                end_line=3,
                start_byte=0,
                end_byte=48,
                content_preview="export function bootValue() { return 'codeman'; }",
                explanation=(
                    "Matched lexical terms in content export function [bootValue]() { ... }."
                ),
            )
        ],
        diagnostics=RetrievalQueryDiagnostics(
            match_count=1,
            query_latency_ms=3,
            total_match_count=1,
            truncated=False,
        ),
    )


def build_semantic_query_result(
    repository_path: Path,
    *,
    query: str = "controller home route",
) -> RunSemanticQueryResult:
    repository = RetrievalRepositoryContext(
        repository_id="repo-123",
        repository_name=repository_path.name,
    )
    snapshot = RetrievalSnapshotContext(
        snapshot_id="snapshot-123",
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
    )
    return RunSemanticQueryResult(
        repository=repository,
        snapshot=snapshot,
        build=SemanticRetrievalBuildContext(
            build_id="semantic-build-123",
            provider_id="local-hash",
            model_id="fixture-local",
            model_version="2026-03-14",
            vector_engine="sqlite-exact",
            semantic_config_fingerprint="semantic-fingerprint-123",
        ),
        query=RetrievalQueryMetadata(text=query),
        results=[
            RetrievalResultItem(
                chunk_id="chunk-123",
                relative_path="src/Controller/HomeController.php",
                language="php",
                strategy="php_structure",
                score=0.875,
                rank=1,
                start_line=4,
                end_line=10,
                start_byte=32,
                end_byte=180,
                content_preview=(
                    "final class HomeController { public function __invoke(): "
                    "string { return 'home'; } }"
                ),
                explanation="Ranked by embedding similarity against the persisted semantic index.",
            )
        ],
        diagnostics=RetrievalQueryDiagnostics(
            match_count=1,
            query_latency_ms=7,
            total_match_count=8,
            truncated=True,
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
    assert "Lexical retrieval returned 1 results" in result.stdout
    assert "Query: bootValue" in result.stdout
    assert "assets/app.js" in result.stdout
    assert "span: lines 1-3 bytes 0-48" in result.stdout
    assert "preview: export function bootValue() { return 'codeman'; }" in result.stdout


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
    assert payload["data"]["query"]["text"] == "--output-format"


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


def test_query_semantic_command_renders_text_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubRunSemanticQueryUseCase:
        def execute(self, _request: object) -> RunSemanticQueryResult:
            return build_semantic_query_result(target_repo.resolve())

    container.run_semantic_query = StubRunSemanticQueryUseCase()

    result = runner.invoke(
        app,
        ["query", "semantic", "repo-123", "controller home route"],
        obj=container,
    )

    assert result.exit_code == 0, result.stdout
    assert "Semantic retrieval returned 1 of 8 results (truncated)" in result.stdout
    assert "Provider: local-hash" in result.stdout
    assert "Model Version: 2026-03-14" in result.stdout
    assert "Vector Engine: sqlite-exact" in result.stdout
    assert "Semantic Config Fingerprint: semantic-fingerprint-123" in result.stdout
    assert "src/Controller/HomeController.php" in result.stdout
    assert "Ranked by embedding similarity against the persisted semantic index." in result.stdout


def test_query_semantic_command_accepts_option_like_query_via_explicit_flag(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)
    seen_requests: list[object] = []

    class StubRunSemanticQueryUseCase:
        def execute(self, request: object) -> RunSemanticQueryResult:
            seen_requests.append(request)
            return build_semantic_query_result(
                target_repo.resolve(),
                query="--query",
            )

    container.run_semantic_query = StubRunSemanticQueryUseCase()

    result = runner.invoke(
        app,
        [
            "query",
            "semantic",
            "repo-123",
            "--query=--query",
            "--output-format",
            "json",
        ],
        obj=container,
    )

    payload = json.loads(result.stdout.splitlines()[-1])

    assert result.exit_code == 0, result.stdout
    assert seen_requests[0].query_text == "--query"
    assert payload["ok"] is True
    assert payload["data"]["query"]["text"] == "--query"
    assert payload["meta"]["command"] == "query.semantic"


def test_query_semantic_command_returns_json_failure_for_missing_baseline(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubRunSemanticQueryUseCase:
        def execute(self, _request: object) -> object:
            raise SemanticBuildBaselineMissingError(
                "No semantic baseline exists yet for this repository and current configuration; "
                "run `codeman index build-semantic <snapshot-id>` first.",
            )

    container.run_semantic_query = StubRunSemanticQueryUseCase()

    result = runner.invoke(
        app,
        [
            "query",
            "semantic",
            "repo-123",
            "controller home route",
            "--output-format",
            "json",
        ],
        obj=container,
    )

    payload = json.loads(result.stdout.splitlines()[-1])

    assert result.exit_code == 44
    assert payload["ok"] is False
    assert payload["error"]["code"] == "semantic_build_baseline_missing"
    assert payload["meta"]["command"] == "query.semantic"


def test_query_semantic_command_returns_json_failure_for_corrupt_artifact(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubRunSemanticQueryUseCase:
        def execute(self, _request: object) -> object:
            raise SemanticArtifactCorruptError(
                "Semantic artifact is invalid for build: semantic-build-123",
                details={
                    "artifact_path": str(
                        workspace / ".codeman" / "indexes" / "vector" / "semantic.sqlite3"
                    ),
                    "reason": "row count does not match recorded metadata",
                },
            )

    container.run_semantic_query = StubRunSemanticQueryUseCase()

    result = runner.invoke(
        app,
        [
            "query",
            "semantic",
            "repo-123",
            "controller home route",
            "--output-format",
            "json",
        ],
        obj=container,
    )

    payload = json.loads(result.stdout.splitlines()[-1])

    assert result.exit_code == 46
    assert payload["ok"] is False
    assert payload["error"]["code"] == "semantic_artifact_corrupt"
    assert payload["error"]["details"]["reason"] == "row count does not match recorded metadata"

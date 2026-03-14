from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from codeman.application.query.compare_retrieval_modes import (
    CompareRetrievalModesBaselineMissingError,
)
from codeman.bootstrap import bootstrap
from codeman.cli.app import app
from codeman.contracts.retrieval import (
    CompareRetrievalModesDiagnostics,
    CompareRetrievalModesResult,
    HybridComponentQueryDiagnostics,
    HybridQueryDiagnostics,
    HybridRetrievalBuildContext,
    LexicalRetrievalBuildContext,
    RetrievalModeComparisonEntry,
    RetrievalModeRankAlignment,
    RetrievalQueryDiagnostics,
    RetrievalQueryMetadata,
    RetrievalRepositoryContext,
    RetrievalResultItem,
    RetrievalSnapshotContext,
    SemanticRetrievalBuildContext,
)

runner = CliRunner()


def build_result_item(
    *,
    chunk_id: str,
    relative_path: str,
    rank: int,
    score: float,
    explanation: str,
) -> RetrievalResultItem:
    return RetrievalResultItem(
        chunk_id=chunk_id,
        relative_path=relative_path,
        language="php",
        strategy="php_structure",
        rank=rank,
        score=score,
        start_line=4,
        end_line=10,
        start_byte=32,
        end_byte=180,
        content_preview=f"preview for {chunk_id}",
        explanation=explanation,
    )


def build_compare_result(
    repository_path: Path,
    *,
    query: str = "controller home route",
) -> CompareRetrievalModesResult:
    repository = RetrievalRepositoryContext(
        repository_id="repo-123",
        repository_name=repository_path.name,
    )
    snapshot = RetrievalSnapshotContext(
        snapshot_id="snapshot-123",
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
    )
    lexical_item = build_result_item(
        chunk_id="chunk-shared",
        relative_path="src/Controller/HomeController.php",
        rank=1,
        score=-1.0,
        explanation="Matched lexical terms in path src/Controller/[HomeController].php.",
    )
    semantic_item = build_result_item(
        chunk_id="chunk-shared",
        relative_path="src/Controller/HomeController.php",
        rank=1,
        score=0.92,
        explanation="Ranked by embedding similarity against the persisted semantic index.",
    )
    hybrid_item = build_result_item(
        chunk_id="chunk-shared",
        relative_path="src/Controller/HomeController.php",
        rank=1,
        score=0.0328,
        explanation=(
            "Fused hybrid rank from lexical and semantic evidence for this persisted chunk."
        ),
    )
    return CompareRetrievalModesResult(
        query=RetrievalQueryMetadata(text=query),
        repository=repository,
        snapshot=snapshot,
        entries=[
            RetrievalModeComparisonEntry(
                retrieval_mode="lexical",
                build=LexicalRetrievalBuildContext(
                    build_id="lexical-build-123",
                    lexical_engine="sqlite-fts5",
                    tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
                    indexed_fields=["content", "relative_path"],
                ),
                diagnostics=RetrievalQueryDiagnostics(
                    match_count=1,
                    query_latency_ms=4,
                    total_match_count=1,
                    truncated=False,
                ),
                results=[lexical_item],
            ),
            RetrievalModeComparisonEntry(
                retrieval_mode="semantic",
                build=SemanticRetrievalBuildContext(
                    build_id="semantic-build-123",
                    provider_id="local-hash",
                    model_id="fixture-local",
                    model_version="2026-03-14",
                    vector_engine="sqlite-exact",
                    semantic_config_fingerprint="semantic-fingerprint-123",
                ),
                diagnostics=RetrievalQueryDiagnostics(
                    match_count=1,
                    query_latency_ms=7,
                    total_match_count=8,
                    truncated=True,
                ),
                results=[semantic_item],
            ),
            RetrievalModeComparisonEntry(
                retrieval_mode="hybrid",
                build=HybridRetrievalBuildContext(
                    build_id="hybrid-build-123",
                    rank_constant=60,
                    rank_window_size=50,
                    lexical_build=LexicalRetrievalBuildContext(
                        build_id="lexical-build-123",
                        lexical_engine="sqlite-fts5",
                        tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
                        indexed_fields=["content", "relative_path"],
                    ),
                    semantic_build=SemanticRetrievalBuildContext(
                        build_id="semantic-build-123",
                        provider_id="local-hash",
                        model_id="fixture-local",
                        model_version="2026-03-14",
                        vector_engine="sqlite-exact",
                        semantic_config_fingerprint="semantic-fingerprint-123",
                    ),
                ),
                diagnostics=HybridQueryDiagnostics(
                    match_count=1,
                    query_latency_ms=9,
                    total_match_count=4,
                    truncated=False,
                    rank_constant=60,
                    rank_window_size=50,
                    total_match_count_is_lower_bound=False,
                    lexical=HybridComponentQueryDiagnostics(
                        match_count=2,
                        total_match_count=2,
                        query_latency_ms=4,
                        truncated=False,
                        contributed_result_count=1,
                    ),
                    semantic=HybridComponentQueryDiagnostics(
                        match_count=3,
                        total_match_count=6,
                        query_latency_ms=5,
                        truncated=True,
                        contributed_result_count=1,
                    ),
                ),
                results=[hybrid_item],
            ),
        ],
        alignment=[
            RetrievalModeRankAlignment(
                chunk_id="chunk-shared",
                relative_path="src/Controller/HomeController.php",
                language="php",
                strategy="php_structure",
                lexical_rank=1,
                semantic_rank=1,
                hybrid_rank=1,
                lexical_score=-1.0,
                semantic_score=0.92,
                hybrid_score=0.0328,
            )
        ],
        diagnostics=CompareRetrievalModesDiagnostics(
            alignment_count=1,
            overlap_count=1,
            query_latency_ms=11,
        ),
    )


def test_compare_query_modes_command_renders_text_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubCompareRetrievalModesUseCase:
        def execute(self, _request: object) -> CompareRetrievalModesResult:
            return build_compare_result(target_repo.resolve())

    container.compare_retrieval_modes = StubCompareRetrievalModesUseCase()

    result = runner.invoke(
        app,
        ["compare", "query-modes", "repo-123", "controller home route"],
        obj=container,
    )

    assert result.exit_code == 0, result.stdout
    assert "Compared Modes: lexical, semantic, hybrid" in result.stdout
    assert "Rank Alignment:" in result.stdout
    assert "delta(h-l)=0" in result.stdout
    assert "Lexical Results:" in result.stdout
    assert "Semantic Results:" in result.stdout
    assert "Hybrid Results:" in result.stdout
    assert "Running retrieval mode comparison for repository" in result.stderr


def test_compare_query_modes_command_accepts_option_like_query_via_explicit_flag(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)
    seen_requests: list[object] = []

    class StubCompareRetrievalModesUseCase:
        def execute(self, request: object) -> CompareRetrievalModesResult:
            seen_requests.append(request)
            return build_compare_result(
                target_repo.resolve(),
                query="--query",
            )

    container.compare_retrieval_modes = StubCompareRetrievalModesUseCase()

    result = runner.invoke(
        app,
        [
            "compare",
            "query-modes",
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
    assert payload["meta"]["command"] == "compare.query_modes"


def test_compare_query_modes_command_returns_json_failure_for_missing_baseline(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubCompareRetrievalModesUseCase:
        def execute(self, _request: object) -> object:
            raise CompareRetrievalModesBaselineMissingError(
                "Comparison cannot run because the semantic retrieval mode is unavailable.",
                details={
                    "mode": "semantic",
                    "mode_error_code": "semantic_build_baseline_missing",
                },
            )

    container.compare_retrieval_modes = StubCompareRetrievalModesUseCase()

    result = runner.invoke(
        app,
        [
            "compare",
            "query-modes",
            "repo-123",
            "controller home route",
            "--output-format",
            "json",
        ],
        obj=container,
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 52
    assert payload["ok"] is False
    assert payload["error"]["code"] == "compare_retrieval_mode_baseline_missing"
    assert payload["error"]["details"]["mode"] == "semantic"
    assert payload["meta"]["command"] == "compare.query_modes"

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from codeman.application.query.run_hybrid_query import (
    DEFAULT_HYBRID_CANDIDATE_WINDOW,
    HybridComponentBaselineMissingError,
    HybridComponentUnavailableError,
    HybridSnapshotMismatchError,
    RunHybridQueryUseCase,
    compose_hybrid_result_from_components,
)
from codeman.application.query.run_lexical_query import LexicalBuildBaselineMissingError
from codeman.application.query.run_semantic_query import SemanticQueryProviderUnavailableError
from codeman.contracts.retrieval import (
    LexicalRetrievalBuildContext,
    RetrievalQueryDiagnostics,
    RetrievalQueryMetadata,
    RetrievalRepositoryContext,
    RetrievalResultItem,
    RetrievalSnapshotContext,
    RunHybridQueryRequest,
    RunLexicalQueryRequest,
    RunLexicalQueryResult,
    RunSemanticQueryRequest,
    RunSemanticQueryResult,
    SemanticRetrievalBuildContext,
)


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
        start_line=1,
        end_line=5,
        start_byte=0,
        end_byte=50,
        content_preview=f"preview for {chunk_id}",
        explanation=explanation,
    )


def build_lexical_result() -> RunLexicalQueryResult:
    return RunLexicalQueryResult(
        query=RetrievalQueryMetadata(text="controller home route"),
        repository=RetrievalRepositoryContext(
            repository_id="repo-123",
            repository_name="registered-repo",
        ),
        snapshot=RetrievalSnapshotContext(
            snapshot_id="snapshot-123",
            revision_identity="revision-abc",
            revision_source="filesystem_fingerprint",
        ),
        build=LexicalRetrievalBuildContext(
            build_id="lexical-build-123",
            lexical_engine="sqlite-fts5",
            tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
            indexed_fields=["content", "relative_path"],
        ),
        results=[
            build_result_item(
                chunk_id="chunk-shared",
                relative_path="src/Controller/HomeController.php",
                rank=1,
                score=-1.0,
                explanation="Matched lexical terms in path src/Controller/[HomeController].php.",
            ),
            build_result_item(
                chunk_id="chunk-lexical",
                relative_path="assets/app.js",
                rank=2,
                score=-0.5,
                explanation="Matched lexical terms in content export function [boot]().",
            ),
        ],
        diagnostics=RetrievalQueryDiagnostics(
            match_count=2,
            query_latency_ms=4,
            total_match_count=2,
            truncated=False,
        ),
    )


def build_semantic_result(
    *,
    snapshot_id: str = "snapshot-123",
    revision_identity: str = "revision-abc",
) -> RunSemanticQueryResult:
    return RunSemanticQueryResult(
        query=RetrievalQueryMetadata(text="controller home route"),
        repository=RetrievalRepositoryContext(
            repository_id="repo-123",
            repository_name="registered-repo",
        ),
        snapshot=RetrievalSnapshotContext(
            snapshot_id=snapshot_id,
            revision_identity=revision_identity,
            revision_source="filesystem_fingerprint",
        ),
        build=SemanticRetrievalBuildContext(
            build_id="semantic-build-123",
            provider_id="local-hash",
            model_id="fixture-local",
            model_version="2026-03-14",
            vector_engine="sqlite-exact",
            semantic_config_fingerprint="semantic-fingerprint-123",
        ),
        results=[
            build_result_item(
                chunk_id="chunk-shared",
                relative_path="src/Controller/HomeController.php",
                rank=1,
                score=0.92,
                explanation="Ranked by embedding similarity against the persisted semantic index.",
            ),
            build_result_item(
                chunk_id="chunk-semantic",
                relative_path="templates/home.html.twig",
                rank=2,
                score=0.75,
                explanation="Ranked by embedding similarity against the persisted semantic index.",
            ),
        ],
        diagnostics=RetrievalQueryDiagnostics(
            match_count=2,
            query_latency_ms=7,
            total_match_count=5,
            truncated=False,
        ),
    )


@dataclass
class StubRunLexicalQueryUseCase:
    result: RunLexicalQueryResult | None = None
    error: Exception | None = None
    seen_requests: list[RunLexicalQueryRequest] = field(default_factory=list)

    def execute(self, request: RunLexicalQueryRequest) -> RunLexicalQueryResult:
        self.seen_requests.append(request)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


@dataclass
class StubRunSemanticQueryUseCase:
    result: RunSemanticQueryResult | None = None
    error: Exception | None = None
    seen_requests: list[RunSemanticQueryRequest] = field(default_factory=list)

    def execute(self, request: RunSemanticQueryRequest) -> RunSemanticQueryResult:
        self.seen_requests.append(request)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def test_run_hybrid_query_requests_internal_candidate_window_and_fuses_results() -> None:
    lexical = StubRunLexicalQueryUseCase(result=build_lexical_result())
    semantic = StubRunSemanticQueryUseCase(result=build_semantic_result())
    use_case = RunHybridQueryUseCase(
        run_lexical_query=lexical,
        run_semantic_query=semantic,
    )

    result = use_case.execute(
        RunHybridQueryRequest(
            repository_id="repo-123",
            query_text="controller home route",
        ),
    )

    assert lexical.seen_requests[0].max_results == DEFAULT_HYBRID_CANDIDATE_WINDOW
    assert semantic.seen_requests[0].max_results == DEFAULT_HYBRID_CANDIDATE_WINDOW
    assert result.retrieval_mode == "hybrid"
    assert result.build.lexical_build.build_id == "lexical-build-123"
    assert result.build.semantic_build.build_id == "semantic-build-123"
    assert result.diagnostics.lexical.match_count == 2
    assert result.diagnostics.semantic.match_count == 2
    assert result.results[0].chunk_id == "chunk-shared"
    assert result.results[0].explanation == (
        "Fused hybrid rank from lexical and semantic evidence for this persisted chunk."
    )


def test_run_hybrid_query_forwards_explicit_component_build_ids() -> None:
    lexical = StubRunLexicalQueryUseCase(result=build_lexical_result())
    semantic = StubRunSemanticQueryUseCase(result=build_semantic_result())
    use_case = RunHybridQueryUseCase(
        run_lexical_query=lexical,
        run_semantic_query=semantic,
    )

    use_case.execute(
        RunHybridQueryRequest(
            repository_id="repo-123",
            query_text="controller home route",
            lexical_build_id="lexical-build-123",
            semantic_build_id="semantic-build-123",
            record_provenance=False,
        ),
    )

    assert lexical.seen_requests[0].build_id == "lexical-build-123"
    assert lexical.seen_requests[0].record_provenance is False
    assert semantic.seen_requests[0].build_id == "semantic-build-123"
    assert semantic.seen_requests[0].record_provenance is False


def test_run_hybrid_query_allows_zero_match_component_without_marking_degraded() -> None:
    lexical_result = build_lexical_result().model_copy(
        update={
            "results": [],
            "diagnostics": RetrievalQueryDiagnostics(
                match_count=0,
                query_latency_ms=1,
                total_match_count=0,
                truncated=False,
            ),
        }
    )
    lexical = StubRunLexicalQueryUseCase(result=lexical_result)
    semantic = StubRunSemanticQueryUseCase(result=build_semantic_result())
    use_case = RunHybridQueryUseCase(
        run_lexical_query=lexical,
        run_semantic_query=semantic,
    )

    result = use_case.execute(
        RunHybridQueryRequest(
            repository_id="repo-123",
            query_text="velociraptor nebula quasar",
            max_results=5,
        ),
    )

    assert result.diagnostics.degraded is False
    assert result.diagnostics.lexical.match_count == 0
    assert result.results[0].explanation == (
        "Fused hybrid rank from semantic evidence only; lexical retrieval returned no "
        "match for this chunk."
    )


def test_run_hybrid_query_raises_when_component_baseline_is_missing() -> None:
    lexical = StubRunLexicalQueryUseCase(
        error=LexicalBuildBaselineMissingError(
            "No lexical baseline exists yet for this repository; run "
            "`codeman index build-lexical <snapshot-id>` first.",
        )
    )
    semantic = StubRunSemanticQueryUseCase(result=build_semantic_result())
    use_case = RunHybridQueryUseCase(
        run_lexical_query=lexical,
        run_semantic_query=semantic,
    )

    with pytest.raises(HybridComponentBaselineMissingError) as exc_info:
        use_case.execute(
            RunHybridQueryRequest(
                repository_id="repo-123",
                query_text="controller home route",
            ),
        )

    assert exc_info.value.details == {
        "component": "lexical",
        "component_error_code": "lexical_build_baseline_missing",
    }


def test_run_hybrid_query_preserves_component_error_details() -> None:
    lexical = StubRunLexicalQueryUseCase(result=build_lexical_result())
    semantic = StubRunSemanticQueryUseCase(
        error=SemanticQueryProviderUnavailableError(
            "Semantic query failed to initialize the configured local embedding provider.",
            details={
                "provider_id": "local-hash",
                "local_model_path": "/tmp/local-model",
            },
        )
    )
    use_case = RunHybridQueryUseCase(
        run_lexical_query=lexical,
        run_semantic_query=semantic,
    )

    with pytest.raises(HybridComponentUnavailableError) as exc_info:
        use_case.execute(
            RunHybridQueryRequest(
                repository_id="repo-123",
                query_text="controller home route",
            ),
        )

    assert exc_info.value.details == {
        "component": "semantic",
        "component_error_code": "embedding_provider_unavailable",
        "component_details": {
            "provider_id": "local-hash",
            "local_model_path": "/tmp/local-model",
        },
    }


def test_run_hybrid_query_raises_when_snapshots_do_not_match() -> None:
    lexical = StubRunLexicalQueryUseCase(result=build_lexical_result())
    semantic = StubRunSemanticQueryUseCase(
        result=build_semantic_result(
            snapshot_id="snapshot-999",
            revision_identity="revision-other",
        )
    )
    use_case = RunHybridQueryUseCase(
        run_lexical_query=lexical,
        run_semantic_query=semantic,
    )

    with pytest.raises(HybridSnapshotMismatchError):
        use_case.execute(
            RunHybridQueryRequest(
                repository_id="repo-123",
                query_text="controller home route",
            ),
        )


def test_run_hybrid_query_marks_total_match_count_as_lower_bound_when_component_truncated() -> None:
    lexical_result = build_lexical_result().model_copy(
        update={
            "diagnostics": RetrievalQueryDiagnostics(
                match_count=2,
                query_latency_ms=4,
                total_match_count=120,
                truncated=True,
            ),
        }
    )
    semantic_result = build_semantic_result().model_copy(
        update={
            "diagnostics": RetrievalQueryDiagnostics(
                match_count=2,
                query_latency_ms=7,
                total_match_count=80,
                truncated=False,
            ),
        }
    )
    lexical = StubRunLexicalQueryUseCase(result=lexical_result)
    semantic = StubRunSemanticQueryUseCase(result=semantic_result)
    use_case = RunHybridQueryUseCase(
        run_lexical_query=lexical,
        run_semantic_query=semantic,
    )

    result = use_case.execute(
        RunHybridQueryRequest(
            repository_id="repo-123",
            query_text="controller home route",
        ),
    )

    assert result.diagnostics.truncated is True
    assert result.diagnostics.total_match_count == 120
    assert result.diagnostics.total_match_count_is_lower_bound is True


def test_compose_hybrid_result_from_components_reuses_existing_component_packages() -> None:
    lexical_result = build_lexical_result()
    semantic_result = build_semantic_result()

    composition = compose_hybrid_result_from_components(
        lexical_result=lexical_result,
        semantic_result=semantic_result,
        query_text="controller home route",
        max_results=2,
        rank_window_size=DEFAULT_HYBRID_CANDIDATE_WINDOW,
        rank_constant=60,
        latency_ms=11,
    )

    assert composition.result.retrieval_mode == "hybrid"
    assert composition.result.build.lexical_build.build_id == "lexical-build-123"
    assert composition.result.build.semantic_build.build_id == "semantic-build-123"
    assert composition.result.results[0].chunk_id == "chunk-shared"
    assert composition.result.results[1].chunk_id == "chunk-lexical"
    assert len(composition.fused_results) == 3

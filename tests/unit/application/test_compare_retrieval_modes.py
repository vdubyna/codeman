from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from codeman.application.query.compare_retrieval_modes import (
    CompareRetrievalModesBaselineMissingError,
    CompareRetrievalModesModeUnavailableError,
    CompareRetrievalModesSnapshotMismatchError,
    CompareRetrievalModesUseCase,
)
from codeman.application.query.run_semantic_query import (
    SemanticBuildBaselineMissingError,
    SemanticQueryProviderUnavailableError,
)
from codeman.contracts.retrieval import (
    CompareRetrievalModesRequest,
    LexicalRetrievalBuildContext,
    RetrievalQueryDiagnostics,
    RetrievalQueryMetadata,
    RetrievalRepositoryContext,
    RetrievalResultItem,
    RetrievalSnapshotContext,
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


def test_compare_retrieval_modes_returns_stable_mode_order_and_alignment() -> None:
    lexical = StubRunLexicalQueryUseCase(result=build_lexical_result())
    semantic = StubRunSemanticQueryUseCase(result=build_semantic_result())
    use_case = CompareRetrievalModesUseCase(
        run_lexical_query=lexical,
        run_semantic_query=semantic,
    )

    result = use_case.execute(
        CompareRetrievalModesRequest(
            repository_id="repo-123",
            query_text="controller home route",
            max_results=2,
        )
    )

    assert lexical.seen_requests[0].max_results == use_case.candidate_window_size
    assert semantic.seen_requests[0].max_results == use_case.candidate_window_size
    assert [entry.retrieval_mode for entry in result.entries] == [
        "lexical",
        "semantic",
        "hybrid",
    ]
    assert result.alignment[0].chunk_id == "chunk-shared"
    assert result.alignment[0].lexical_rank == 1
    assert result.alignment[0].semantic_rank == 1
    assert result.alignment[0].hybrid_rank == 1
    assert result.alignment[1].chunk_id == "chunk-lexical"
    assert result.alignment[1].hybrid_rank == 2
    assert result.alignment[2].chunk_id == "chunk-semantic"
    assert result.alignment[2].hybrid_rank == 3
    assert result.diagnostics.alignment_count == 3
    assert result.diagnostics.overlap_count == 3


def test_compare_retrieval_modes_maps_missing_component_baseline() -> None:
    lexical = StubRunLexicalQueryUseCase(result=build_lexical_result())
    semantic = StubRunSemanticQueryUseCase(
        error=SemanticBuildBaselineMissingError(
            "No semantic baseline exists yet for this repository and current configuration; "
            "run `codeman index build-semantic <snapshot-id>` first.",
        )
    )
    use_case = CompareRetrievalModesUseCase(
        run_lexical_query=lexical,
        run_semantic_query=semantic,
    )

    with pytest.raises(CompareRetrievalModesBaselineMissingError) as exc_info:
        use_case.execute(
            CompareRetrievalModesRequest(
                repository_id="repo-123",
                query_text="controller home route",
            )
        )

    assert exc_info.value.details == {
        "mode": "semantic",
        "mode_error_code": "semantic_build_baseline_missing",
    }


def test_compare_retrieval_modes_maps_unavailable_component_details() -> None:
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
    use_case = CompareRetrievalModesUseCase(
        run_lexical_query=lexical,
        run_semantic_query=semantic,
    )

    with pytest.raises(CompareRetrievalModesModeUnavailableError) as exc_info:
        use_case.execute(
            CompareRetrievalModesRequest(
                repository_id="repo-123",
                query_text="controller home route",
            )
        )

    assert exc_info.value.details == {
        "mode": "semantic",
        "mode_error_code": "embedding_provider_unavailable",
        "mode_details": {
            "provider_id": "local-hash",
            "local_model_path": "/tmp/local-model",
        },
    }


def test_compare_retrieval_modes_raises_when_mode_snapshots_do_not_match() -> None:
    lexical = StubRunLexicalQueryUseCase(result=build_lexical_result())
    semantic = StubRunSemanticQueryUseCase(
        result=build_semantic_result(
            snapshot_id="snapshot-999",
            revision_identity="revision-other",
        )
    )
    use_case = CompareRetrievalModesUseCase(
        run_lexical_query=lexical,
        run_semantic_query=semantic,
    )

    with pytest.raises(CompareRetrievalModesSnapshotMismatchError) as exc_info:
        use_case.execute(
            CompareRetrievalModesRequest(
                repository_id="repo-123",
                query_text="controller home route",
            )
        )

    assert exc_info.value.details == {
        "lexical_snapshot_id": "snapshot-123",
        "semantic_snapshot_id": "snapshot-999",
        "lexical_revision_identity": "revision-abc",
        "semantic_revision_identity": "revision-other",
        "lexical_build_id": "lexical-build-123",
        "semantic_build_id": "semantic-build-123",
    }

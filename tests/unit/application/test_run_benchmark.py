from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from codeman.application.evaluation.load_benchmark_dataset import (
    BenchmarkDatasetValidationError,
    LoadBenchmarkDatasetUseCase,
)
from codeman.application.evaluation.run_benchmark import (
    BenchmarkRunBaselineMissingError,
    BenchmarkRunError,
    BenchmarkRunModeUnavailableError,
    RunBenchmarkUseCase,
)
from codeman.application.query.run_lexical_query import LexicalQueryError
from codeman.config.embedding_providers import EmbeddingProviderConfig, EmbeddingProvidersConfig
from codeman.config.indexing import IndexingConfig, build_indexing_fingerprint
from codeman.config.semantic_indexing import (
    SemanticIndexingConfig,
    build_semantic_indexing_fingerprint,
)
from codeman.contracts.configuration import RecordRunConfigurationProvenanceRequest
from codeman.contracts.evaluation import BenchmarkRunStatus, RunBenchmarkRequest
from codeman.contracts.repository import RepositoryRecord, SnapshotRecord
from codeman.contracts.retrieval import (
    HybridComponentQueryDiagnostics,
    HybridQueryDiagnostics,
    HybridRetrievalBuildContext,
    LexicalIndexBuildRecord,
    LexicalRetrievalBuildContext,
    RetrievalQueryDiagnostics,
    RetrievalQueryMetadata,
    RetrievalRepositoryContext,
    RetrievalResultItem,
    RetrievalSnapshotContext,
    RunHybridQueryRequest,
    RunHybridQueryResult,
    RunLexicalQueryRequest,
    RunLexicalQueryResult,
    RunSemanticQueryRequest,
    RunSemanticQueryResult,
    SemanticIndexBuildRecord,
    SemanticRetrievalBuildContext,
)
from codeman.infrastructure.artifacts.filesystem_artifact_store import (
    FilesystemArtifactStore,
)
from codeman.runtime import build_runtime_paths


def build_dataset_payload(*, query_ids: list[str]) -> dict[str, object]:
    return {
        "schema_version": "1",
        "dataset_id": "fixture-benchmark",
        "dataset_version": "2026-03-15",
        "cases": [
            {
                "query_id": query_id,
                "query_text": f"query text for {query_id}",
                "source_kind": "human_authored",
                "judgments": [
                    {
                        "relative_path": "src/Controller/HomeController.php",
                        "language": "php",
                        "start_line": 4,
                        "end_line": 10,
                        "relevance_grade": 2,
                    }
                ],
            }
            for query_id in query_ids
        ],
    }


def write_dataset(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def build_repository_record(tmp_path: Path) -> RepositoryRecord:
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir(exist_ok=True)
    return RepositoryRecord(
        repository_id="repo-123",
        repository_name=repository_path.name,
        canonical_path=repository_path.resolve(),
        requested_path=repository_path.resolve(),
        created_at=datetime(2026, 3, 15, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 3, 15, 9, 0, tzinfo=UTC),
    )


def build_snapshot_record() -> SnapshotRecord:
    return SnapshotRecord(
        snapshot_id="snapshot-123",
        repository_id="repo-123",
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        manifest_path=Path("/tmp/manifest.json"),
        created_at=datetime(2026, 3, 15, 9, 5, tzinfo=UTC),
        source_inventory_extracted_at=datetime(2026, 3, 15, 9, 6, tzinfo=UTC),
        chunk_generation_completed_at=datetime(2026, 3, 15, 9, 7, tzinfo=UTC),
        indexing_config_fingerprint=build_indexing_fingerprint(IndexingConfig()),
    )


def build_lexical_build(tmp_path: Path) -> LexicalIndexBuildRecord:
    index_path = tmp_path / "lexical.sqlite3"
    index_path.write_text("fixture", encoding="utf-8")
    return LexicalIndexBuildRecord(
        build_id="lexical-build-123",
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        indexing_config_fingerprint=build_indexing_fingerprint(IndexingConfig()),
        lexical_engine="sqlite-fts5",
        tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
        indexed_fields=["content", "relative_path"],
        chunks_indexed=12,
        index_path=index_path,
        created_at=datetime(2026, 3, 15, 9, 10, tzinfo=UTC),
    )


def build_semantic_config(local_model_path: Path) -> SemanticIndexingConfig:
    return SemanticIndexingConfig(
        provider_id="local-hash",
        vector_engine="sqlite-exact",
        vector_dimension=4,
    )


def build_embedding_providers_config(
    local_model_path: Path,
) -> EmbeddingProvidersConfig:
    return EmbeddingProvidersConfig(
        local_hash=EmbeddingProviderConfig(
            model_id="fixture-local",
            model_version="2026-03-14",
            local_model_path=local_model_path,
        ),
    )


def build_semantic_build(
    tmp_path: Path,
    *,
    semantic_config_fingerprint: str = "semantic-fingerprint-123",
) -> SemanticIndexBuildRecord:
    artifact_path = tmp_path / "semantic.sqlite3"
    artifact_path.write_text("fixture", encoding="utf-8")
    return SemanticIndexBuildRecord(
        build_id="semantic-build-123",
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        semantic_config_fingerprint=semantic_config_fingerprint,
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="2026-03-14",
        vector_engine="sqlite-exact",
        document_count=12,
        embedding_dimension=4,
        artifact_path=artifact_path,
        created_at=datetime(2026, 3, 15, 9, 10, tzinfo=UTC),
    )


def build_lexical_result(*, query_text: str) -> RunLexicalQueryResult:
    return RunLexicalQueryResult(
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
            indexing_config_fingerprint=build_indexing_fingerprint(IndexingConfig()),
            lexical_engine="sqlite-fts5",
            tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
            indexed_fields=["content", "relative_path"],
        ),
        query=RetrievalQueryMetadata(text=query_text),
        results=[
            RetrievalResultItem(
                chunk_id=f"chunk-{query_text}",
                relative_path="src/Controller/HomeController.php",
                language="php",
                strategy="php_structure",
                rank=1,
                score=-1.0,
                start_line=4,
                end_line=10,
                start_byte=32,
                end_byte=180,
                content_preview=(
                    "final class HomeController { public function __invoke(): string {} }"
                ),
                explanation="Matched lexical terms in the controller class.",
            )
        ],
        diagnostics=RetrievalQueryDiagnostics(
            match_count=1,
            total_match_count=1,
            truncated=False,
            query_latency_ms=5,
        ),
    )


def build_semantic_result(*, query_text: str) -> RunSemanticQueryResult:
    return RunSemanticQueryResult(
        repository=RetrievalRepositoryContext(
            repository_id="repo-123",
            repository_name="registered-repo",
        ),
        snapshot=RetrievalSnapshotContext(
            snapshot_id="snapshot-123",
            revision_identity="revision-abc",
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
        query=RetrievalQueryMetadata(text=query_text),
        results=[
            RetrievalResultItem(
                chunk_id=f"semantic-{query_text}",
                relative_path="src/Controller/HomeController.php",
                language="php",
                strategy="php_structure",
                rank=1,
                score=0.93,
                start_line=4,
                end_line=10,
                start_byte=32,
                end_byte=180,
                content_preview=(
                    "final class HomeController { public function __invoke(): string {} }"
                ),
                explanation="Ranked by embedding similarity against the persisted semantic index.",
            )
        ],
        diagnostics=RetrievalQueryDiagnostics(
            match_count=1,
            total_match_count=1,
            truncated=False,
            query_latency_ms=8,
        ),
    )


def build_hybrid_result(*, query_text: str) -> RunHybridQueryResult:
    lexical_build = LexicalRetrievalBuildContext(
        build_id="lexical-build-123",
        indexing_config_fingerprint=build_indexing_fingerprint(IndexingConfig()),
        lexical_engine="sqlite-fts5",
        tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
        indexed_fields=["content", "relative_path"],
    )
    semantic_build = SemanticRetrievalBuildContext(
        build_id="semantic-build-123",
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="2026-03-14",
        vector_engine="sqlite-exact",
        semantic_config_fingerprint="semantic-fingerprint-123",
    )
    return RunHybridQueryResult(
        repository=RetrievalRepositoryContext(
            repository_id="repo-123",
            repository_name="registered-repo",
        ),
        snapshot=RetrievalSnapshotContext(
            snapshot_id="snapshot-123",
            revision_identity="revision-abc",
            revision_source="filesystem_fingerprint",
        ),
        build=HybridRetrievalBuildContext(
            build_id="hybrid-build-123",
            rank_constant=60,
            rank_window_size=50,
            lexical_build=lexical_build,
            semantic_build=semantic_build,
        ),
        query=RetrievalQueryMetadata(text=query_text),
        results=[
            RetrievalResultItem(
                chunk_id=f"hybrid-{query_text}",
                relative_path="src/Controller/HomeController.php",
                language="php",
                strategy="php_structure",
                rank=1,
                score=1.0,
                start_line=4,
                end_line=10,
                start_byte=32,
                end_byte=180,
                content_preview=(
                    "final class HomeController { public function __invoke(): string {} }"
                ),
                explanation="Fused hybrid rank from lexical and semantic evidence.",
            )
        ],
        diagnostics=HybridQueryDiagnostics(
            match_count=1,
            total_match_count=1,
            truncated=False,
            query_latency_ms=9,
            rank_constant=60,
            rank_window_size=50,
            lexical=HybridComponentQueryDiagnostics(
                match_count=1,
                total_match_count=1,
                truncated=False,
                query_latency_ms=5,
                contributed_result_count=1,
            ),
            semantic=HybridComponentQueryDiagnostics(
                match_count=1,
                total_match_count=1,
                truncated=False,
                query_latency_ms=8,
                contributed_result_count=1,
            ),
        ),
    )


@dataclass
class StubRepositoryStore:
    repository: RepositoryRecord | None
    initialized: bool = False

    def initialize(self) -> None:
        self.initialized = True

    def get_by_repository_id(self, repository_id: str) -> RepositoryRecord | None:
        if self.repository is None:
            return None
        if self.repository.repository_id != repository_id:
            return None
        return self.repository

    def get_by_canonical_path(self, canonical_path: Path) -> RepositoryRecord | None:
        return None

    def create_repository(self, **_: object) -> RepositoryRecord:
        raise AssertionError("Not used in benchmark tests.")


@dataclass
class StubSnapshotStore:
    snapshot: SnapshotRecord | None
    initialized: bool = False

    def initialize(self) -> None:
        self.initialized = True

    def get_by_snapshot_id(self, snapshot_id: str) -> SnapshotRecord | None:
        return self.snapshot if self.snapshot and self.snapshot.snapshot_id == snapshot_id else None

    def get_latest_indexed_snapshot(self, repository_id: str) -> SnapshotRecord | None:
        return self.snapshot

    def create_snapshot(self, **_: object) -> SnapshotRecord:
        raise AssertionError("Not used in benchmark tests.")

    def mark_source_inventory_extracted(self, **_: object) -> None:
        raise AssertionError("Not used in benchmark tests.")

    def mark_chunks_generated(self, **_: object) -> None:
        raise AssertionError("Not used in benchmark tests.")


@dataclass
class StubIndexBuildStore:
    build: LexicalIndexBuildRecord | None
    initialized: bool = False

    def initialize(self) -> None:
        self.initialized = True

    def create_build(self, build: LexicalIndexBuildRecord) -> LexicalIndexBuildRecord:
        raise AssertionError("Not used in benchmark tests.")

    def get_latest_build_for_snapshot(self, snapshot_id: str) -> LexicalIndexBuildRecord | None:
        return self.build

    def get_latest_build_for_repository(
        self,
        repository_id: str,
        indexing_config_fingerprint: str,
    ) -> LexicalIndexBuildRecord | None:
        return self.build

    def get_by_build_id(self, build_id: str) -> LexicalIndexBuildRecord | None:
        return self.build if self.build and self.build.build_id == build_id else None


@dataclass
class StubSemanticIndexBuildStore:
    build: SemanticIndexBuildRecord | None = None
    initialized: bool = False

    def initialize(self) -> None:
        self.initialized = True

    def create_build(self, build: object) -> object:
        raise AssertionError("Not used in lexical benchmark tests.")

    def get_latest_build_for_snapshot(
        self,
        snapshot_id: str,
        semantic_config_fingerprint: str,
    ) -> SemanticIndexBuildRecord | None:
        if (
            self.build is None
            or self.build.snapshot_id != snapshot_id
            or self.build.semantic_config_fingerprint != semantic_config_fingerprint
        ):
            return None
        return self.build

    def get_latest_build_for_repository(
        self,
        repository_id: str,
        semantic_config_fingerprint: str,
    ) -> SemanticIndexBuildRecord | None:
        if (
            self.build is None
            or self.build.repository_id != repository_id
            or self.build.semantic_config_fingerprint != semantic_config_fingerprint
        ):
            return None
        return self.build

    def get_by_build_id(self, build_id: str) -> SemanticIndexBuildRecord | None:
        if self.build is None or self.build.build_id != build_id:
            return None
        return self.build


@dataclass
class StubBenchmarkRunStore:
    created: list[object] = field(default_factory=list)
    updated: list[object] = field(default_factory=list)
    initialized: bool = False

    def initialize(self) -> None:
        self.initialized = True

    def create_run(self, record: object) -> object:
        self.created.append(record)
        return record

    def update_run(self, record: object) -> object:
        self.updated.append(record)
        return record

    def get_by_run_id(self, run_id: str) -> object | None:
        return None

    def list_by_repository_id(self, repository_id: str) -> list[object]:
        return []


@dataclass
class StubLexicalRunner:
    responses: list[RunLexicalQueryResult | BaseException]
    requests: list[RunLexicalQueryRequest] = field(default_factory=list)

    def execute(self, request: RunLexicalQueryRequest) -> RunLexicalQueryResult:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


@dataclass
class StubSemanticRunner:
    responses: list[RunSemanticQueryResult | BaseException]
    requests: list[RunSemanticQueryRequest] = field(default_factory=list)

    def execute(self, request: RunSemanticQueryRequest) -> RunSemanticQueryResult:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


@dataclass
class StubHybridRunner:
    candidate_window_size: int = 50
    rank_constant: int = 60
    responses: list[RunHybridQueryResult | BaseException] = field(default_factory=list)
    requests: list[RunHybridQueryRequest] = field(default_factory=list)

    def execute(self, request: RunHybridQueryRequest) -> RunHybridQueryResult:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


@dataclass
class UnexpectedRunner:
    candidate_window_size: int = 50
    rank_constant: int = 60

    def execute(self, request: object) -> object:
        raise AssertionError("This runner should not be used in the current test.")


@dataclass
class StubRunProvenanceUseCase:
    requests: list[RecordRunConfigurationProvenanceRequest] = field(default_factory=list)

    def execute(self, request: RecordRunConfigurationProvenanceRequest) -> object:
        self.requests.append(request)
        return SimpleNamespace(run_id=request.run_id)


def build_use_case(
    *,
    tmp_path: Path,
    repository: RepositoryRecord | None = None,
    snapshot: SnapshotRecord | None = None,
    lexical_build: LexicalIndexBuildRecord | None = None,
    semantic_build: SemanticIndexBuildRecord | None = None,
    lexical_runner: StubLexicalRunner | None = None,
    semantic_runner: StubSemanticRunner | None = None,
    hybrid_runner: StubHybridRunner | None = None,
    provenance: StubRunProvenanceUseCase | None = None,
    semantic_indexing_config: SemanticIndexingConfig | None = None,
    embedding_providers_config: EmbeddingProvidersConfig | None = None,
) -> tuple[
    RunBenchmarkUseCase,
    StubBenchmarkRunStore,
    FilesystemArtifactStore,
    StubRunProvenanceUseCase,
]:
    runtime_paths = build_runtime_paths(workspace_root=tmp_path / "workspace")
    benchmark_run_store = StubBenchmarkRunStore()
    artifact_store = FilesystemArtifactStore(runtime_paths.artifacts)
    provenance_use_case = provenance or StubRunProvenanceUseCase()
    use_case = RunBenchmarkUseCase(
        runtime_paths=runtime_paths,
        repository_store=StubRepositoryStore(repository=repository),
        snapshot_store=StubSnapshotStore(snapshot=snapshot),
        index_build_store=StubIndexBuildStore(build=lexical_build),
        semantic_index_build_store=StubSemanticIndexBuildStore(build=semantic_build),
        benchmark_run_store=benchmark_run_store,
        artifact_store=artifact_store,
        load_benchmark_dataset=LoadBenchmarkDatasetUseCase(),
        run_lexical_query=lexical_runner or StubLexicalRunner(responses=[]),
        run_semantic_query=semantic_runner or UnexpectedRunner(),
        run_hybrid_query=hybrid_runner or UnexpectedRunner(),
        indexing_config=IndexingConfig(),
        semantic_indexing_config=semantic_indexing_config or SemanticIndexingConfig(),
        embedding_providers_config=embedding_providers_config or EmbeddingProvidersConfig(),
        record_run_provenance=provenance_use_case,
    )
    return use_case, benchmark_run_store, artifact_store, provenance_use_case


def test_run_benchmark_executes_cases_and_persists_artifact_and_provenance(
    tmp_path: Path,
) -> None:
    dataset_path = write_dataset(
        tmp_path / "dataset.json",
        build_dataset_payload(query_ids=["case-1", "case-2"]),
    )
    repository = build_repository_record(tmp_path)
    snapshot = build_snapshot_record()
    lexical_build = build_lexical_build(tmp_path)
    lexical_runner = StubLexicalRunner(
        responses=[
            build_lexical_result(query_text="query text for case-1"),
            build_lexical_result(query_text="query text for case-2"),
        ]
    )
    use_case, benchmark_run_store, artifact_store, provenance = build_use_case(
        tmp_path=tmp_path,
        repository=repository,
        snapshot=snapshot,
        lexical_build=lexical_build,
        lexical_runner=lexical_runner,
    )
    progress_lines: list[str] = []

    result = use_case.execute(
        RunBenchmarkRequest(
            repository_id="repo-123",
            dataset_path=dataset_path,
            retrieval_mode="lexical",
            max_results=7,
        ),
        progress=progress_lines.append,
    )

    assert result.run.status == BenchmarkRunStatus.SUCCEEDED
    assert result.run.case_count == 2
    assert result.run.completed_case_count == 2
    assert result.run.artifact_path is not None
    assert result.run.artifact_path == (
        artifact_store.artifacts_root / "benchmarks" / result.run.run_id / "run.json"
    )
    assert benchmark_run_store.created[0].status == BenchmarkRunStatus.RUNNING
    assert benchmark_run_store.updated[-1].status == BenchmarkRunStatus.SUCCEEDED
    assert lexical_runner.requests[0].record_provenance is False
    assert lexical_runner.requests[1].record_provenance is False
    assert provenance.requests[0].run_id == result.run.run_id
    assert provenance.requests[0].workflow_type == "eval.benchmark"
    assert provenance.requests[0].workflow_context.benchmark_dataset_id == "fixture-benchmark"
    assert provenance.requests[0].workflow_context.retrieval_mode == "lexical"
    assert progress_lines == [
        f"Loading benchmark dataset: {dataset_path}",
        "Resolving benchmark baseline for repository: repo-123 (lexical)",
        "Running benchmark case 1/2: case-1",
        "Running benchmark case 2/2: case-2",
        f"Writing benchmark artifact for run: {result.run.run_id}",
        f"Recording benchmark provenance for run: {result.run.run_id}",
    ]


def test_run_benchmark_executes_semantic_cases_against_the_preflight_build(
    tmp_path: Path,
) -> None:
    dataset_path = write_dataset(
        tmp_path / "dataset.json",
        build_dataset_payload(query_ids=["case-1"]),
    )
    repository = build_repository_record(tmp_path)
    snapshot = build_snapshot_record()
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    semantic_config = build_semantic_config(local_model_path)
    embedding_config = build_embedding_providers_config(local_model_path)
    semantic_build = build_semantic_build(
        tmp_path,
        semantic_config_fingerprint=build_semantic_indexing_fingerprint(
            semantic_config,
            embedding_config,
        ),
    )
    semantic_runner = StubSemanticRunner(
        responses=[build_semantic_result(query_text="query text for case-1")]
    )
    use_case, benchmark_run_store, artifact_store, _ = build_use_case(
        tmp_path=tmp_path,
        repository=repository,
        snapshot=snapshot,
        semantic_build=semantic_build,
        semantic_runner=semantic_runner,
        semantic_indexing_config=semantic_config,
        embedding_providers_config=embedding_config,
    )

    result = use_case.execute(
        RunBenchmarkRequest(
            repository_id="repo-123",
            dataset_path=dataset_path,
            retrieval_mode="semantic",
            max_results=6,
        ),
    )

    assert result.run.status == BenchmarkRunStatus.SUCCEEDED
    assert semantic_runner.requests[0].build_id == semantic_build.build_id
    assert semantic_runner.requests[0].record_provenance is False
    assert benchmark_run_store.updated[-1].status == BenchmarkRunStatus.SUCCEEDED
    assert (
        artifact_store.read_benchmark_run_artifact(result.run.artifact_path).build.build_id
        == semantic_build.build_id
    )


def test_run_benchmark_executes_hybrid_cases_against_the_preflight_builds(
    tmp_path: Path,
) -> None:
    dataset_path = write_dataset(
        tmp_path / "dataset.json",
        build_dataset_payload(query_ids=["case-1"]),
    )
    repository = build_repository_record(tmp_path)
    snapshot = build_snapshot_record()
    lexical_build = build_lexical_build(tmp_path)
    local_model_path = tmp_path / "local-model"
    local_model_path.mkdir()
    semantic_config = build_semantic_config(local_model_path)
    embedding_config = build_embedding_providers_config(local_model_path)
    semantic_build = build_semantic_build(
        tmp_path,
        semantic_config_fingerprint=build_semantic_indexing_fingerprint(
            semantic_config,
            embedding_config,
        ),
    )
    hybrid_runner = StubHybridRunner(
        responses=[build_hybrid_result(query_text="query text for case-1")]
    )
    use_case, benchmark_run_store, artifact_store, _ = build_use_case(
        tmp_path=tmp_path,
        repository=repository,
        snapshot=snapshot,
        lexical_build=lexical_build,
        semantic_build=semantic_build,
        hybrid_runner=hybrid_runner,
        semantic_indexing_config=semantic_config,
        embedding_providers_config=embedding_config,
    )

    result = use_case.execute(
        RunBenchmarkRequest(
            repository_id="repo-123",
            dataset_path=dataset_path,
            retrieval_mode="hybrid",
            max_results=5,
        ),
    )

    assert result.run.status == BenchmarkRunStatus.SUCCEEDED
    assert hybrid_runner.requests[0].lexical_build_id == lexical_build.build_id
    assert hybrid_runner.requests[0].semantic_build_id == semantic_build.build_id
    assert hybrid_runner.requests[0].record_provenance is False
    artifact = artifact_store.read_benchmark_run_artifact(result.run.artifact_path)
    assert artifact.build.lexical_build.build_id == lexical_build.build_id
    assert artifact.build.semantic_build.build_id == semantic_build.build_id
    assert benchmark_run_store.updated[-1].status == BenchmarkRunStatus.SUCCEEDED


def test_run_benchmark_surfaces_dataset_failures_before_creating_a_run(tmp_path: Path) -> None:
    dataset_path = write_dataset(
        tmp_path / "dataset.json",
        {
            "schema_version": "1",
            "dataset_id": "fixture-benchmark",
            "dataset_version": "2026-03-15",
            "cases": [{"query_id": "case-1"}],
        },
    )
    repository = build_repository_record(tmp_path)
    snapshot = build_snapshot_record()
    lexical_build = build_lexical_build(tmp_path)
    use_case, benchmark_run_store, _, _ = build_use_case(
        tmp_path=tmp_path,
        repository=repository,
        snapshot=snapshot,
        lexical_build=lexical_build,
    )

    with pytest.raises(BenchmarkDatasetValidationError):
        use_case.execute(
            RunBenchmarkRequest(
                repository_id="repo-123",
                dataset_path=dataset_path,
                retrieval_mode="lexical",
            )
        )

    assert benchmark_run_store.created == []
    assert benchmark_run_store.updated == []


def test_run_benchmark_fails_preflight_when_selected_baseline_is_missing(tmp_path: Path) -> None:
    dataset_path = write_dataset(
        tmp_path / "dataset.json",
        build_dataset_payload(query_ids=["case-1"]),
    )
    repository = build_repository_record(tmp_path)
    snapshot = build_snapshot_record()
    use_case, benchmark_run_store, _, _ = build_use_case(
        tmp_path=tmp_path,
        repository=repository,
        snapshot=snapshot,
        lexical_build=None,
    )

    with pytest.raises(BenchmarkRunBaselineMissingError) as exc_info:
        use_case.execute(
            RunBenchmarkRequest(
                repository_id="repo-123",
                dataset_path=dataset_path,
                retrieval_mode="lexical",
            )
        )

    assert exc_info.value.details == {
        "retrieval_mode": "lexical",
        "component": "lexical",
        "repository_id": "repo-123",
        "indexing_config_fingerprint": build_indexing_fingerprint(IndexingConfig()),
    }
    assert benchmark_run_store.created == []


def test_run_benchmark_marks_run_failed_when_query_execution_breaks_midstream(
    tmp_path: Path,
) -> None:
    dataset_path = write_dataset(
        tmp_path / "dataset.json",
        build_dataset_payload(query_ids=["case-1", "case-2"]),
    )
    repository = build_repository_record(tmp_path)
    snapshot = build_snapshot_record()
    lexical_build = build_lexical_build(tmp_path)
    lexical_runner = StubLexicalRunner(
        responses=[
            build_lexical_result(query_text="query text for case-1"),
            LexicalQueryError("Lexical query crashed during execution."),
        ]
    )
    use_case, benchmark_run_store, artifact_store, provenance = build_use_case(
        tmp_path=tmp_path,
        repository=repository,
        snapshot=snapshot,
        lexical_build=lexical_build,
        lexical_runner=lexical_runner,
    )

    with pytest.raises(BenchmarkRunModeUnavailableError) as exc_info:
        use_case.execute(
            RunBenchmarkRequest(
                repository_id="repo-123",
                dataset_path=dataset_path,
                retrieval_mode="lexical",
            )
        )

    assert exc_info.value.details == {
        "query_id": "case-2",
        "retrieval_mode": "lexical",
        "component_error_code": "lexical_query_failed",
    }
    assert benchmark_run_store.created[0].status == BenchmarkRunStatus.RUNNING
    assert benchmark_run_store.updated[-1].status == BenchmarkRunStatus.FAILED
    assert benchmark_run_store.updated[-1].completed_case_count == 1
    assert benchmark_run_store.updated[-1].artifact_path is not None
    assert (
        artifact_store.read_benchmark_run_artifact(
            benchmark_run_store.updated[-1].artifact_path
        ).failure
        is not None
    )
    assert provenance.requests == []


def test_run_benchmark_marks_run_failed_when_execution_is_interrupted(
    tmp_path: Path,
) -> None:
    dataset_path = write_dataset(
        tmp_path / "dataset.json",
        build_dataset_payload(query_ids=["case-1", "case-2"]),
    )
    repository = build_repository_record(tmp_path)
    snapshot = build_snapshot_record()
    lexical_build = build_lexical_build(tmp_path)
    lexical_runner = StubLexicalRunner(
        responses=[
            build_lexical_result(query_text="query text for case-1"),
            KeyboardInterrupt(),
        ]
    )
    use_case, benchmark_run_store, artifact_store, provenance = build_use_case(
        tmp_path=tmp_path,
        repository=repository,
        snapshot=snapshot,
        lexical_build=lexical_build,
        lexical_runner=lexical_runner,
    )

    with pytest.raises(BenchmarkRunError) as exc_info:
        use_case.execute(
            RunBenchmarkRequest(
                repository_id="repo-123",
                dataset_path=dataset_path,
                retrieval_mode="lexical",
            )
        )

    assert exc_info.value.message == "Benchmark execution was interrupted."
    assert benchmark_run_store.created[0].status == BenchmarkRunStatus.RUNNING
    assert benchmark_run_store.updated[-1].status == BenchmarkRunStatus.FAILED
    assert benchmark_run_store.updated[-1].completed_case_count == 1
    assert benchmark_run_store.updated[-1].artifact_path is not None
    assert artifact_store.read_benchmark_run_artifact(
        benchmark_run_store.updated[-1].artifact_path
    ).failure.details == {"reason": "KeyboardInterrupt"}
    assert provenance.requests == []

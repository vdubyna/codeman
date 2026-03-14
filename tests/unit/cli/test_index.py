from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from codeman.application.indexing.build_chunks import SourceInventoryMissingError
from codeman.application.indexing.build_lexical_index import ChunkBaselineMissingError
from codeman.application.indexing.extract_source_files import SnapshotSourceMismatchError
from codeman.application.indexing.semantic_index_errors import (
    EmbeddingProviderUnavailableError,
)
from codeman.application.repo.reindex_repository import IndexedBaselineMissingError
from codeman.bootstrap import bootstrap
from codeman.cli.app import app
from codeman.contracts.chunking import (
    BuildChunksResult,
    ChunkFileDiagnostic,
    ChunkGenerationDiagnostics,
    ChunkRecord,
)
from codeman.contracts.reindexing import ReindexDiagnostics, ReindexRepositoryResult
from codeman.contracts.repository import (
    ExtractSourceFilesResult,
    RepositoryRecord,
    SnapshotRecord,
    SourceFileRecord,
    SourceInventoryDiagnostics,
)
from codeman.contracts.retrieval import (
    BuildLexicalIndexResult,
    BuildSemanticIndexResult,
    EmbeddingProviderDescriptor,
    LexicalIndexBuildDiagnostics,
    LexicalIndexBuildRecord,
    SemanticIndexBuildDiagnostics,
    SemanticIndexBuildRecord,
)

runner = CliRunner()


def build_result(repository_path: Path) -> ExtractSourceFilesResult:
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
    )
    return ExtractSourceFilesResult(
        repository=repository,
        snapshot=snapshot,
        source_files=[
            SourceFileRecord(
                source_file_id="source-123",
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                relative_path="assets/app.js",
                language="javascript",
                content_hash="hash-123",
                byte_size=16,
                discovered_at=now,
            )
        ],
        diagnostics=SourceInventoryDiagnostics(
            persisted_by_language={"javascript": 1},
            skipped_by_reason={"unsupported_extension": 1},
            persisted_total=1,
            skipped_total=1,
        ),
    )


def build_chunk_result(repository_path: Path) -> BuildChunksResult:
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
    )
    return BuildChunksResult(
        repository=repository,
        snapshot=snapshot,
        chunks=[
            ChunkRecord(
                chunk_id="chunk-123",
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                source_file_id="source-123",
                relative_path="assets/app.js",
                language="javascript",
                strategy="javascript_structure",
                source_content_hash="hash-123",
                start_line=1,
                end_line=3,
                start_byte=0,
                end_byte=42,
                payload_path=repository_path / ".codeman" / "chunk-123.json",
                created_at=now,
            ),
            ChunkRecord(
                chunk_id="chunk-456",
                snapshot_id=snapshot.snapshot_id,
                repository_id=repository.repository_id,
                source_file_id="source-456",
                relative_path="assets/broken.js",
                language="javascript",
                strategy="javascript_fallback",
                source_content_hash="hash-456",
                start_line=1,
                end_line=2,
                start_byte=0,
                end_byte=31,
                payload_path=repository_path / ".codeman" / "chunk-456.json",
                created_at=now,
            ),
        ],
        diagnostics=ChunkGenerationDiagnostics(
            chunks_by_language={"javascript": 2},
            chunks_by_strategy={
                "javascript_fallback": 1,
                "javascript_structure": 1,
            },
            total_chunks=2,
            fallback_file_count=1,
            degraded_file_count=1,
            skipped_file_count=0,
            file_diagnostics=[
                ChunkFileDiagnostic(
                    source_file_id="source-123",
                    relative_path="assets/app.js",
                    language="javascript",
                    preferred_strategy="javascript_structure",
                    strategy_used="javascript_structure",
                    mode="structural",
                    chunk_count=1,
                ),
                ChunkFileDiagnostic(
                    source_file_id="source-456",
                    relative_path="assets/broken.js",
                    language="javascript",
                    preferred_strategy="javascript_structure",
                    strategy_used="javascript_fallback",
                    mode="fallback",
                    chunk_count=1,
                    reason="preferred_path_unavailable",
                    message="Unbalanced braces detected in JavaScript source",
                ),
            ],
        ),
    )


def build_reindex_result(repository_path: Path) -> ReindexRepositoryResult:
    now = datetime.now(UTC)
    repository = RepositoryRecord(
        repository_id="repo-123",
        repository_name=repository_path.name,
        canonical_path=repository_path,
        requested_path=repository_path,
        created_at=now,
        updated_at=now,
    )
    return ReindexRepositoryResult(
        run_id="run-123",
        repository=repository,
        previous_snapshot_id="snapshot-123",
        result_snapshot_id="snapshot-456",
        change_reason="source_changed",
        previous_revision_identity="revision-old",
        result_revision_identity="revision-new",
        previous_config_fingerprint="fingerprint-old",
        current_config_fingerprint="fingerprint-old",
        source_files_reused=4,
        source_files_rebuilt=1,
        source_files_removed=0,
        chunks_reused=7,
        chunks_rebuilt=1,
        noop=False,
        diagnostics=ReindexDiagnostics(
            source_files_scanned=5,
            source_files_unchanged=4,
            source_files_changed=1,
            source_files_reused=4,
            source_files_rebuilt=1,
            chunks_reused=7,
            chunks_rebuilt=1,
        ),
    )


def build_lexical_result(repository_path: Path) -> BuildLexicalIndexResult:
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
    return BuildLexicalIndexResult(
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
        diagnostics=LexicalIndexBuildDiagnostics(
            chunks_indexed=2,
            refreshed_existing_artifact=False,
        ),
    )


def build_semantic_result(repository_path: Path) -> BuildSemanticIndexResult:
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
    return BuildSemanticIndexResult(
        repository=repository,
        snapshot=snapshot,
        build=SemanticIndexBuildRecord(
            build_id="build-semantic-123",
            repository_id=repository.repository_id,
            snapshot_id=snapshot.snapshot_id,
            revision_identity=snapshot.revision_identity,
            revision_source=snapshot.revision_source,
            semantic_config_fingerprint="semantic-fingerprint-123",
            provider_id="local-hash",
            model_id="fixture-local",
            model_version="1",
            is_external_provider=False,
            vector_engine="sqlite-exact",
            document_count=2,
            embedding_dimension=8,
            artifact_path=(
                repository_path
                / ".codeman"
                / "indexes"
                / "vector"
                / repository.repository_id
                / snapshot.snapshot_id
                / "semantic-fingerprint-123"
                / "semantic.sqlite3"
            ),
            created_at=now,
        ),
        provider=EmbeddingProviderDescriptor(
            provider_id="local-hash",
            model_id="fixture-local",
            model_version="1",
            is_external_provider=False,
            local_model_path=repository_path / ".local-model",
        ),
        diagnostics=SemanticIndexBuildDiagnostics(
            document_count=2,
            embedding_dimension=8,
            embedding_documents_path=(
                repository_path
                / ".codeman"
                / "artifacts"
                / "snapshots"
                / snapshot.snapshot_id
                / "embeddings"
                / "semantic-fingerprint-123"
                / "documents.json"
            ),
            refreshed_existing_artifact=False,
        ),
    )


def test_index_extract_sources_command_renders_text_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubExtractSourceFilesUseCase:
        def execute(self, _request: object) -> ExtractSourceFilesResult:
            return build_result(target_repo.resolve())

    container.extract_source_files = StubExtractSourceFilesUseCase()

    result = runner.invoke(
        app,
        ["index", "extract-sources", "snapshot-123"],
        obj=container,
    )

    assert result.exit_code == 0, result.stdout
    assert "Extracted source inventory: 1 files" in result.stdout
    assert "Persisted by language: javascript=1" in result.stdout


def test_index_extract_sources_command_returns_json_failure_for_mismatch(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubExtractSourceFilesUseCase:
        def execute(self, _request: object) -> object:
            raise SnapshotSourceMismatchError(
                "Snapshot revision no longer matches the live repository state; "
                "create a new snapshot before extracting sources: snapshot-123",
            )

    container.extract_source_files = StubExtractSourceFilesUseCase()

    result = runner.invoke(
        app,
        ["index", "extract-sources", "snapshot-123", "--output-format", "json"],
        obj=container,
    )

    payload = json.loads(result.stdout.splitlines()[-1])

    assert result.exit_code == 27
    assert payload["ok"] is False
    assert payload["error"]["code"] == "snapshot_source_mismatch"
    assert payload["meta"]["command"] == "index.extract-sources"


def test_index_build_chunks_command_renders_text_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubBuildChunksUseCase:
        def execute(self, _request: object) -> BuildChunksResult:
            return build_chunk_result(target_repo.resolve())

    container.build_chunks = StubBuildChunksUseCase()

    result = runner.invoke(
        app,
        ["index", "build-chunks", "snapshot-123"],
        obj=container,
    )

    assert result.exit_code == 0, result.stdout
    assert "Generated retrieval chunks: 2 chunks" in result.stdout
    assert "Files using fallback: 1" in result.stdout


def test_index_build_chunks_command_returns_json_failure_for_missing_inventory(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubBuildChunksUseCase:
        def execute(self, _request: object) -> object:
            raise SourceInventoryMissingError(
                "Source inventory is missing for snapshot; run "
                "`codeman index extract-sources snapshot-123` first.",
            )

    container.build_chunks = StubBuildChunksUseCase()

    result = runner.invoke(
        app,
        ["index", "build-chunks", "snapshot-123", "--output-format", "json"],
        obj=container,
    )

    payload = json.loads(result.stdout.splitlines()[-1])

    assert result.exit_code == 29
    assert payload["ok"] is False
    assert payload["error"]["code"] == "source_inventory_missing"
    assert payload["meta"]["command"] == "index.build-chunks"


def test_index_reindex_command_renders_text_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubReindexRepositoryUseCase:
        def execute(self, _request: object) -> ReindexRepositoryResult:
            return build_reindex_result(target_repo.resolve())

    container.reindex_repository = StubReindexRepositoryUseCase()

    result = runner.invoke(
        app,
        ["index", "reindex", "repo-123"],
        obj=container,
    )

    assert result.exit_code == 0, result.stdout
    assert "Re-indexed repository: registered-repo" in result.stdout
    assert "Change reason: source_changed" in result.stdout
    assert "Chunks rebuilt: 1" in result.stdout


def test_index_reindex_command_returns_json_failure_for_missing_baseline(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubReindexRepositoryUseCase:
        def execute(self, _request: object) -> object:
            raise IndexedBaselineMissingError(
                "No indexed baseline exists yet for this repository; complete the initial "
                "`repo snapshot -> index extract-sources -> index build-chunks` flow first.",
            )

    container.reindex_repository = StubReindexRepositoryUseCase()

    result = runner.invoke(
        app,
        ["index", "reindex", "repo-123", "--output-format", "json"],
        obj=container,
    )

    payload = json.loads(result.stdout.splitlines()[-1])

    assert result.exit_code == 32
    assert payload["ok"] is False
    assert payload["error"]["code"] == "indexed_baseline_missing"
    assert payload["meta"]["command"] == "index.reindex"


def test_index_build_lexical_command_renders_text_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubBuildLexicalIndexUseCase:
        def execute(self, _request: object) -> BuildLexicalIndexResult:
            return build_lexical_result(target_repo.resolve())

    container.build_lexical_index = StubBuildLexicalIndexUseCase()

    result = runner.invoke(
        app,
        ["index", "build-lexical", "snapshot-123"],
        obj=container,
    )

    assert result.exit_code == 0, result.stdout
    assert "Built lexical index: 2 chunks" in result.stdout
    assert "Lexical engine: sqlite-fts5" in result.stdout
    assert "Tokenizer: unicode61 remove_diacritics 0 tokenchars '_'" in result.stdout


def test_index_build_lexical_command_returns_json_failure_for_missing_baseline(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubBuildLexicalIndexUseCase:
        def execute(self, _request: object) -> object:
            raise ChunkBaselineMissingError(
                "Chunk baseline is missing for snapshot; run "
                "`codeman index build-chunks snapshot-123` first.",
            )

    container.build_lexical_index = StubBuildLexicalIndexUseCase()

    result = runner.invoke(
        app,
        ["index", "build-lexical", "snapshot-123", "--output-format", "json"],
        obj=container,
    )

    payload = json.loads(result.stdout.splitlines()[-1])

    assert result.exit_code == 34
    assert payload["ok"] is False
    assert payload["error"]["code"] == "chunk_baseline_missing"
    assert payload["meta"]["command"] == "index.build-lexical"


def test_index_build_semantic_command_renders_text_summary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_repo = tmp_path / "registered-repo"
    target_repo.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubBuildSemanticIndexUseCase:
        def execute(self, _request: object) -> BuildSemanticIndexResult:
            return build_semantic_result(target_repo.resolve())

    container.build_semantic_index = StubBuildSemanticIndexUseCase()

    result = runner.invoke(
        app,
        ["index", "build-semantic", "snapshot-123"],
        obj=container,
    )

    assert result.exit_code == 0, result.stdout
    assert "Built semantic index: 2 documents" in result.stdout
    assert "Provider: local-hash (local)" in result.stdout
    assert "Vector engine: sqlite-exact" in result.stdout


def test_index_build_semantic_command_returns_json_failure_for_missing_provider(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    container = bootstrap(workspace_root=workspace)

    class StubBuildSemanticIndexUseCase:
        def execute(self, _request: object) -> object:
            raise EmbeddingProviderUnavailableError(
                "Semantic indexing requires an explicit local embedding provider.",
                details={"provider_id": None},
            )

    container.build_semantic_index = StubBuildSemanticIndexUseCase()

    result = runner.invoke(
        app,
        ["index", "build-semantic", "snapshot-123", "--output-format", "json"],
        obj=container,
    )

    payload = json.loads(result.stdout.splitlines()[-1])

    assert result.exit_code == 37
    assert payload["ok"] is False
    assert payload["error"]["code"] == "embedding_provider_unavailable"
    assert payload["error"]["details"]["provider_id"] is None
    assert payload["meta"]["command"] == "index.build-semantic"

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codeman.application.query.format_results import (
    ResolvedLexicalMatch,
    RetrievalResultFormatter,
)
from codeman.contracts.chunking import ChunkPayloadDocument, ChunkRecord
from codeman.contracts.repository import RepositoryRecord, SnapshotRecord
from codeman.contracts.retrieval import (
    LexicalIndexBuildRecord,
    LexicalQueryDiagnostics,
    LexicalQueryMatch,
)


def build_repository_record(repository_path: Path) -> RepositoryRecord:
    now = datetime.now(UTC)
    return RepositoryRecord(
        repository_id="repo-123",
        repository_name=repository_path.name,
        canonical_path=repository_path,
        requested_path=repository_path,
        created_at=now,
        updated_at=now,
    )


def build_snapshot_record(repository_id: str, workspace: Path) -> SnapshotRecord:
    now = datetime.now(UTC)
    return SnapshotRecord(
        snapshot_id="snapshot-123",
        repository_id=repository_id,
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        manifest_path=workspace / ".codeman" / "artifacts" / "manifest.json",
        created_at=now,
        source_inventory_extracted_at=now,
        chunk_generation_completed_at=now,
        indexing_config_fingerprint="fingerprint-123",
    )


def build_index_record(workspace: Path, repository_id: str) -> LexicalIndexBuildRecord:
    return LexicalIndexBuildRecord(
        build_id="build-123",
        repository_id=repository_id,
        snapshot_id="snapshot-123",
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        indexing_config_fingerprint="fingerprint-123",
        lexical_engine="sqlite-fts5",
        tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
        indexed_fields=["content", "relative_path"],
        chunks_indexed=3,
        index_path=workspace / ".codeman" / "indexes" / "lexical.sqlite3",
        created_at=datetime.now(UTC),
    )


def build_resolved_match(*, content: str) -> ResolvedLexicalMatch:
    now = datetime.now(UTC)
    return ResolvedLexicalMatch(
        match=LexicalQueryMatch(
            chunk_id="chunk-1",
            relative_path="src/Controller/HomeController.php",
            language="php",
            strategy="php_structure",
            score=-1.25,
            rank=1,
            path_match_context="src/Controller/[HomeController].php",
            content_match_context="final class [HomeController] { ... }",
            path_match_highlighted=True,
            content_match_highlighted=True,
        ),
        chunk=ChunkRecord(
            chunk_id="chunk-1",
            snapshot_id="snapshot-123",
            repository_id="repo-123",
            source_file_id="source-123",
            relative_path="src/Controller/HomeController.php",
            language="php",
            strategy="php_structure",
            serialization_version="1",
            source_content_hash="hash-123",
            start_line=4,
            end_line=10,
            start_byte=32,
            end_byte=180,
            payload_path=Path(".codeman/artifacts/snapshots/snapshot-123/chunks/chunk-1.json"),
            created_at=now,
        ),
        payload=ChunkPayloadDocument(
            chunk_id="chunk-1",
            snapshot_id="snapshot-123",
            repository_id="repo-123",
            source_file_id="source-123",
            relative_path="src/Controller/HomeController.php",
            language="php",
            strategy="php_structure",
            serialization_version="1",
            source_content_hash="hash-123",
            start_line=4,
            end_line=10,
            start_byte=32,
            end_byte=180,
            content=content,
        ),
    )


def test_formatter_builds_shared_agent_friendly_retrieval_package(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    build = build_index_record(workspace, repository.repository_id)
    formatter = RetrievalResultFormatter(preview_char_limit=72)

    result = formatter.format_lexical_results(
        repository=repository,
        snapshot=snapshot,
        build=build,
        query_text="HomeController",
        diagnostics=LexicalQueryDiagnostics(match_count=1, query_latency_ms=5),
        matches=[
            build_resolved_match(
                content=(
                    "final class HomeController { public function __invoke(): string "
                    "{ return 'home'; } }"
                ),
            )
        ],
    )

    assert result.retrieval_mode == "lexical"
    assert result.query.text == "HomeController"
    assert result.repository.repository_id == repository.repository_id
    assert result.snapshot.snapshot_id == snapshot.snapshot_id
    assert result.build.build_id == build.build_id
    assert result.diagnostics.match_count == 1
    assert len(result.results) == 1
    assert result.results[0].chunk_id == "chunk-1"
    assert result.results[0].start_line == 4
    assert result.results[0].end_byte == 180
    assert result.results[0].content_preview.endswith("...")
    assert len(result.results[0].content_preview) <= 72
    assert "src/Controller/[HomeController].php" in result.results[0].explanation
    assert "final class [HomeController]" in result.results[0].explanation


def test_formatter_ignores_plain_brackets_without_highlight_markers(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    build = build_index_record(workspace, repository.repository_id)
    formatter = RetrievalResultFormatter()
    resolved = build_resolved_match(
        content="const items = [1, 2, 3]; return items[0];",
    )
    resolved = ResolvedLexicalMatch(
        match=resolved.match.model_copy(
            update={
                "content_match_context": "const items = [1, 2, 3]; return items[0];",
                "content_match_highlighted": False,
            }
        ),
        chunk=resolved.chunk,
        payload=resolved.payload,
    )

    result = formatter.format_lexical_results(
        repository=repository,
        snapshot=snapshot,
        build=build,
        query_text="HomeController",
        diagnostics=LexicalQueryDiagnostics(match_count=1, query_latency_ms=5),
        matches=[resolved],
    )

    assert result.results[0].explanation == (
        "Matched lexical terms in path src/Controller/[HomeController].php."
    )


def test_formatter_returns_empty_results_without_extra_noise(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    repository_path = tmp_path / "registered-repo"
    repository_path.mkdir()
    repository = build_repository_record(repository_path.resolve())
    snapshot = build_snapshot_record(repository.repository_id, workspace)
    build = build_index_record(workspace, repository.repository_id)
    formatter = RetrievalResultFormatter()

    result = formatter.format_lexical_results(
        repository=repository,
        snapshot=snapshot,
        build=build,
        query_text="missing-symbol",
        diagnostics=LexicalQueryDiagnostics(
            match_count=0,
            query_latency_ms=2,
            total_match_count=0,
            truncated=False,
        ),
        matches=[],
    )

    assert result.retrieval_mode == "lexical"
    assert result.results == []
    assert result.diagnostics.match_count == 0

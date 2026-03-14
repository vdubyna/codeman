from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codeman.contracts.retrieval import LexicalIndexBuildRecord, LexicalIndexDocument
from codeman.infrastructure.indexes.lexical.sqlite_fts5_builder import (
    SqliteFts5LexicalIndexBuilder,
)
from codeman.infrastructure.indexes.lexical.sqlite_fts5_query_engine import (
    SqliteFts5LexicalQueryEngine,
)
from codeman.runtime import build_runtime_paths


def build_documents() -> list[LexicalIndexDocument]:
    return [
        LexicalIndexDocument(
            chunk_id="chunk-2",
            snapshot_id="snapshot-123",
            repository_id="repo-123",
            relative_path="src/Controller/HomeController.php",
            language="php",
            strategy="php_structure",
            content="final class HomeController { public function bootValue() {} }",
        ),
        LexicalIndexDocument(
            chunk_id="chunk-1",
            snapshot_id="snapshot-123",
            repository_id="repo-123",
            relative_path="assets/app.js",
            language="javascript",
            strategy="javascript_structure",
            content="export function snake_case() { return bootValue(); }",
        ),
        LexicalIndexDocument(
            chunk_id="chunk-3",
            snapshot_id="snapshot-123",
            repository_id="repo-123",
            relative_path="templates/page.html.twig",
            language="twig",
            strategy="twig_structure",
            content="{{ include('partials/card.html.twig') }}",
        ),
    ]


def build_record(index_path: Path) -> LexicalIndexBuildRecord:
    return LexicalIndexBuildRecord(
        build_id="build-123",
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        revision_identity="revision-abc",
        revision_source="filesystem_fingerprint",
        indexing_config_fingerprint="fingerprint-123",
        lexical_engine="sqlite-fts5",
        tokenizer_spec="unicode61 remove_diacritics 0 tokenchars '_'",
        indexed_fields=["content", "relative_path"],
        chunks_indexed=3,
        index_path=index_path,
        created_at=datetime.now(UTC),
    )


def test_sqlite_fts5_query_engine_matches_symbols_paths_and_safe_punctuation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    builder = SqliteFts5LexicalIndexBuilder(runtime_paths=runtime_paths)
    engine = SqliteFts5LexicalQueryEngine()

    artifact = builder.build(
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        documents=build_documents(),
    )
    build = build_record(artifact.index_path)

    snake_case_result = engine.query(build=build, query_text="snake_case")
    path_result = engine.query(
        build=build,
        query_text="src/Controller/HomeController.php",
    )
    punctuation_result = engine.query(build=build, query_text="bootValue()")

    assert [match.chunk_id for match in snake_case_result.matches] == ["chunk-1"]
    assert [match.chunk_id for match in path_result.matches] == ["chunk-2"]
    assert [match.chunk_id for match in punctuation_result.matches] == [
        "chunk-1",
        "chunk-2",
    ]
    assert punctuation_result.diagnostics.match_count == 2


def test_sqlite_fts5_query_engine_orders_ties_by_chunk_id(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime_paths = build_runtime_paths(workspace)
    builder = SqliteFts5LexicalIndexBuilder(runtime_paths=runtime_paths)
    engine = SqliteFts5LexicalQueryEngine()

    artifact = builder.build(
        repository_id="repo-123",
        snapshot_id="snapshot-123",
        documents=[
            LexicalIndexDocument(
                chunk_id="chunk-b",
                snapshot_id="snapshot-123",
                repository_id="repo-123",
                relative_path="assets/second.js",
                language="javascript",
                strategy="javascript_structure",
                content="bootValue",
            ),
            LexicalIndexDocument(
                chunk_id="chunk-a",
                snapshot_id="snapshot-123",
                repository_id="repo-123",
                relative_path="assets/first.js",
                language="javascript",
                strategy="javascript_structure",
                content="bootValue",
            ),
        ],
    )
    build = build_record(artifact.index_path)

    result = engine.query(build=build, query_text="bootValue")

    assert [match.chunk_id for match in result.matches] == ["chunk-a", "chunk-b"]
    assert [match.rank for match in result.matches] == [1, 2]

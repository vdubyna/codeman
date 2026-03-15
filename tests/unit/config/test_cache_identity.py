from __future__ import annotations

from codeman.application.indexing.chunk_materializer import build_chunk_id
from codeman.config.cache_identity import (
    build_chunk_cache_key,
    build_embedding_cache_key,
    build_normalized_chunk_identity,
    build_parser_cache_key,
)
from codeman.contracts.retrieval import SemanticSourceDocument


def build_source_document(
    *,
    chunk_id: str,
    snapshot_id: str,
    source_file_id: str,
    serialization_version: str = "1",
    model_content: str = 'export function boot() { return "codeman"; }',
) -> SemanticSourceDocument:
    return SemanticSourceDocument(
        chunk_id=chunk_id,
        snapshot_id=snapshot_id,
        repository_id="repo-123",
        source_file_id=source_file_id,
        relative_path="assets/app.js",
        language="javascript",
        strategy="javascript_structure",
        serialization_version=serialization_version,
        source_content_hash="hash-app",
        start_line=1,
        end_line=3,
        start_byte=0,
        end_byte=42,
        content=model_content,
    )


def test_parser_and_chunk_cache_keys_are_stable_for_identical_inputs() -> None:
    parser_first = build_parser_cache_key(
        language="javascript",
        relative_path="assets/app.js",
        source_content_hash="hash-app",
        parser_policy_id="javascript-parser-v1",
    )
    parser_second = build_parser_cache_key(
        language="javascript",
        relative_path="assets/app.js",
        source_content_hash="hash-app",
        parser_policy_id="javascript-parser-v1",
    )
    chunk_first = build_chunk_cache_key(
        language="javascript",
        relative_path="assets/app.js",
        source_content_hash="hash-app",
        indexing_config_fingerprint="index-fp-1",
    )
    chunk_second = build_chunk_cache_key(
        language="javascript",
        relative_path="assets/app.js",
        source_content_hash="hash-app",
        indexing_config_fingerprint="index-fp-1",
    )

    assert parser_first == parser_second
    assert chunk_first == chunk_second


def test_chunk_and_embedding_cache_keys_invalidate_when_identity_changes() -> None:
    first_document = build_source_document(
        chunk_id="chunk-1",
        snapshot_id="snapshot-1",
        source_file_id="source-1",
    )
    second_document = build_source_document(
        chunk_id="chunk-1",
        snapshot_id="snapshot-1",
        source_file_id="source-1",
        serialization_version="2",
    )

    first_chunk_key = build_chunk_cache_key(
        language="javascript",
        relative_path="assets/app.js",
        source_content_hash="hash-app",
        indexing_config_fingerprint="index-fp-1",
    )
    changed_chunk_key = build_chunk_cache_key(
        language="javascript",
        relative_path="assets/app.js",
        source_content_hash="hash-app",
        indexing_config_fingerprint="index-fp-2",
    )
    first_embedding_key = build_embedding_cache_key(
        semantic_config_fingerprint="semantic-fp-1",
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="1",
        vector_dimension=8,
        normalized_chunks=[build_normalized_chunk_identity(first_document)],
    )
    changed_embedding_key = build_embedding_cache_key(
        semantic_config_fingerprint="semantic-fp-1",
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="2",
        vector_dimension=8,
        normalized_chunks=[build_normalized_chunk_identity(second_document)],
    )

    assert first_chunk_key != changed_chunk_key
    assert first_embedding_key != changed_embedding_key


def test_normalized_chunk_identity_stays_reusable_across_snapshots_even_when_chunk_id_changes() -> (
    None
):
    first_chunk_id = build_chunk_id(
        source_file_id="snapshot-1:assets/app.js",
        strategy="javascript_structure",
        start_line=1,
        end_line=3,
        start_byte=0,
        end_byte=42,
    )
    second_chunk_id = build_chunk_id(
        source_file_id="snapshot-2:assets/app.js",
        strategy="javascript_structure",
        start_line=1,
        end_line=3,
        start_byte=0,
        end_byte=42,
    )
    first_document = build_source_document(
        chunk_id=first_chunk_id,
        snapshot_id="snapshot-1",
        source_file_id="snapshot-1:assets/app.js",
    )
    second_document = build_source_document(
        chunk_id=second_chunk_id,
        snapshot_id="snapshot-2",
        source_file_id="snapshot-2:assets/app.js",
    )

    assert first_chunk_id != second_chunk_id
    assert build_normalized_chunk_identity(first_document) == build_normalized_chunk_identity(
        second_document
    )

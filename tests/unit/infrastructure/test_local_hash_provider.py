from __future__ import annotations

from pathlib import Path

from codeman.contracts.retrieval import EmbeddingProviderDescriptor, SemanticSourceDocument
from codeman.infrastructure.embeddings.local_hash_provider import (
    DeterministicLocalHashEmbeddingProvider,
)


def build_source_document(*, chunk_id: str, content: str) -> SemanticSourceDocument:
    return SemanticSourceDocument(
        chunk_id=chunk_id,
        snapshot_id="snapshot-123",
        repository_id="repo-123",
        source_file_id=f"{chunk_id}-source",
        relative_path="assets/app.js",
        language="javascript",
        strategy="javascript_structure",
        serialization_version="1",
        source_content_hash=f"hash-{chunk_id}",
        start_line=1,
        end_line=3,
        start_byte=0,
        end_byte=42,
        content=content,
    )


def test_local_hash_provider_is_deterministic(tmp_path: Path) -> None:
    provider = DeterministicLocalHashEmbeddingProvider()
    descriptor = EmbeddingProviderDescriptor(
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="1",
        is_external_provider=False,
        local_model_path=(tmp_path / "local-model").resolve(),
    )
    documents = [
        build_source_document(
            chunk_id="chunk-123",
            content='export function boot() { return "codeman"; }',
        )
    ]

    first = provider.embed(provider=descriptor, documents=documents, vector_dimension=8)
    second = provider.embed(provider=descriptor, documents=documents, vector_dimension=8)

    assert first == second
    assert len(first[0].embedding) == 8


def test_local_hash_provider_changes_vector_when_content_changes(tmp_path: Path) -> None:
    provider = DeterministicLocalHashEmbeddingProvider()
    descriptor = EmbeddingProviderDescriptor(
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="1",
        is_external_provider=False,
        local_model_path=(tmp_path / "local-model").resolve(),
    )
    first_documents = [
        build_source_document(
            chunk_id="chunk-123",
            content='export function boot() { return "codeman"; }',
        )
    ]
    second_documents = [
        build_source_document(
            chunk_id="chunk-123",
            content='export function boot() { return "fresh"; }',
        )
    ]

    first = provider.embed(provider=descriptor, documents=first_documents, vector_dimension=8)
    second = provider.embed(provider=descriptor, documents=second_documents, vector_dimension=8)

    assert first[0].embedding != second[0].embedding

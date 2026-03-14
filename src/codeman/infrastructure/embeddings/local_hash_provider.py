"""Deterministic local embedding provider for semantic indexing tests and local builds."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Sequence

from codeman.application.ports.embedding_provider_port import EmbeddingProviderPort
from codeman.contracts.retrieval import (
    EmbeddingProviderDescriptor,
    SemanticEmbeddingDocument,
    SemanticQueryEmbedding,
    SemanticSourceDocument,
)


def _expanded_digest(seed: bytes, required_bytes: int) -> bytes:
    chunks: list[bytes] = []
    counter = 0
    while sum(len(chunk) for chunk in chunks) < required_bytes:
        chunks.append(hashlib.sha256(seed + counter.to_bytes(4, "big")).digest())
        counter += 1
    return b"".join(chunks)[:required_bytes]


def _normalize(values: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in values))
    if magnitude == 0:
        return [0.0 for _ in values]
    return [round(value / magnitude, 8) for value in values]


@dataclass(slots=True)
class DeterministicLocalHashEmbeddingProvider(EmbeddingProviderPort):
    """Produce deterministic local embeddings without network or model downloads."""

    def embed(
        self,
        *,
        provider: EmbeddingProviderDescriptor,
        documents: Sequence[SemanticSourceDocument],
        vector_dimension: int,
    ) -> list[SemanticEmbeddingDocument]:
        """Return deterministic unit-length embeddings for source documents."""

        return [
            SemanticEmbeddingDocument(
                chunk_id=document.chunk_id,
                snapshot_id=document.snapshot_id,
                repository_id=document.repository_id,
                source_file_id=document.source_file_id,
                relative_path=document.relative_path,
                language=document.language,
                strategy=document.strategy,
                serialization_version=document.serialization_version,
                source_content_hash=document.source_content_hash,
                start_line=document.start_line,
                end_line=document.end_line,
                start_byte=document.start_byte,
                end_byte=document.end_byte,
                content=document.content,
                provider_id=provider.provider_id,
                model_id=provider.model_id,
                model_version=provider.model_version,
                vector_dimension=vector_dimension,
                embedding=self._build_embedding(
                    provider=provider,
                    document=document,
                    vector_dimension=vector_dimension,
                ),
            )
            for document in documents
        ]

    def embed_query(
        self,
        *,
        provider: EmbeddingProviderDescriptor,
        query_text: str,
        vector_dimension: int,
    ) -> SemanticQueryEmbedding:
        """Return a deterministic query embedding without inventing document metadata."""

        return SemanticQueryEmbedding(
            provider_id=provider.provider_id,
            model_id=provider.model_id,
            model_version=provider.model_version,
            vector_dimension=vector_dimension,
            embedding=self._build_query_embedding(
                provider=provider,
                query_text=query_text,
                vector_dimension=vector_dimension,
            ),
        )

    @staticmethod
    def _build_embedding(
        *,
        provider: EmbeddingProviderDescriptor,
        document: SemanticSourceDocument,
        vector_dimension: int,
    ) -> list[float]:
        seed = "\0".join(
            [
                provider.provider_id,
                provider.model_id,
                provider.model_version,
                str(provider.local_model_path) if provider.local_model_path is not None else "",
                document.chunk_id,
                document.source_content_hash,
                document.content,
            ],
        ).encode("utf-8")
        raw = _expanded_digest(seed, vector_dimension * 4)
        values = [
            (int.from_bytes(raw[index : index + 4], "big") / 2**31) - 1.0
            for index in range(0, len(raw), 4)
        ]
        return _normalize(values[:vector_dimension])

    @staticmethod
    def _build_query_embedding(
        *,
        provider: EmbeddingProviderDescriptor,
        query_text: str,
        vector_dimension: int,
    ) -> list[float]:
        seed = "\0".join(
            [
                provider.provider_id,
                provider.model_id,
                provider.model_version,
                str(provider.local_model_path) if provider.local_model_path is not None else "",
                "semantic-query",
                query_text,
            ],
        ).encode("utf-8")
        raw = _expanded_digest(seed, vector_dimension * 4)
        values = [
            (int.from_bytes(raw[index : index + 4], "big") / 2**31) - 1.0
            for index in range(0, len(raw), 4)
        ]
        return _normalize(values[:vector_dimension])

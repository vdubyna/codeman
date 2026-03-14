from __future__ import annotations

import math
from pathlib import Path

import pytest

from codeman.contracts.retrieval import EmbeddingProviderDescriptor
from codeman.infrastructure.embeddings.local_hash_provider import (
    DeterministicLocalHashEmbeddingProvider,
)


def test_local_hash_provider_generates_deterministic_query_embedding(tmp_path: Path) -> None:
    provider = DeterministicLocalHashEmbeddingProvider()
    descriptor = EmbeddingProviderDescriptor(
        provider_id="local-hash",
        model_id="fixture-local",
        model_version="2026-03-14",
        local_model_path=tmp_path / "local-model",
    )

    first = provider.embed_query(
        provider=descriptor,
        query_text="controller home route",
        vector_dimension=8,
    )
    second = provider.embed_query(
        provider=descriptor,
        query_text="controller home route",
        vector_dimension=8,
    )

    magnitude = math.sqrt(sum(value * value for value in first.embedding))

    assert first == second
    assert first.provider_id == "local-hash"
    assert first.model_version == "2026-03-14"
    assert first.vector_dimension == 8
    assert len(first.embedding) == 8
    assert magnitude == pytest.approx(1.0, abs=1e-7)

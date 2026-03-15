"""Port for reusable runtime cache artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from codeman.contracts.cache import (
    ChunkCacheArtifactDocument,
    EmbeddingCacheArtifactDocument,
    ParserCacheArtifactDocument,
)


class CacheStorePort(Protocol):
    """Filesystem-backed cache persistence boundary."""

    def write_parser_cache(self, artifact: ParserCacheArtifactDocument) -> Path:
        """Persist one reusable parser artifact and return its path."""

    def read_parser_cache(self, cache_key: str) -> ParserCacheArtifactDocument | None:
        """Load one reusable parser artifact by cache key."""

    def write_chunk_cache(self, artifact: ChunkCacheArtifactDocument) -> Path:
        """Persist one reusable chunk artifact and return its path."""

    def read_chunk_cache(self, cache_key: str) -> ChunkCacheArtifactDocument | None:
        """Load one reusable chunk artifact by cache key."""

    def write_embedding_cache(self, artifact: EmbeddingCacheArtifactDocument) -> Path:
        """Persist one reusable embedding artifact and return its path."""

    def read_embedding_cache(self, cache_key: str) -> EmbeddingCacheArtifactDocument | None:
        """Load one reusable embedding artifact by cache key."""

"""Persist reusable cache artifacts under `.codeman/cache/`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codeman.application.ports.cache_store_port import CacheStorePort
from codeman.contracts.cache import (
    ChunkCacheArtifactDocument,
    EmbeddingCacheArtifactDocument,
    ParserCacheArtifactDocument,
)


@dataclass(slots=True)
class FilesystemCacheStore(CacheStorePort):
    """Store reusable parser, chunk, and embedding artifacts on disk."""

    cache_root: Path

    def write_parser_cache(self, artifact: ParserCacheArtifactDocument) -> Path:
        destination = self._artifact_path("parser", artifact.cache_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
        return destination

    def read_parser_cache(self, cache_key: str) -> ParserCacheArtifactDocument | None:
        destination = self._artifact_path("parser", cache_key)
        if not destination.exists():
            return None
        return ParserCacheArtifactDocument.model_validate_json(
            destination.read_text(encoding="utf-8"),
        )

    def write_chunk_cache(self, artifact: ChunkCacheArtifactDocument) -> Path:
        destination = self._artifact_path("chunk", artifact.cache_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
        return destination

    def read_chunk_cache(self, cache_key: str) -> ChunkCacheArtifactDocument | None:
        destination = self._artifact_path("chunk", cache_key)
        if not destination.exists():
            return None
        return ChunkCacheArtifactDocument.model_validate_json(
            destination.read_text(encoding="utf-8"),
        )

    def write_embedding_cache(self, artifact: EmbeddingCacheArtifactDocument) -> Path:
        destination = self._artifact_path("embedding", artifact.cache_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
        return destination

    def read_embedding_cache(self, cache_key: str) -> EmbeddingCacheArtifactDocument | None:
        destination = self._artifact_path("embedding", cache_key)
        if not destination.exists():
            return None
        return EmbeddingCacheArtifactDocument.model_validate_json(
            destination.read_text(encoding="utf-8"),
        )

    def _artifact_path(self, kind: str, cache_key: str) -> Path:
        return self.cache_root / kind / f"{cache_key}.json"

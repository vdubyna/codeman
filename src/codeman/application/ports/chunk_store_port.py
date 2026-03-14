"""Persistence port for generated chunk metadata."""

from __future__ import annotations

from typing import Protocol, Sequence

from codeman.contracts.chunking import ChunkRecord


class ChunkStorePort(Protocol):
    """Persistence boundary for retrieval chunk metadata."""

    def initialize(self) -> None:
        """Prepare chunk metadata persistence for use."""

    def upsert_chunks(self, chunks: Sequence[ChunkRecord]) -> list[ChunkRecord]:
        """Persist chunk metadata rows without duplicating deterministic chunks."""

    def list_by_snapshot(self, snapshot_id: str) -> list[ChunkRecord]:
        """Return chunk rows for a snapshot ordered by path and span."""

    def get_by_chunk_ids(self, chunk_ids: Sequence[str]) -> list[ChunkRecord]:
        """Return chunk rows for the provided ids in the same order they were requested."""

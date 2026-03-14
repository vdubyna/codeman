"""Port for building lexical index artifacts."""

from __future__ import annotations

from typing import Protocol, Sequence

from codeman.contracts.retrieval import LexicalIndexArtifact, LexicalIndexDocument


class LexicalIndexPort(Protocol):
    """Boundary for adapter-owned lexical artifact construction."""

    def build(
        self,
        *,
        repository_id: str,
        snapshot_id: str,
        documents: Sequence[LexicalIndexDocument],
    ) -> LexicalIndexArtifact:
        """Build and persist lexical artifacts for one snapshot."""

"""Port for executing lexical queries against persisted index artifacts."""

from __future__ import annotations

from typing import Protocol

from codeman.contracts.retrieval import (
    LexicalIndexBuildRecord,
    LexicalQueryResult,
)


class LexicalQueryPort(Protocol):
    """Adapter boundary for repository-scoped lexical query execution."""

    def query(
        self,
        *,
        build: LexicalIndexBuildRecord,
        query_text: str,
    ) -> LexicalQueryResult:
        """Execute one lexical query against the provided build artifact."""

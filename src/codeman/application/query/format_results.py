"""Shared enrichment and formatting for retrieval result packages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from codeman.contracts.chunking import ChunkPayloadDocument, ChunkRecord
from codeman.contracts.repository import RepositoryRecord, SnapshotRecord
from codeman.contracts.retrieval import (
    LexicalIndexBuildRecord,
    LexicalQueryDiagnostics,
    LexicalQueryMatch,
    RetrievalBuildContext,
    RetrievalQueryMetadata,
    RetrievalRepositoryContext,
    RetrievalResultItem,
    RetrievalSnapshotContext,
    RunLexicalQueryResult,
)

__all__ = [
    "ResolvedLexicalMatch",
    "RetrievalResultFormatter",
]


@dataclass(slots=True, frozen=True)
class ResolvedLexicalMatch:
    """One lexical match resolved to persisted chunk metadata and payload content."""

    match: LexicalQueryMatch
    chunk: ChunkRecord
    payload: ChunkPayloadDocument


@dataclass(slots=True)
class RetrievalResultFormatter:
    """Format enriched retrieval data into a shared agent-friendly package."""

    preview_char_limit: int = 180
    evidence_char_limit: int = 140

    def format_lexical_results(
        self,
        *,
        repository: RepositoryRecord,
        snapshot: SnapshotRecord,
        build: LexicalIndexBuildRecord,
        query_text: str,
        diagnostics: LexicalQueryDiagnostics,
        matches: Sequence[ResolvedLexicalMatch],
    ) -> RunLexicalQueryResult:
        """Build the shared lexical retrieval package from enriched match inputs."""

        return RunLexicalQueryResult(
            query=RetrievalQueryMetadata(text=query_text),
            repository=RetrievalRepositoryContext(
                repository_id=repository.repository_id,
                repository_name=repository.repository_name,
            ),
            snapshot=RetrievalSnapshotContext(
                snapshot_id=snapshot.snapshot_id,
                revision_identity=snapshot.revision_identity,
                revision_source=snapshot.revision_source,
            ),
            build=RetrievalBuildContext(
                build_id=build.build_id,
                lexical_engine=build.lexical_engine,
                tokenizer_spec=build.tokenizer_spec,
                indexed_fields=list(build.indexed_fields),
            ),
            results=[self._format_match(match) for match in matches],
            diagnostics=diagnostics,
        )

    def _format_match(self, resolved: ResolvedLexicalMatch) -> RetrievalResultItem:
        return RetrievalResultItem(
            chunk_id=resolved.match.chunk_id,
            relative_path=resolved.chunk.relative_path,
            language=resolved.chunk.language,
            strategy=resolved.chunk.strategy,
            rank=resolved.match.rank,
            score=resolved.match.score,
            start_line=resolved.chunk.start_line,
            end_line=resolved.chunk.end_line,
            start_byte=resolved.chunk.start_byte,
            end_byte=resolved.chunk.end_byte,
            content_preview=self._truncate(
                self._normalize_whitespace(resolved.payload.content),
                limit=self.preview_char_limit,
            ),
            explanation=self._build_explanation(resolved.match),
        )

    def _build_explanation(self, match: LexicalQueryMatch) -> str:
        contexts: list[str] = []
        path_context = self._context_if_highlighted(
            match.path_match_context,
            highlighted=match.path_match_highlighted,
        )
        content_context = self._context_if_highlighted(
            match.content_match_context,
            highlighted=match.content_match_highlighted,
        )

        if path_context is not None:
            contexts.append(f"path {path_context}")
        if content_context is not None:
            contexts.append(f"content {content_context}")
        if not contexts:
            return "Matched persisted lexical evidence for this ranked chunk."
        if len(contexts) == 1:
            return f"Matched lexical terms in {contexts[0]}."
        return f"Matched lexical terms in {contexts[0]} and {contexts[1]}."

    def _context_if_highlighted(
        self,
        value: str | None,
        *,
        highlighted: bool,
    ) -> str | None:
        if value is None or not highlighted:
            return None
        normalized = self._truncate(
            self._normalize_whitespace(value),
            limit=self.evidence_char_limit,
        )
        return normalized

    @staticmethod
    def _normalize_whitespace(value: str) -> str:
        return " ".join(value.split())

    @staticmethod
    def _truncate(value: str, *, limit: int) -> str:
        if len(value) <= limit:
            return value
        if limit <= 3:
            return value[:limit]
        return value[: limit - 3].rstrip() + "..."

"""Shared enrichment and formatting for retrieval result packages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from codeman.contracts.chunking import ChunkPayloadDocument, ChunkRecord
from codeman.contracts.repository import RepositoryRecord, SnapshotRecord
from codeman.contracts.retrieval import (
    HybridQueryDiagnostics,
    HybridRetrievalBuildContext,
    LexicalIndexBuildRecord,
    LexicalQueryDiagnostics,
    LexicalQueryMatch,
    LexicalRetrievalBuildContext,
    RetrievalQueryMetadata,
    RetrievalRepositoryContext,
    RetrievalResultItem,
    RetrievalSnapshotContext,
    RunHybridQueryResult,
    RunLexicalQueryResult,
    RunSemanticQueryResult,
    SemanticIndexBuildRecord,
    SemanticQueryDiagnostics,
    SemanticQueryMatch,
    SemanticRetrievalBuildContext,
)

__all__ = [
    "ResolvedHybridMatch",
    "ResolvedLexicalMatch",
    "ResolvedSemanticMatch",
    "RetrievalResultFormatter",
]


@dataclass(slots=True, frozen=True)
class ResolvedLexicalMatch:
    """One lexical match resolved to persisted chunk metadata and payload content."""

    match: LexicalQueryMatch
    chunk: ChunkRecord
    payload: ChunkPayloadDocument


@dataclass(slots=True, frozen=True)
class ResolvedSemanticMatch:
    """One semantic match resolved to persisted chunk metadata and payload content."""

    match: SemanticQueryMatch
    chunk: ChunkRecord
    payload: ChunkPayloadDocument


@dataclass(slots=True, frozen=True)
class ResolvedHybridMatch:
    """One fused hybrid match resolved from already formatted component results."""

    item: RetrievalResultItem
    fused_score: float
    lexical_rank: int | None
    semantic_rank: int | None


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
            build=LexicalRetrievalBuildContext(
                build_id=build.build_id,
                indexing_config_fingerprint=build.indexing_config_fingerprint,
                lexical_engine=build.lexical_engine,
                tokenizer_spec=build.tokenizer_spec,
                indexed_fields=list(build.indexed_fields),
            ),
            results=[self._format_match(match) for match in matches],
            diagnostics=diagnostics,
        )

    def format_semantic_results(
        self,
        *,
        repository: RepositoryRecord,
        snapshot: SnapshotRecord,
        build: SemanticIndexBuildRecord,
        query_text: str,
        diagnostics: SemanticQueryDiagnostics,
        matches: Sequence[ResolvedSemanticMatch],
    ) -> RunSemanticQueryResult:
        """Build the shared semantic retrieval package from enriched match inputs."""

        return RunSemanticQueryResult(
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
            build=SemanticRetrievalBuildContext(
                build_id=build.build_id,
                provider_id=build.provider_id,
                model_id=build.model_id,
                model_version=build.model_version,
                vector_engine=build.vector_engine,
                semantic_config_fingerprint=build.semantic_config_fingerprint,
            ),
            results=[self._format_semantic_match(match) for match in matches],
            diagnostics=diagnostics,
        )

    def format_hybrid_results(
        self,
        *,
        repository: RetrievalRepositoryContext | RepositoryRecord,
        snapshot: RetrievalSnapshotContext | SnapshotRecord,
        build: HybridRetrievalBuildContext,
        query_text: str,
        diagnostics: HybridQueryDiagnostics,
        matches: Sequence[ResolvedHybridMatch],
    ) -> RunHybridQueryResult:
        """Build the shared hybrid retrieval package from fused match inputs."""

        repository_context = (
            repository
            if isinstance(repository, RetrievalRepositoryContext)
            else RetrievalRepositoryContext(
                repository_id=repository.repository_id,
                repository_name=repository.repository_name,
            )
        )
        snapshot_context = (
            snapshot
            if isinstance(snapshot, RetrievalSnapshotContext)
            else RetrievalSnapshotContext(
                snapshot_id=snapshot.snapshot_id,
                revision_identity=snapshot.revision_identity,
                revision_source=snapshot.revision_source,
            )
        )
        return RunHybridQueryResult(
            query=RetrievalQueryMetadata(text=query_text),
            repository=repository_context,
            snapshot=snapshot_context,
            build=build,
            results=[
                self._format_hybrid_match(index=index, resolved=match)
                for index, match in enumerate(matches, start=1)
            ],
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

    def _format_semantic_match(self, resolved: ResolvedSemanticMatch) -> RetrievalResultItem:
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
            explanation="Ranked by embedding similarity against the persisted semantic index.",
        )

    def _format_hybrid_match(
        self,
        *,
        index: int,
        resolved: ResolvedHybridMatch,
    ) -> RetrievalResultItem:
        return RetrievalResultItem(
            chunk_id=resolved.item.chunk_id,
            relative_path=resolved.item.relative_path,
            language=resolved.item.language,
            strategy=resolved.item.strategy,
            rank=index,
            score=resolved.fused_score,
            start_line=resolved.item.start_line,
            end_line=resolved.item.end_line,
            start_byte=resolved.item.start_byte,
            end_byte=resolved.item.end_byte,
            content_preview=resolved.item.content_preview,
            explanation=self._build_hybrid_explanation(resolved),
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

    @staticmethod
    def _build_hybrid_explanation(resolved: ResolvedHybridMatch) -> str:
        if resolved.lexical_rank is not None and resolved.semantic_rank is not None:
            return "Fused hybrid rank from lexical and semantic evidence for this persisted chunk."
        if resolved.lexical_rank is not None:
            return (
                "Fused hybrid rank from lexical evidence only; semantic retrieval returned no "
                "match for this chunk."
            )
        if resolved.semantic_rank is not None:
            return (
                "Fused hybrid rank from semantic evidence only; lexical retrieval returned no "
                "match for this chunk."
            )
        return "Fused hybrid rank from persisted retrieval evidence for this chunk."

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

"""SQLite FTS5 lexical query adapter."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from time import perf_counter

from codeman.application.ports.lexical_query_port import LexicalQueryPort
from codeman.contracts.retrieval import (
    LexicalIndexBuildRecord,
    LexicalQueryDiagnostics,
    LexicalQueryMatch,
    LexicalQueryResult,
)

_HIGHLIGHT_OPEN = "<<__CODEMAN_MATCH_OPEN__>>"
_HIGHLIGHT_CLOSE = "<<__CODEMAN_MATCH_CLOSE__>>"


def _escape_fts5_literal(term: str) -> str:
    return term.replace('"', '""')


def _normalize_query_text(query_text: str) -> str:
    terms = [segment for segment in query_text.split() if segment]
    if not terms:
        raise ValueError("Query text must contain at least one searchable term.")
    return " ".join(f'"{_escape_fts5_literal(term)}"' for term in terms)


def _normalize_match_context(value: str | None) -> tuple[str | None, bool]:
    if value is None:
        return None, False

    highlighted = _HIGHLIGHT_OPEN in value and _HIGHLIGHT_CLOSE in value
    normalized = value.replace(_HIGHLIGHT_OPEN, "[").replace(_HIGHLIGHT_CLOSE, "]")
    return normalized, highlighted


@dataclass(slots=True)
class SqliteFts5LexicalQueryEngine(LexicalQueryPort):
    """Execute lexical queries against a persisted SQLite FTS5 artifact."""

    def query(
        self,
        *,
        build: LexicalIndexBuildRecord,
        query_text: str,
        max_results: int = 20,
    ) -> LexicalQueryResult:
        normalized_query = _normalize_query_text(query_text)
        started_at = perf_counter()
        connection = sqlite3.connect(build.index_path)
        try:
            total_matches = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM lexical_chunks
                    WHERE lexical_chunks MATCH ?
                    """,
                    (normalized_query,),
                ).fetchone()[0]
            )
            rows = connection.execute(
                """
                SELECT
                    chunk_id,
                    relative_path,
                    language,
                    strategy,
                    bm25(lexical_chunks) AS score,
                    highlight(
                        lexical_chunks,
                        1,
                        ?,
                        ?
                    ) AS path_match_context,
                    snippet(
                        lexical_chunks,
                        0,
                        ?,
                        ?,
                        '...',
                        12
                    ) AS content_match_context
                FROM lexical_chunks
                WHERE lexical_chunks MATCH ?
                ORDER BY rank, chunk_id
                LIMIT ?
                """,
                (
                    _HIGHLIGHT_OPEN,
                    _HIGHLIGHT_CLOSE,
                    _HIGHLIGHT_OPEN,
                    _HIGHLIGHT_CLOSE,
                    normalized_query,
                    max_results,
                ),
            ).fetchall()
        finally:
            connection.close()

        elapsed_ms = int(round((perf_counter() - started_at) * 1000))
        matches: list[LexicalQueryMatch] = []
        for index, row in enumerate(rows, start=1):
            path_context, path_highlighted = _normalize_match_context(row[5])
            content_context, content_highlighted = _normalize_match_context(row[6])
            matches.append(
                LexicalQueryMatch(
                    chunk_id=row[0],
                    relative_path=row[1],
                    language=row[2],
                    strategy=row[3],
                    score=float(row[4]),
                    rank=index,
                    path_match_context=path_context,
                    content_match_context=content_context,
                    path_match_highlighted=path_highlighted,
                    content_match_highlighted=content_highlighted,
                )
            )
        return LexicalQueryResult(
            matches=matches,
            diagnostics=LexicalQueryDiagnostics(
                match_count=len(matches),
                query_latency_ms=elapsed_ms,
                total_match_count=total_matches,
                truncated=total_matches > len(matches),
            ),
        )

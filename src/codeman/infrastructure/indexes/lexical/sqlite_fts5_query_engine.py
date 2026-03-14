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


def _escape_fts5_literal(term: str) -> str:
    return term.replace('"', '""')


def _normalize_query_text(query_text: str) -> str:
    terms = [segment for segment in query_text.split() if segment]
    if not terms:
        raise ValueError("Query text must contain at least one searchable term.")
    return " ".join(f'"{_escape_fts5_literal(term)}"' for term in terms)


@dataclass(slots=True)
class SqliteFts5LexicalQueryEngine(LexicalQueryPort):
    """Execute lexical queries against a persisted SQLite FTS5 artifact."""

    def query(
        self,
        *,
        build: LexicalIndexBuildRecord,
        query_text: str,
    ) -> LexicalQueryResult:
        normalized_query = _normalize_query_text(query_text)
        started_at = perf_counter()
        connection = sqlite3.connect(build.index_path)
        try:
            rows = connection.execute(
                """
                SELECT
                    chunk_id,
                    relative_path,
                    language,
                    strategy,
                    bm25(lexical_chunks) AS score
                FROM lexical_chunks
                WHERE lexical_chunks MATCH ?
                ORDER BY rank, chunk_id
                """,
                (normalized_query,),
            ).fetchall()
        finally:
            connection.close()

        elapsed_ms = int(round((perf_counter() - started_at) * 1000))
        matches = [
            LexicalQueryMatch(
                chunk_id=row[0],
                relative_path=row[1],
                language=row[2],
                strategy=row[3],
                score=float(row[4]),
                rank=index,
            )
            for index, row in enumerate(rows, start=1)
        ]
        return LexicalQueryResult(
            matches=matches,
            diagnostics=LexicalQueryDiagnostics(
                match_count=len(matches),
                query_latency_ms=elapsed_ms,
            ),
        )

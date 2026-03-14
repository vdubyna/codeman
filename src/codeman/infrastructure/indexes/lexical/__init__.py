"""SQLite-backed lexical index adapter."""

from codeman.infrastructure.indexes.lexical.sqlite_fts5_builder import (
    SqliteFts5LexicalIndexBuilder,
)
from codeman.infrastructure.indexes.lexical.sqlite_fts5_query_engine import (
    SqliteFts5LexicalQueryEngine,
)

__all__ = ["SqliteFts5LexicalIndexBuilder", "SqliteFts5LexicalQueryEngine"]

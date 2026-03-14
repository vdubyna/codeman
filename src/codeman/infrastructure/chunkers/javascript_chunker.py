"""JavaScript structure-aware chunker."""

from __future__ import annotations

from codeman.infrastructure.chunkers.common import BoundaryChunker


class JavascriptChunker(BoundaryChunker):
    """Generate JavaScript chunks around declaration boundaries."""

    strategy_name = "javascript_structure"

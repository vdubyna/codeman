"""HTML structure-aware chunker."""

from __future__ import annotations

from codeman.infrastructure.chunkers.common import BoundaryChunker


class HtmlChunker(BoundaryChunker):
    """Generate HTML chunks around meaningful sections."""

    strategy_name = "html_structure"

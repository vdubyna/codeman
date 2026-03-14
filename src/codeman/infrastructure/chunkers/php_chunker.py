"""PHP structure-aware chunker."""

from __future__ import annotations

from codeman.infrastructure.chunkers.common import BoundaryChunker


class PhpChunker(BoundaryChunker):
    """Generate PHP chunks around declaration boundaries."""

    strategy_name = "php_structure"

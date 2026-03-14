"""Twig structure-aware chunker."""

from __future__ import annotations

from codeman.infrastructure.chunkers.common import BoundaryChunker


class TwigChunker(BoundaryChunker):
    """Generate Twig chunks around template sections."""

    strategy_name = "twig_structure"

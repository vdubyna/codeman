"""Heuristic PHP parser for structure-aware chunking."""

from __future__ import annotations

import re

from codeman.application.ports.parser_port import ParserFailure, StructuralBoundary

_BOUNDARY_PATTERNS = (
    re.compile(r"^\s*(?:final\s+|abstract\s+)?(?:class|interface|trait)\s+\w+"),
    re.compile(
        r"^\s*(?:public|protected|private)?\s*(?:static\s+)?function\s+\w+\s*\(",
    ),
)


class PhpParser:
    """Detect PHP declaration boundaries without requiring a full AST."""

    def parse(
        self,
        *,
        source_text: str,
        relative_path: str,
    ) -> tuple[StructuralBoundary, ...]:
        """Return declaration starts for PHP files."""

        if source_text.count("{") != source_text.count("}"):
            raise ParserFailure(f"Unbalanced braces detected in PHP source: {relative_path}")

        boundaries = [
            StructuralBoundary(kind="declaration", start_line=index)
            for index, line in enumerate(source_text.splitlines(), start=1)
            if any(pattern.search(line) for pattern in _BOUNDARY_PATTERNS)
        ]
        return tuple(boundaries)

"""Heuristic JavaScript parser for structure-aware chunking."""

from __future__ import annotations

import re

from codeman.application.ports.parser_port import ParserFailure, StructuralBoundary

_BOUNDARY_PATTERNS = (
    re.compile(r"^\s*export\s+(?:default\s+)?class\s+[A-Za-z_$][\w$]*"),
    re.compile(r"^\s*class\s+[A-Za-z_$][\w$]*"),
    re.compile(r"^\s*export\s+(?:async\s+)?function\s+[A-Za-z_$][\w$]*\s*\("),
    re.compile(r"^\s*(?:async\s+)?function\s+[A-Za-z_$][\w$]*\s*\("),
)


class JavascriptParser:
    """Detect JavaScript declaration boundaries with lightweight heuristics."""

    def parse(
        self,
        *,
        source_text: str,
        relative_path: str,
    ) -> tuple[StructuralBoundary, ...]:
        """Return declaration starts for JavaScript files."""

        if source_text.count("{") != source_text.count("}"):
            raise ParserFailure(
                f"Unbalanced braces detected in JavaScript source: {relative_path}",
            )

        boundaries = [
            StructuralBoundary(kind="declaration", start_line=index)
            for index, line in enumerate(source_text.splitlines(), start=1)
            if any(pattern.search(line) for pattern in _BOUNDARY_PATTERNS)
        ]
        return tuple(boundaries)

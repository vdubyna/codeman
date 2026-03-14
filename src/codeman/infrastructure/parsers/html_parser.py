"""Heuristic HTML parser for structure-aware chunking."""

from __future__ import annotations

import re

from codeman.application.ports.parser_port import StructuralBoundary

_BOUNDARY_PATTERN = re.compile(
    r"<(?:body|main|section|article|header|footer|nav|aside|form)\b",
    re.IGNORECASE,
)


class HtmlParser:
    """Detect meaningful HTML section starts."""

    def parse(
        self,
        *,
        source_text: str,
        relative_path: str,
    ) -> tuple[StructuralBoundary, ...]:
        """Return structural tag boundaries for HTML files."""

        del relative_path
        boundaries = [
            StructuralBoundary(kind="section", start_line=index)
            for index, line in enumerate(source_text.splitlines(), start=1)
            if _BOUNDARY_PATTERN.search(line)
        ]
        return tuple(boundaries)

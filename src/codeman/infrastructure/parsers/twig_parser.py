"""Heuristic Twig parser for structure-aware chunking."""

from __future__ import annotations

import re

from codeman.application.ports.parser_port import StructuralBoundary

_BOUNDARY_PATTERN = re.compile(r"{%\s*(block|macro|embed)\b")


class TwigParser:
    """Detect Twig template section boundaries."""

    def parse(
        self,
        *,
        source_text: str,
        relative_path: str,
    ) -> tuple[StructuralBoundary, ...]:
        """Return Twig block-style boundaries."""

        del relative_path
        boundaries = [
            StructuralBoundary(kind="template-section", start_line=index)
            for index, line in enumerate(source_text.splitlines(), start=1)
            if _BOUNDARY_PATTERN.search(line)
        ]
        return tuple(boundaries)

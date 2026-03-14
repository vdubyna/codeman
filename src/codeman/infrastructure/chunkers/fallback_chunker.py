"""Bounded fallback chunker used when structural parsing cannot proceed safely."""

from __future__ import annotations

from codeman.application.ports.chunker_port import ChunkDraft
from codeman.infrastructure.chunkers.common import _build_draft


class WindowedFallbackChunker:
    """Split source files into bounded ordered windows."""

    def __init__(
        self,
        strategy_name: str,
        *,
        max_lines: int = 40,
        boundary_search_window: int = 5,
    ) -> None:
        self.strategy_name = strategy_name
        self.max_lines = max_lines
        self.boundary_search_window = boundary_search_window

    def chunk(
        self,
        *,
        source_text: str,
        relative_path: str,
        boundaries: tuple[()] = (),
    ) -> tuple[ChunkDraft, ...]:
        """Return bounded fallback chunks without relying on parser output."""

        del relative_path, boundaries
        lines = source_text.splitlines(keepends=True)
        if not lines:
            return ()

        total_lines = len(lines)
        start_line = 1
        drafts: list[ChunkDraft] = []
        while start_line <= total_lines:
            end_line = min(start_line + self.max_lines - 1, total_lines)
            if end_line < total_lines:
                search_floor = max(start_line + 1, end_line - self.boundary_search_window)
                for candidate in range(end_line, search_floor - 1, -1):
                    if not lines[candidate - 1].strip():
                        end_line = candidate
                        break

            draft = _build_draft(
                source_text=source_text,
                strategy=self.strategy_name,
                start_line=start_line,
                end_line=end_line,
            )
            if draft is not None:
                drafts.append(draft)

            next_start = end_line + 1
            if next_start <= start_line:
                next_start = min(start_line + self.max_lines, total_lines + 1)
            start_line = next_start

        return tuple(drafts)

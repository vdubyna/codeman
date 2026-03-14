"""Shared helpers for structural and fallback chunkers."""

from __future__ import annotations

from collections.abc import Sequence

from codeman.application.ports.chunker_port import ChunkDraft
from codeman.application.ports.parser_port import StructuralBoundary


def _split_lines(source_text: str) -> list[str]:
    return source_text.splitlines(keepends=True)


def _build_offsets(lines: Sequence[str]) -> tuple[list[int], int]:
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line.encode("utf-8"))
    return offsets, cursor


def _build_draft(
    *,
    source_text: str,
    strategy: str,
    start_line: int,
    end_line: int,
) -> ChunkDraft | None:
    lines = _split_lines(source_text)
    if not lines:
        return None

    normalized_start = max(1, min(start_line, len(lines)))
    normalized_end = max(normalized_start, min(end_line, len(lines)))
    offsets, total_bytes = _build_offsets(lines)
    content = "".join(lines[normalized_start - 1 : normalized_end])
    start_byte = offsets[normalized_start - 1]
    end_byte = total_bytes if normalized_end == len(lines) else offsets[normalized_end]
    return ChunkDraft(
        strategy=strategy,
        start_line=normalized_start,
        end_line=normalized_end,
        start_byte=start_byte,
        end_byte=end_byte,
        content=content,
    )


class BoundaryChunker:
    """Convert structural boundaries into contiguous chunk drafts."""

    strategy_name = "structure"

    def chunk(
        self,
        *,
        source_text: str,
        relative_path: str,
        boundaries: Sequence[StructuralBoundary] = (),
    ) -> tuple[ChunkDraft, ...]:
        """Build chunk drafts from declaration or section boundaries."""

        del relative_path
        lines = _split_lines(source_text)
        if not lines or not boundaries:
            return ()

        total_lines = len(lines)
        start_lines = sorted(
            {
                min(max(boundary.start_line, 1), total_lines)
                for boundary in boundaries
            },
        )
        if not start_lines:
            return ()
        if start_lines[0] != 1:
            if len(start_lines) == 1:
                start_lines = [1, *start_lines]
            else:
                start_lines[0] = 1

        drafts: list[ChunkDraft] = []
        for index, start_line in enumerate(start_lines):
            end_line = (
                start_lines[index + 1] - 1
                if index + 1 < len(start_lines)
                else total_lines
            )
            draft = _build_draft(
                source_text=source_text,
                strategy=self.strategy_name,
                start_line=start_line,
                end_line=end_line,
            )
            if draft is not None:
                drafts.append(draft)

        return tuple(drafts)

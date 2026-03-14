"""Ports for turning source files into retrieval chunks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from codeman.application.ports.parser_port import StructuralBoundary
from codeman.contracts.repository import SourceLanguage


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    """In-memory chunk candidate before artifact persistence."""

    strategy: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    content: str


class ChunkerPort(Protocol):
    """Boundary for structural and fallback chunker implementations."""

    strategy_name: str

    def chunk(
        self,
        *,
        source_text: str,
        relative_path: str,
        boundaries: Sequence[StructuralBoundary] = (),
    ) -> tuple[ChunkDraft, ...]:
        """Produce ordered chunk drafts for a source file."""


class ChunkerRegistryPort(Protocol):
    """Resolve structural and fallback chunkers by language."""

    def get_structural(self, language: SourceLanguage) -> ChunkerPort | None:
        """Return the preferred structural chunker for a language."""

    def get_fallback(self, language: SourceLanguage) -> ChunkerPort:
        """Return the bounded fallback chunker for a language."""

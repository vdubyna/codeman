"""Ports for structure-aware source parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from codeman.contracts.repository import SourceLanguage


class ParserFailure(RuntimeError):
    """Raised when a preferred structural parser cannot safely parse a file."""


@dataclass(frozen=True, slots=True)
class StructuralBoundary:
    """A meaningful source boundary discovered by a structural parser."""

    kind: str
    start_line: int
    label: str | None = None


class StructuralParserPort(Protocol):
    """Boundary for preferred structure-aware parser implementations."""

    def parse(
        self,
        *,
        source_text: str,
        relative_path: str,
    ) -> tuple[StructuralBoundary, ...]:
        """Return structural boundaries for a source file."""


class ParserRegistryPort(Protocol):
    """Resolve structural parsers by normalized source language."""

    def get(self, language: SourceLanguage) -> StructuralParserPort | None:
        """Return a parser for the requested language when available."""

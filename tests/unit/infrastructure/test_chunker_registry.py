from __future__ import annotations

from codeman.application.ports.parser_port import StructuralBoundary
from codeman.infrastructure.chunkers.chunker_registry import ChunkerRegistry
from codeman.infrastructure.chunkers.fallback_chunker import WindowedFallbackChunker


def test_chunker_registry_returns_structural_and_fallback_chunkers() -> None:
    registry = ChunkerRegistry()

    for language in ("php", "javascript", "html", "twig"):
        assert registry.get_structural(language) is not None
        assert registry.get_fallback(language) is not None


def test_structural_chunker_sorts_boundaries_into_ordered_spans() -> None:
    registry = ChunkerRegistry()
    chunker = registry.get_structural("javascript")
    assert chunker is not None

    drafts = chunker.chunk(
        source_text="one\ntwo\nthree\nfour\nfive\n",
        relative_path="assets/app.js",
        boundaries=(
            StructuralBoundary(kind="declaration", start_line=4),
            StructuralBoundary(kind="declaration", start_line=2),
        ),
    )

    assert [(draft.start_line, draft.end_line) for draft in drafts] == [(1, 3), (4, 5)]
    assert drafts[0].start_byte == 0
    assert drafts[1].content == "four\nfive\n"


def test_structural_chunker_keeps_single_boundary_split_out_of_preamble() -> None:
    registry = ChunkerRegistry()
    chunker = registry.get_structural("twig")
    assert chunker is not None

    drafts = chunker.chunk(
        source_text=(
            '{% extends "base.html.twig" %}\n\n'
            "{% block body %}\n  <h1>Fixture</h1>\n{% endblock %}\n"
        ),
        relative_path="templates/page.html.twig",
        boundaries=(StructuralBoundary(kind="template-section", start_line=3),),
    )

    assert [(draft.start_line, draft.end_line) for draft in drafts] == [(1, 2), (3, 5)]


def test_fallback_chunker_keeps_chunks_bounded_and_ordered() -> None:
    source_text = "".join(f"line {index}\n" for index in range(1, 46))
    chunker = WindowedFallbackChunker("javascript_fallback", max_lines=20)

    drafts = chunker.chunk(
        source_text=source_text,
        relative_path="assets/broken.js",
    )

    assert len(drafts) == 3
    assert all((draft.end_line - draft.start_line + 1) <= 20 for draft in drafts)
    assert [(draft.start_line, draft.end_line) for draft in drafts] == [
        (1, 20),
        (21, 40),
        (41, 45),
    ]

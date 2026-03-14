"""Resolve chunkers by source language."""

from __future__ import annotations

from codeman.application.ports.chunker_port import ChunkerPort, ChunkerRegistryPort
from codeman.contracts.repository import SourceLanguage
from codeman.infrastructure.chunkers.fallback_chunker import WindowedFallbackChunker
from codeman.infrastructure.chunkers.html_chunker import HtmlChunker
from codeman.infrastructure.chunkers.javascript_chunker import JavascriptChunker
from codeman.infrastructure.chunkers.php_chunker import PhpChunker
from codeman.infrastructure.chunkers.twig_chunker import TwigChunker


class ChunkerRegistry(ChunkerRegistryPort):
    """Language-aware registry for preferred and fallback chunkers."""

    def __init__(self) -> None:
        self._structural: dict[SourceLanguage, ChunkerPort] = {
            "php": PhpChunker(),
            "javascript": JavascriptChunker(),
            "html": HtmlChunker(),
            "twig": TwigChunker(),
        }
        self._fallback: dict[SourceLanguage, ChunkerPort] = {
            language: WindowedFallbackChunker(f"{language}_fallback")
            for language in ("php", "javascript", "html", "twig")
        }

    def get_structural(self, language: SourceLanguage) -> ChunkerPort | None:
        """Return the preferred structural chunker for a language."""

        return self._structural.get(language)

    def get_fallback(self, language: SourceLanguage) -> ChunkerPort:
        """Return the bounded fallback chunker for a language."""

        return self._fallback[language]

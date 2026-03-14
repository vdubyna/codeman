"""Resolve structure-aware parsers by source language."""

from __future__ import annotations

from codeman.application.ports.parser_port import ParserRegistryPort, StructuralParserPort
from codeman.contracts.repository import SourceLanguage
from codeman.infrastructure.parsers.html_parser import HtmlParser
from codeman.infrastructure.parsers.javascript_parser import JavascriptParser
from codeman.infrastructure.parsers.php_parser import PhpParser
from codeman.infrastructure.parsers.twig_parser import TwigParser


class ParserRegistry(ParserRegistryPort):
    """Language-aware registry for preferred structural parsers."""

    def __init__(self) -> None:
        self._parsers: dict[SourceLanguage, StructuralParserPort] = {
            "php": PhpParser(),
            "javascript": JavascriptParser(),
            "html": HtmlParser(),
            "twig": TwigParser(),
        }

    def get(self, language: SourceLanguage) -> StructuralParserPort | None:
        """Return the parser for a language when one is registered."""

        return self._parsers.get(language)

from __future__ import annotations

import pytest

from codeman.application.ports.parser_port import ParserFailure
from codeman.infrastructure.parsers.html_parser import HtmlParser
from codeman.infrastructure.parsers.javascript_parser import JavascriptParser
from codeman.infrastructure.parsers.php_parser import PhpParser
from codeman.infrastructure.parsers.twig_parser import TwigParser


def test_php_parser_finds_class_and_method_boundaries() -> None:
    source = """<?php

declare(strict_types=1);

final class HomeController
{
    public function __invoke(): string
    {
        return 'home';
    }
}
"""

    boundaries = PhpParser().parse(
        source_text=source,
        relative_path="src/Controller/HomeController.php",
    )

    assert [boundary.start_line for boundary in boundaries] == [5, 7]


def test_javascript_parser_finds_function_boundary() -> None:
    boundaries = JavascriptParser().parse(
        source_text='export function boot() {\n  return "codeman";\n}\n',
        relative_path="assets/app.js",
    )

    assert [boundary.start_line for boundary in boundaries] == [1]


def test_html_and_twig_parsers_find_template_boundaries() -> None:
    html_boundaries = HtmlParser().parse(
        source_text=(
            "<!doctype html>\n<html>\n  <body>\n"
            "    <main>Fixture</main>\n  </body>\n</html>\n"
        ),
        relative_path="public/index.html",
    )
    twig_boundaries = TwigParser().parse(
        source_text=(
            '{% extends "base.html.twig" %}\n\n'
            "{% block body %}\n  <h1>Fixture</h1>\n{% endblock %}\n"
        ),
        relative_path="templates/page.html.twig",
    )

    assert [boundary.start_line for boundary in html_boundaries] == [3, 4]
    assert [boundary.start_line for boundary in twig_boundaries] == [3]


def test_javascript_parser_raises_on_unbalanced_braces() -> None:
    with pytest.raises(ParserFailure):
        JavascriptParser().parse(
            source_text='export function broken() {\n  return "missing";\n',
            relative_path="assets/broken.js",
        )

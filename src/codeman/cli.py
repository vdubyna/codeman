"""CLI entry point for the codeman project."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codeman",
        description="Minimal Python CLI scaffold for a BMAD-enabled project.",
    )
    parser.add_argument(
        "--name",
        default="world",
        help="Name to greet.",
    )
    return parser


def greet(name: str) -> str:
    clean_name = name.strip() or "world"
    return f"Hello, {clean_name}!"


def main() -> int:
    args = build_parser().parse_args()
    print(greet(args.name))
    return 0


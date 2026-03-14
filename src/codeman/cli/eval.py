"""Evaluation command group placeholder."""

from __future__ import annotations

import typer

app = typer.Typer(help="Benchmark and evaluation commands.", no_args_is_help=True)


@app.callback()
def eval_group() -> None:
    """Run benchmark workflows."""

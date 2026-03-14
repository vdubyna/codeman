"""Comparison command group placeholder."""

from __future__ import annotations

import typer

app = typer.Typer(help="Experiment comparison commands.", no_args_is_help=True)


@app.callback()
def compare_group() -> None:
    """Compare experiment outputs."""

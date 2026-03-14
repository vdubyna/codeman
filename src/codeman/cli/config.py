"""Configuration command group placeholder."""

from __future__ import annotations

import typer

app = typer.Typer(help="Configuration inspection and override commands.", no_args_is_help=True)


@app.callback()
def config_group() -> None:
    """Inspect configuration and runtime defaults."""

"""Index command group placeholder."""

from __future__ import annotations

import typer

app = typer.Typer(help="Index build and refresh commands.", no_args_is_help=True)


@app.callback()
def index_group() -> None:
    """Manage index build workflows."""

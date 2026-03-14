"""Query command group placeholder."""

from __future__ import annotations

import typer

app = typer.Typer(help="Retrieval query commands.", no_args_is_help=True)


@app.callback()
def query_group() -> None:
    """Run retrieval queries."""

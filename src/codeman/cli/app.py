"""Root Typer application."""

from __future__ import annotations

import typer

from codeman.bootstrap import BootstrapContainer, bootstrap
from codeman.cli import compare, config, eval, index, query, repo


def create_app() -> typer.Typer:
    """Build the root CLI application."""

    app = typer.Typer(
        help="codeman CLI for repository retrieval experiments.",
        no_args_is_help=True,
        pretty_exceptions_show_locals=False,
    )

    @app.callback()
    def app_callback(ctx: typer.Context) -> None:
        """Initialize shared CLI context."""

        if ctx.obj is None:
            ctx.obj = bootstrap()

    app.add_typer(repo.app, name="repo")
    app.add_typer(index.app, name="index")
    app.add_typer(query.app, name="query")
    app.add_typer(eval.app, name="eval")
    app.add_typer(compare.app, name="compare")
    app.add_typer(config.app, name="config")

    return app


app = create_app()


def get_container(ctx: typer.Context) -> BootstrapContainer:
    """Return the shared bootstrap container for the current command invocation."""

    if isinstance(ctx.obj, BootstrapContainer):
        return ctx.obj

    container = bootstrap()
    ctx.obj = container
    return container


def main() -> None:
    """Console script entrypoint."""

    app()

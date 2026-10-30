"""PyDeps command-line interface."""

from __future__ import annotations

import typer

from pydeps import __version__

app = typer.Typer(
    name="pydeps",
    help="PyDeps: A Python Dependency Intelligence Engine.",
    no_args_is_help=True,
    add_completion=False,
)


def version_callback(value: bool) -> None:
    """Print the PyDeps version and exit."""
    if value:
        typer.echo(f"pydeps {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the PyDeps version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """PyDeps: Analyze, evaluate compatibility, and resolve Python dependencies."""
    # Global options are handled here (e.g. --version)


if __name__ == "__main__":
    app()

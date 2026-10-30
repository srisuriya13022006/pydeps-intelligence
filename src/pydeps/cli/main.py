"""PyDeps command-line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from pydeps import __version__
from pydeps.analyzer.analyzer import ImportAnalyzer
from pydeps.scanner.scanner import ProjectScanner

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
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help="Show the PyDeps version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """PyDeps: Analyze, evaluate compatibility, and resolve Python dependencies."""


@app.command("scan")
def scan_command(
    project_path: Annotated[
        Path,
        typer.Argument(
            help="Path to project root directory to scan.",
            exists=False,
        ),
    ] = Path("."),
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Format scan results as structured JSON.",
        ),
    ] = False,
    follow_symlinks: Annotated[
        bool,
        typer.Option(
            "--follow-symlinks",
            help="Follow filesystem directory symlinks during discovery.",
        ),
    ] = False,
) -> None:
    """Scan a Python project and discover source files, notebooks, and metadata."""
    if not project_path.exists():
        typer.secho(
            f"Error: Specified project path does not exist: {project_path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    scanner = ProjectScanner(follow_symlinks=follow_symlinks)
    structure = scanner.scan(project_path)

    if json_output:
        typer.echo(structure.model_dump_json(indent=2))
        return

    meta_str = ", ".join(p.name for p in structure.metadata_files) or "None"
    local_str = ", ".join(structure.local_modules) or "None"
    roots_str = ", ".join(p.name for p in structure.source_roots)

    typer.secho(f"=== PyDeps Project Scan: {structure.root_path.name} ===", fg=typer.colors.CYAN)
    typer.echo(f"Root Directory:      {structure.root_path}")
    typer.echo(f"Python Source Files: {len(structure.source_files)}")
    typer.echo(f"Jupyter Notebooks:   {len(structure.notebook_files)}")
    typer.echo(f"Source Roots:        {roots_str}")
    typer.echo(f"Project Metadata:    {meta_str}")
    typer.echo(f"Local Modules:       {local_str}")

    if structure.diagnostics:
        typer.secho("\nDiagnostics & Warnings:", fg=typer.colors.YELLOW)
        for diag in structure.diagnostics:
            typer.echo(f"  - {diag}")


@app.command("analyze")
def analyze_command(
    project_path: Annotated[
        Path,
        typer.Argument(
            help="Path to project root directory to analyze.",
            exists=False,
        ),
    ] = Path("."),
    python_version: Annotated[
        str,
        typer.Option(
            "--python-version",
            "-p",
            help="Target Python version for standard library evaluation (e.g. 3.10, 3.11).",
        ),
    ] = "3.11",
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Format analysis results as structured JSON.",
        ),
    ] = False,
    follow_symlinks: Annotated[
        bool,
        typer.Option(
            "--follow-symlinks",
            help="Follow filesystem directory symlinks during discovery.",
        ),
    ] = False,
) -> None:
    """Analyze a project and classify all discovered imports."""
    if not project_path.exists():
        typer.secho(
            f"Error: Specified project path does not exist: {project_path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    scanner = ProjectScanner(follow_symlinks=follow_symlinks)
    structure = scanner.scan(project_path)

    analyzer = ImportAnalyzer()
    result = analyzer.analyze_project(
        structure,
        target_python_version=python_version,
    )

    if json_output:
        typer.echo(result.model_dump_json(indent=2))
        return

    summary = result.summary()
    header = f"=== PyDeps Import Analysis: {structure.root_path.name} (Python {python_version}) ==="
    typer.secho(header, fg=typer.colors.CYAN)
    typer.echo(
        f"Scanned Files:       {summary['source_files']} Python, "
        f"{summary['notebook_files']} Notebooks"
    )
    typer.echo(f"Total Import Stmts:  {summary['total_import_statements']}")

    stdlib_mods = summary["unique_standard_library_modules"]
    typer.echo(f"Standard Library:    {len(stdlib_mods)} unique modules")
    if stdlib_mods:
        typer.echo(f"  -> {', '.join(stdlib_mods)}")

    local_mods = summary["unique_local_modules"]
    typer.echo(f"Local Modules:       {len(local_mods)} unique modules")
    if local_mods:
        typer.echo(f"  -> {', '.join(local_mods)}")

    ext_pkgs = summary["unique_external_packages"]
    typer.echo(f"External Candidates: {len(ext_pkgs)} third-party distributions")
    if ext_pkgs:
        typer.secho(f"  -> {', '.join(ext_pkgs)}", fg=typer.colors.GREEN)

    if summary["optional_imports_count"] > 0:
        typer.echo(f"Optional Imports:    {summary['optional_imports_count']} (try/except/guard)")
    if summary["type_checking_imports_count"] > 0:
        typer.echo(f"Type-Checking Only:  {summary['type_checking_imports_count']}")
    if summary["dynamic_imports_count"] > 0:
        typer.secho(
            f"Dynamic Imports:     {summary['dynamic_imports_count']} requiring review",
            fg=typer.colors.YELLOW,
        )
    if summary["unresolved_imports_count"] > 0:
        typer.secho(
            f"Unresolved Imports:  {summary['unresolved_imports_count']}",
            fg=typer.colors.RED,
        )

    if result.diagnostics:
        typer.secho("\nDiagnostics:", fg=typer.colors.YELLOW)
        for diag in result.diagnostics:
            typer.echo(f"  - {diag}")


if __name__ == "__main__":
    app()

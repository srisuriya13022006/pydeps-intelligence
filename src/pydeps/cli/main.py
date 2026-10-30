"""PyDeps command-line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from pydeps._version import __version__
from pydeps.analyzer.analyzer import ImportAnalyzer
from pydeps.metadata.metadata_provider import MetadataProvider
from pydeps.registry.package_mapper import PackageMapper
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
    resolve_names: Annotated[
        bool,
        typer.Option(
            "--resolve-names",
            "-r",
            help="Resolve external import candidates to canonical PyPI distribution names.",
        ),
    ] = False,
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

    package_report = None
    if resolve_names:
        mapper = PackageMapper()
        package_report = mapper.map_analysis(result)

    if json_output:
        if resolve_names and package_report is not None:
            typer.echo(package_report.model_dump_json(indent=2))
        else:
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
    typer.echo(f"External Candidates: {len(ext_pkgs)} third-party imports")
    if ext_pkgs:
        typer.secho(f"  -> {', '.join(ext_pkgs)}", fg=typer.colors.GREEN)

    if resolve_names and package_report is not None:
        typer.secho("\n--- Resolved Distributions ---", fg=typer.colors.CYAN)
        sel_dists = package_report.selected_distributions
        typer.echo(f"Resolved Packages:   {len(sel_dists)} distributions")
        if sel_dists:
            typer.secho(f"  -> {', '.join(sel_dists)}", fg=typer.colors.GREEN)

        if package_report.ambiguous_imports:
            amb_count = len(package_report.ambiguous_imports)
            msg = f"Ambiguous Imports:   {amb_count} imports require review"
            typer.secho(msg, fg=typer.colors.YELLOW)
            for amb in package_report.ambiguous_imports:
                cand_str = ", ".join(amb.candidate_distributions)
                typer.echo(f"  - {amb.import_name} -> candidates: {cand_str}")

        if package_report.unresolved_imports:
            unres_count = len(package_report.unresolved_imports)
            typer.secho(f"Unresolved Imports:  {unres_count} imports", fg=typer.colors.RED)

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


@app.command("map")
def map_command(
    project_path: Annotated[
        Path,
        typer.Argument(
            help="Path to project root directory to map.",
            exists=False,
        ),
    ] = Path("."),
    python_version: Annotated[
        str,
        typer.Option(
            "--python-version",
            "-p",
            help="Target Python version for standard library evaluation.",
        ),
    ] = "3.11",
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Format mapping results as structured JSON.",
        ),
    ] = False,
) -> None:
    """Map external candidate imports in a project to canonical PyPI distribution names."""
    if not project_path.exists():
        typer.secho(
            f"Error: Specified project path does not exist: {project_path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    scanner = ProjectScanner()
    structure = scanner.scan(project_path)

    analyzer = ImportAnalyzer()
    analysis = analyzer.analyze_project(structure, target_python_version=python_version)

    mapper = PackageMapper()
    report = mapper.map_analysis(analysis)

    if json_output:
        typer.echo(report.model_dump_json(indent=2))
        return

    typer.secho(f"=== PyDeps Package Mapping: {structure.root_path.name} ===", fg=typer.colors.CYAN)
    typer.echo(f"Candidate Imports:      {len(report.mappings)}")
    typer.echo(f"Resolved Distributions: {len(report.selected_distributions)}")
    if report.selected_distributions:
        typer.secho(f"  -> {', '.join(report.selected_distributions)}", fg=typer.colors.GREEN)

    typer.echo("\n--- Detailed Mappings ---")
    for m in report.mappings:
        status_color = typer.colors.GREEN if m.selected_distribution else typer.colors.YELLOW
        cand_str = ", ".join(m.candidate_distributions)
        target_display = m.selected_distribution or f"[Ambiguous: {cand_str}]"
        typer.echo(
            f"  {m.import_name:<20} -> {typer.style(target_display, fg=status_color)} "
            f"({m.mapping_source.value}, {m.confidence.value})"
        )

    if report.ambiguous_imports:
        typer.secho("\nAmbiguous Mappings Requiring Review:", fg=typer.colors.YELLOW)
        for amb in report.ambiguous_imports:
            typer.echo(f"  - {amb.import_name}: candidates={amb.candidate_distributions}")

    if report.unresolved_imports:
        typer.secho("\nUnresolved Imports:", fg=typer.colors.RED)
        for unres in report.unresolved_imports:
            typer.echo(f"  - {unres}")


@app.command("metadata")
def metadata_command(
    package: Annotated[
        str,
        typer.Argument(
            help="PyPI distribution package name to query (e.g. 'requests', 'flask').",
        ),
    ],
    version: Annotated[
        str | None,
        typer.Option(
            "--version",
            "-v",
            help="Specific package version (defaults to latest release).",
        ),
    ] = None,
    offline: Annotated[
        bool,
        typer.Option(
            "--offline",
            help="Operate in offline mode (only read from cache).",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Format metadata as structured JSON.",
        ),
    ] = False,
) -> None:
    """Retrieve and display structured release metadata from PyPI."""
    provider = MetadataProvider(offline=offline)
    result = provider.get_metadata(package, version=version)

    if json_output:
        typer.echo(result.model_dump_json(indent=2))
        if not result.success:
            raise typer.Exit(code=1)
        return

    if not result.success or not result.metadata:
        typer.secho(f"Error fetching metadata for '{package}':", fg=typer.colors.RED, err=True)
        for diag in result.diagnostics:
            typer.echo(f"  - {diag}", err=True)
        raise typer.Exit(code=1)

    rel = result.metadata
    hdr = f"=== PyPI Metadata: {rel.distribution_name} {rel.version} ==="
    typer.secho(hdr, fg=typer.colors.CYAN)
    if rel.summary:
        typer.echo(f"Summary:         {rel.summary}")
    typer.echo(f"Source:          {result.source}")
    typer.echo(f"Requires-Python: {rel.requires_python or 'None declared'}")
    typer.echo(f"Yanked:          {'Yes - ' + (rel.yanked_reason or '') if rel.yanked else 'No'}")

    typer.echo(f"\nDependencies ({len(rel.requires_dist)}):")
    for dep in rel.requires_dist:
        typer.echo(f"  - {dep.to_pep508()}")

    if rel.provides_extra:
        typer.echo(f"\nExtras Provided: {', '.join(rel.provides_extra)}")

    typer.echo(f"\nArtifact Files ({len(rel.release_files)}):")
    for art in rel.release_files:
        sha_short = (art.sha256[:10] + "...") if art.sha256 else "None"
        info = f"{art.package_type}, {art.size or 0} bytes, sha256:{sha_short}"
        typer.echo(f"  - {art.filename} ({info})")


if __name__ == "__main__":
    app()

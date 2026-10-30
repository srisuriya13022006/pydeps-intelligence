"""Integration tests for PyDeps CLI."""

from __future__ import annotations

from typer.testing import CliRunner

from pydeps import __version__
from pydeps.cli.main import app

runner = CliRunner()


def test_cli_help() -> None:
    """Test 'pydeps --help' displays usage, options, and returns 0."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "PyDeps" in result.stdout
    assert "--help" in result.stdout
    assert "--version" in result.stdout


def test_cli_version_flag() -> None:
    """Test 'pydeps --version' outputs current version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"pydeps {__version__}" in result.stdout


def test_cli_version_short_flag() -> None:
    """Test 'pydeps -v' outputs current version."""
    result = runner.invoke(app, ["-v"])
    assert result.exit_code == 0
    assert f"pydeps {__version__}" in result.stdout


def test_cli_no_args_shows_help() -> None:
    """Test invoking pydeps without arguments displays help."""
    result = runner.invoke(app, [])
    # When no_args_is_help=True, typer prints help
    assert "PyDeps" in result.stdout or "--help" in result.stdout

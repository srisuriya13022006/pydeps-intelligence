"""Integration tests for PyDeps CLI."""

from __future__ import annotations

import json
from pathlib import Path

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
    assert "scan" in result.stdout
    assert "analyze" in result.stdout


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
    assert "PyDeps" in result.stdout or "--help" in result.stdout


def test_cli_scan_command(tmp_path: Path) -> None:
    """Test 'pydeps scan' summarizes project source files."""
    (tmp_path / "app.py").write_text("import os\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")

    result = runner.invoke(app, ["scan", str(tmp_path)])
    assert result.exit_code == 0
    assert "Python Source Files: 1" in result.stdout
    assert "pyproject.toml" in result.stdout


def test_cli_scan_json_output(tmp_path: Path) -> None:
    """Test 'pydeps scan --json' produces valid JSON output."""
    (tmp_path / "app.py").write_text("import sys\n", encoding="utf-8")

    result = runner.invoke(app, ["scan", str(tmp_path), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "source_files" in data
    assert len(data["source_files"]) == 1
    assert "root_path" in data


def test_cli_scan_non_existent_path(tmp_path: Path) -> None:
    """Test 'pydeps scan' on a non-existent path exits with code 1."""
    bad_path = tmp_path / "missing_dir"
    result = runner.invoke(app, ["scan", str(bad_path)])
    assert result.exit_code == 1
    assert "does not exist" in result.stderr or "does not exist" in result.stdout


def test_cli_analyze_command(tmp_path: Path) -> None:
    """Test 'pydeps analyze' classifies imports and outputs summary."""
    (tmp_path / "main.py").write_text(
        "import math\nimport requests\nfrom . import local_helper\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["analyze", str(tmp_path)])
    assert result.exit_code == 0
    assert "Standard Library:" in result.stdout
    assert "math" in result.stdout
    assert "External Candidates:" in result.stdout
    assert "requests" in result.stdout


def test_cli_analyze_json_output(tmp_path: Path) -> None:
    """Test 'pydeps analyze --json' returns valid structured JSON."""
    (tmp_path / "main.py").write_text("import click\nimport json\n", encoding="utf-8")

    result = runner.invoke(app, ["analyze", str(tmp_path), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "standard_library_imports" in data
    assert "external_candidate_imports" in data
    ext_mods = [imp["module_name"] for imp in data["external_candidate_imports"]]
    assert "click" in ext_mods


def test_cli_analyze_non_existent_path(tmp_path: Path) -> None:
    """Test 'pydeps analyze' on a non-existent path exits with code 1."""
    bad_path = tmp_path / "missing_dir"
    result = runner.invoke(app, ["analyze", str(bad_path)])
    assert result.exit_code == 1
    assert "does not exist" in result.stderr or "does not exist" in result.stdout


def test_cli_analyze_resolve_names(tmp_path: Path) -> None:
    """Test 'pydeps analyze --resolve-names' displays mapped distributions."""
    (tmp_path / "app.py").write_text("import yaml\nimport requests\n", encoding="utf-8")

    result = runner.invoke(app, ["analyze", str(tmp_path), "--resolve-names"])
    assert result.exit_code == 0
    assert "Resolved Distributions" in result.stdout
    assert "pyyaml" in result.stdout
    assert "requests" in result.stdout


def test_cli_analyze_resolve_names_json(tmp_path: Path) -> None:
    """Test 'pydeps analyze --resolve-names --json' produces structured PackageReport."""
    (tmp_path / "app.py").write_text("import cv2\n", encoding="utf-8")

    result = runner.invoke(app, ["analyze", str(tmp_path), "--resolve-names", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "mappings" in data
    assert "selected_distributions" in data
    assert "ambiguous_imports" in data
    assert len(data["ambiguous_imports"]) == 1
    assert data["ambiguous_imports"][0]["import_name"] == "cv2"


def test_cli_map_command(tmp_path: Path) -> None:
    """Test 'pydeps map' maps imports in a project to distribution names."""
    (tmp_path / "main.py").write_text("import PIL\nimport dotenv\n", encoding="utf-8")

    result = runner.invoke(app, ["map", str(tmp_path)])
    assert result.exit_code == 0
    assert "PyDeps Package Mapping" in result.stdout
    assert "pillow" in result.stdout.lower()
    assert "python-dotenv" in result.stdout.lower()


def test_cli_map_json_output(tmp_path: Path) -> None:
    """Test 'pydeps map --json' outputs valid PackageReport JSON."""
    (tmp_path / "main.py").write_text("import sklearn\n", encoding="utf-8")

    result = runner.invoke(app, ["map", str(tmp_path), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "mappings" in data
    assert data["selected_distributions"] == ["scikit-learn"]


def test_cli_map_non_existent_path(tmp_path: Path) -> None:
    """Test 'pydeps map' on missing path returns error code 1."""
    bad_path = tmp_path / "missing_dir"
    result = runner.invoke(app, ["map", str(bad_path)])
    assert result.exit_code == 1
    assert "does not exist" in result.stderr or "does not exist" in result.stdout


def test_cli_metadata_offline_cache_miss() -> None:
    """Test 'pydeps metadata --offline' on un-cached package exits with 1."""
    result = runner.invoke(app, ["metadata", "uncached-pkg-xyz", "--offline"])
    assert result.exit_code == 1
    assert "Error fetching metadata" in result.stderr or "offline mode is enabled" in result.stderr


def test_cli_metadata_offline_json_miss() -> None:
    """Test 'pydeps metadata --offline --json' on un-cached package exits with 1 and JSON."""
    result = runner.invoke(app, ["metadata", "uncached-pkg-xyz", "--offline", "--json"])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["success"] is False
    assert data["source"] == "offline_cache_miss"

"""Integration tests for the 'pydeps resolve' CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from pydeps_intelligence.cli.main import app

runner = CliRunner(env={"NO_COLOR": "1"})


def test_cli_resolve_help() -> None:
    """Test displaying help message for pydeps resolve."""
    result = runner.invoke(app, ["resolve", "--help"], color=False)
    assert result.exit_code == 0
    assert "Resolve direct and transitive dependencies" in result.stdout
    assert "--mode" in result.stdout
    assert "--backend" in result.stdout
    assert "--strategy" in result.stdout


def test_cli_resolve_nonexistent_path() -> None:
    """Test error handling when specified project directory does not exist."""
    result = runner.invoke(app, ["resolve", "path/that/does/not/exist_12345"])
    assert result.exit_code != 0


def test_cli_resolve_universal_success(tmp_path: Path) -> None:
    """Test successful universal resolution via CLI with mocked uv backend."""
    (tmp_path / "app.py").write_text("import requests\n", encoding="utf-8")

    mock_lock = """version = 1
requires-python = ">=3.9"

[[package]]
name = "requests"
version = "2.31.0"
source = { registry = "https://pypi.org/simple" }
dependencies = []
"""
    with patch("pydeps_intelligence.resolver.uv_backend.UvBackend.find_uv", return_value="uv"):

        def mock_run(cmd, cwd=None, *args, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            if "export" in cmd:
                mock.stdout = "requests==2.31.0\n"
            else:
                if cwd:
                    (Path(cwd) / "uv.lock").write_text(mock_lock, encoding="utf-8")
                mock.stdout = "Resolved"
            return mock

        with patch("subprocess.run", side_effect=mock_run):
            result = runner.invoke(app, ["resolve", str(tmp_path), "--mode", "universal"])
            assert result.exit_code == 0
            assert "PyDeps Resolution:" in result.stdout
            assert "requests == 2.31.0" in result.stdout
            assert "SUCCESS" in result.stdout


def test_cli_resolve_json_output(tmp_path: Path) -> None:
    """Test exporting structured resolution JSON from CLI."""
    (tmp_path / "app.py").write_text("import requests\n", encoding="utf-8")

    mock_lock = """version = 1
requires-python = ">=3.9"

[[package]]
name = "requests"
version = "2.31.0"
source = { registry = "https://pypi.org/simple" }
dependencies = []
"""
    with patch("pydeps_intelligence.resolver.uv_backend.UvBackend.find_uv", return_value="uv"):

        def mock_run(cmd, cwd=None, *args, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            if "export" in cmd:
                mock.stdout = "requests==2.31.0\n"
            else:
                if cwd:
                    (Path(cwd) / "uv.lock").write_text(mock_lock, encoding="utf-8")
                mock.stdout = "Resolved"
            return mock

        with patch("subprocess.run", side_effect=mock_run):
            result = runner.invoke(app, ["resolve", str(tmp_path), "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["success"] is True
            assert data["mode"] == "universal"
            assert data["status"] == "success"
            assert "graph" in data

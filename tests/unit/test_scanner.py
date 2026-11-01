"""Unit tests for the ProjectScanner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from pydeps_intelligence.scanner import ProjectScanner


def test_scan_empty_directory(tmp_path: Path) -> None:
    """Test scanning an empty directory produces empty lists without errors."""
    scanner = ProjectScanner()
    structure = scanner.scan(tmp_path)
    assert structure.root_path == tmp_path
    assert structure.source_files == []
    assert structure.notebook_files == []
    assert structure.local_modules == []
    assert structure.diagnostics == []


def test_scan_non_existent_directory(tmp_path: Path) -> None:
    """Test non-existent path records diagnostic without raising uncaught exception."""
    bad_path = tmp_path / "non_existent_subdir"
    scanner = ProjectScanner()
    structure = scanner.scan(bad_path)
    assert len(structure.diagnostics) >= 1
    assert "does not exist" in structure.diagnostics[0]
    assert structure.source_files == []


def test_scan_single_file(tmp_path: Path) -> None:
    """Test scanning a single file target."""
    py_file = tmp_path / "app.py"
    py_file.write_text("print('hello')\n", encoding="utf-8")

    scanner = ProjectScanner()
    structure = scanner.scan(py_file)
    assert structure.source_files == [py_file]
    assert "app" in structure.local_modules


def test_scan_nested_directories_and_deterministic_order(tmp_path: Path) -> None:
    """Test recursive discovery and deterministic sorting across nested directories."""
    # Create files in non-alphabetical order
    (tmp_path / "z_module.py").write_text("# z\n", encoding="utf-8")
    (tmp_path / "a_module.py").write_text("# a\n", encoding="utf-8")
    sub = tmp_path / "subpkg"
    sub.mkdir()
    (sub / "m_module.py").write_text("# m\n", encoding="utf-8")
    (sub / "__init__.py").write_text("# init\n", encoding="utf-8")

    scanner = ProjectScanner()
    structure = scanner.scan(tmp_path)

    expected_files = [
        tmp_path / "a_module.py",
        sub / "__init__.py",
        sub / "m_module.py",
        tmp_path / "z_module.py",
    ]
    assert structure.source_files == expected_files
    assert "a_module" in structure.local_modules
    assert "subpkg" in structure.local_modules
    assert "z_module" in structure.local_modules


def test_scan_default_and_custom_exclusions(tmp_path: Path) -> None:
    """Test that default exclusions (.git, .venv, __pycache__) and custom exclusions are skipped."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config.py").write_text("# secret\n", encoding="utf-8")

    venv_dir = tmp_path / ".venv" / "Lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "site_pkg.py").write_text("# ignored\n", encoding="utf-8")

    custom_dir = tmp_path / "custom_ignored"
    custom_dir.mkdir()
    (custom_dir / "skip.py").write_text("# skip\n", encoding="utf-8")

    valid_file = tmp_path / "main.py"
    valid_file.write_text("import sys\n", encoding="utf-8")

    # With default + custom exclusion
    scanner = ProjectScanner(exclusions=[".git", ".venv", "custom_ignored"])
    structure = scanner.scan(tmp_path)

    assert structure.source_files == [valid_file]


def test_scan_notebook_discovery_and_code_extraction(tmp_path: Path) -> None:
    """Test discovery of .ipynb files and safe code extraction without execution."""
    nb_file = tmp_path / "notebook.ipynb"
    nb_content = {
        "cells": [
            {
                "cell_type": "markdown",
                "source": ["# Title markdown\n"],
            },
            {
                "cell_type": "code",
                "source": [
                    "%matplotlib inline\n",
                    "import pandas as pd\n",
                    "from sklearn.linear_model import LinearRegression\n",
                ],
            },
            {
                "cell_type": "code",
                "source": "!pip install torch\nimport torch\n",
            },
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 2,
    }
    nb_file.write_text(json.dumps(nb_content), encoding="utf-8")

    scanner = ProjectScanner()
    structure = scanner.scan(tmp_path)
    assert structure.notebook_files == [nb_file]

    extracted_code = ProjectScanner.extract_notebook_code(nb_file)
    assert "import pandas as pd" in extracted_code
    assert "from sklearn.linear_model import LinearRegression" in extracted_code
    assert "import torch" in extracted_code
    # Ensure magics were commented out safely to prevent AST parse errors
    assert "# [ipython-magic] %matplotlib inline" in extracted_code
    assert "# [ipython-magic] !pip install torch" in extracted_code


def test_scan_metadata_files_discovery(tmp_path: Path) -> None:
    """Test discovery of standard metadata and configuration files."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("requests>=2.0\n", encoding="utf-8")
    (tmp_path / "setup.cfg").write_text("[metadata]\nname=test\n", encoding="utf-8")

    scanner = ProjectScanner()
    structure = scanner.scan(tmp_path)

    meta_names = {p.name for p in structure.metadata_files}
    assert "pyproject.toml" in meta_names
    assert "requirements.txt" in meta_names
    assert "setup.cfg" in meta_names


def test_scan_permission_error_handling(tmp_path: Path) -> None:
    """Test graceful handling when directory stat encounters a PermissionError."""
    with patch("pathlib.Path.stat", side_effect=PermissionError("Access denied")):
        scanner = ProjectScanner()
        structure = scanner.scan(tmp_path)
        assert len(structure.diagnostics) >= 1
        assert "Permission or OS error" in structure.diagnostics[0]

"""Integration tests for end-to-end source scanning and import analysis pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from pydeps import ImportAnalyzer, ProjectScanner


def test_full_pipeline_on_realistic_src_layout(tmp_path: Path) -> None:
    """Test full pipeline on a realistic multi-package project with src-layout and notebooks."""
    # 1. Setup project hierarchy
    src = tmp_path / "src"
    pkg = src / "my_service"
    core = pkg / "core"
    core.mkdir(parents=True)

    # __init__.py files
    (pkg / "__init__.py").write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    (core / "__init__.py").write_text("", encoding="utf-8")

    # core/engine.py
    (core / "engine.py").write_text(
        """
import os
import sys
from typing import TYPE_CHECKING
import httpx
from ..models import ConfigModel

if TYPE_CHECKING:
    import mypy_boto3_s3

def run():
    try:
        import orjson as fast_json
    except ImportError:
        import json as fast_json
""",
        encoding="utf-8",
    )

    # models.py
    (pkg / "models.py").write_text(
        """
from pydantic import BaseModel
import datetime

class ConfigModel(BaseModel):
    name: str
""",
        encoding="utf-8",
    )

    # notebooks/analysis.ipynb
    nb_dir = tmp_path / "notebooks"
    nb_dir.mkdir()
    nb_file = nb_dir / "eda.ipynb"
    nb_file.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "code",
                        "source": [
                            "%matplotlib inline\n",
                            "import numpy as np\n",
                            "import pandas as pd\n",
                            "from my_service.core.engine import run\n",
                        ],
                    }
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 2,
            }
        ),
        encoding="utf-8",
    )

    # tests/test_engine.py
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_engine.py").write_text(
        """
import pytest
from my_service.core.engine import run
""",
        encoding="utf-8",
    )

    # pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        """
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "my_service"
version = "0.1.0"
""",
        encoding="utf-8",
    )

    # 2. Run public API pipeline
    scanner = ProjectScanner()
    structure = scanner.scan(tmp_path)

    analyzer = ImportAnalyzer()
    analysis = analyzer.analyze_project(structure, target_python_version="3.11")

    # 3. Verify structure discovery
    assert len(structure.source_files) == 5
    assert len(structure.notebook_files) == 1
    assert "my_service" in structure.local_modules

    # 4. Verify external candidates
    external_pkgs = analysis.unique_external_packages
    assert "httpx" in external_pkgs
    assert "pydantic" in external_pkgs
    assert "orjson" in external_pkgs
    assert "numpy" in external_pkgs
    assert "pandas" in external_pkgs
    assert "pytest" in external_pkgs
    assert "mypy_boto3_s3" in external_pkgs

    # Ensure local package my_service is NOT classified as third-party
    assert "my_service" not in external_pkgs
    assert "my_service" in analysis.unique_local_modules

    # 5. Verify standard library modules
    stdlib_mods = analysis.unique_standard_library_modules
    assert "os" in stdlib_mods
    assert "sys" in stdlib_mods
    assert "typing" in stdlib_mods
    assert "datetime" in stdlib_mods
    assert "json" in stdlib_mods

    # 6. Verify optional and type-checking imports
    assert len(analysis.type_checking_imports) >= 1
    assert any(imp.module_name == "mypy_boto3_s3" for imp in analysis.type_checking_imports)

    assert len(analysis.optional_imports) >= 1
    assert any(imp.module_name == "orjson" for imp in analysis.optional_imports)

    # 7. Verify report generation
    report = analysis.to_analysis_report()
    assert report.project_information.project_name == tmp_path.name
    assert len(report.discovered_imports) == len(analysis.all_imports)

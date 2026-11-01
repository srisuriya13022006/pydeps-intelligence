"""Unit tests verifying packaging metadata, wheel/sdist archives, and distribution contracts."""

from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

import pydeps_intelligence

ROOT = Path(__file__).resolve().parent.parent.parent


def test_import_namespace_and_exports() -> None:
    """Import namespace must be pydeps_intelligence and export core APIs."""
    import pydeps_intelligence as pi

    assert pi.__version__ == "0.1.0a1"
    assert hasattr(pi, "PyDeps")
    assert hasattr(pi, "PyDepsIntelligence")
    assert hasattr(pi, "ProjectScanner")
    assert hasattr(pi, "ImportAnalyzer")
    assert hasattr(pi, "PackageMapper")
    assert hasattr(pi, "DiagnosticReport")


def test_version_consistency() -> None:
    """Declared version in _version.py and pyproject.toml must match exactly."""
    pyproject_path = ROOT / "pyproject.toml"
    assert pyproject_path.exists()

    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    pyproject_version = data["project"]["version"]
    assert pyproject_version == pydeps_intelligence.__version__
    assert pyproject_version == "0.1.0a1"


def test_pyproject_metadata() -> None:
    """pyproject.toml must declare distribution name, console script, and dependencies."""
    pyproject_path = ROOT / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    project = data["project"]
    assert project["name"] == "pydeps-intelligence"
    assert project["requires-python"] == ">=3.10"

    # Console script entry point
    scripts = project.get("scripts", {})
    assert "pydeps-intel" in scripts
    assert scripts["pydeps-intel"] == "pydeps_intelligence.cli.main:app"

    # Runtime dependencies
    deps = project.get("dependencies", [])
    dep_names = [d.split(">=")[0].split(";")[0].strip() for d in deps]
    assert "pydantic" in dep_names
    assert "packaging" in dep_names
    assert "typer" in dep_names
    assert "httpx" in dep_names

    # Dev dependencies
    dev_deps = project.get("optional-dependencies", {}).get("dev", [])
    dev_names = [d.split(">=")[0].strip() for d in dev_deps]
    assert "pytest" in dev_names
    assert "ruff" in dev_names
    assert "build" in dev_names
    assert "twine" in dev_names


def test_license_and_notice_files() -> None:
    """Official Apache-2.0 LICENSE and NOTICE files must exist and be valid."""
    license_path = ROOT / "LICENSE"
    notice_path = ROOT / "NOTICE"

    assert license_path.exists(), "LICENSE file is missing"
    assert notice_path.exists(), "NOTICE file is missing"

    license_text = license_path.read_text(encoding="utf-8")
    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text
    assert "sri suriya" in license_text

    notice_text = notice_path.read_text(encoding="utf-8")
    assert "PyDeps Intelligence" in notice_text
    assert "sri suriya" in notice_text


def test_package_typed_marker() -> None:
    """PEP 561 py.typed marker must exist in package source directory."""
    py_typed = ROOT / "src" / "pydeps_intelligence" / "py.typed"
    assert py_typed.exists()


def test_wheel_archive_contents() -> None:
    """Built wheel archive must include all modules and no excluded/sensitive files."""
    dist_dir = ROOT / "dist"
    wheels = list(dist_dir.glob("*.whl"))
    if not wheels:
        return  # Skip if wheel has not been built yet

    latest_wheel = sorted(wheels)[-1]
    with zipfile.ZipFile(latest_wheel, "r") as zf:
        namelist = zf.namelist()

        # Must include package modules
        assert any(n.startswith("pydeps_intelligence/__init__.py") for n in namelist)
        assert any(n.startswith("pydeps_intelligence/cli/main.py") for n in namelist)
        assert any(n.startswith("pydeps_intelligence/py.typed") for n in namelist)

        # Must include license
        assert any("LICENSE" in n for n in namelist)
        assert any("NOTICE" in n for n in namelist)

        # Must NOT include scratch files, tests, caches, or virtual environments
        for name in namelist:
            assert ".venv" not in name
            assert "__pycache__" not in name
            assert ".pytest_cache" not in name
            assert "scratch" not in name
            assert not name.startswith("tests/")


def test_sdist_archive_contents() -> None:
    """Built source distribution must include required source tree without temp files."""
    dist_dir = ROOT / "dist"
    sdists = list(dist_dir.glob("*.tar.gz"))
    if not sdists:
        return  # Skip if sdist has not been built yet

    latest_sdist = sorted(sdists)[-1]
    with tarfile.open(latest_sdist, "r:gz") as tf:
        namelist = tf.getnames()

        # Check required files
        assert any("pyproject.toml" in n for n in namelist)
        assert any("LICENSE" in n for n in namelist)
        assert any("NOTICE" in n for n in namelist)
        assert any("README.md" in n for n in namelist)
        assert any("src/pydeps_intelligence/__init__.py" in n for n in namelist)

        # Forbidden files
        for name in namelist:
            assert ".venv" not in name
            assert "__pycache__" not in name
            assert ".pytest_cache" not in name
            assert "scratch" not in name

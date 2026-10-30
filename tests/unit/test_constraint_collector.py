"""Unit tests for ConstraintCollector."""

from __future__ import annotations

from pathlib import Path

from pydeps.models.dependencies import DependencyType
from pydeps.resolver.constraint_collector import ConstraintCollector, parse_pep508_line


def test_parse_pep508_line_variants() -> None:
    """Test parsing various PEP 508 requirement lines."""
    # Standard pinned
    d1 = parse_pep508_line("requests >= 2.25.0")
    assert d1 is not None
    assert d1.name == "requests"
    assert d1.version_specifier == ">=2.25.0"

    # Extras and markers
    d2 = parse_pep508_line("pydantic[email] == 2.0.0; python_version >= '3.10'")
    assert d2 is not None
    assert d2.name == "pydantic"
    assert "email" in d2.extras
    assert d2.version_specifier == "==2.0.0"
    assert d2.environment_marker == 'python_version >= "3.10"'

    # Ignored comments and empty lines
    assert parse_pep508_line("# Just a comment") is None
    assert parse_pep508_line("   ") is None
    assert parse_pep508_line("-r other.txt") is None


def test_collector_pyproject_toml(tmp_path: Path) -> None:
    """Test collecting dependencies from standard PEP 621 pyproject.toml."""
    pyproject_content = """
[project]
name = "sample-app"
version = "1.0.0"
dependencies = [
    "flask >= 2.0.0",
    "gunicorn == 20.1.0; os_name != 'nt'",
]

[project.optional-dependencies]
dev = [
    "pytest >= 7.0.0",
]
security = [
    "cryptography >= 40.0.0",
]

[dependency-groups]
testing = [
    "coverage >= 7.0.0",
]
"""
    (tmp_path / "pyproject.toml").write_text(pyproject_content, encoding="utf-8")

    collector = ConstraintCollector(tmp_path)
    res = collector.collect_all_constraints()

    deps_by_name = res["by_name"]
    assert "flask" in deps_by_name
    assert deps_by_name["flask"].version_specifier == ">=2.0.0"
    assert deps_by_name["flask"].dependency_type == DependencyType.DIRECT

    assert "gunicorn" in deps_by_name
    assert deps_by_name["gunicorn"].environment_marker == 'os_name != "nt"'

    assert "pytest" in deps_by_name
    assert deps_by_name["pytest"].dependency_type == DependencyType.DEV

    assert "cryptography" in deps_by_name
    assert deps_by_name["cryptography"].dependency_type == DependencyType.OPTIONAL

    assert "coverage" in deps_by_name
    assert deps_by_name["coverage"].dependency_type == DependencyType.DEV


def test_collector_requirements_txt(tmp_path: Path) -> None:
    """Test collecting requirements from requirements.txt, dev.txt, and constraints.txt."""
    (tmp_path / "requirements.txt").write_text(
        "fastapi >= 0.100.0\nuvicorn[standard] >= 0.20.0\n", encoding="utf-8"
    )
    (tmp_path / "requirements-dev.txt").write_text("mypy >= 1.0.0\n", encoding="utf-8")
    (tmp_path / "constraints.txt").write_text("urllib3 < 2.0.0\n", encoding="utf-8")

    collector = ConstraintCollector(tmp_path)
    res = collector.collect_all_constraints()
    deps = res["by_name"]

    assert "fastapi" in deps
    assert "uvicorn" in deps
    assert "mypy" in deps
    assert deps["mypy"].dependency_type == DependencyType.DEV
    assert "urllib3" in deps
    assert deps["urllib3"].version_specifier == "<2.0.0"


def test_collector_setup_cfg_static(tmp_path: Path) -> None:
    """Test static dependency extraction from setup.cfg without code execution."""
    setup_cfg_content = """
[options]
install_requires =
    click >= 8.0.0
    rich >= 12.0.0

[options.extras_require]
dev =
    black >= 22.0.0
"""
    (tmp_path / "setup.cfg").write_text(setup_cfg_content, encoding="utf-8")

    collector = ConstraintCollector(tmp_path)
    res = collector.collect_all_constraints()
    deps = res["by_name"]

    assert "click" in deps
    assert "rich" in deps
    assert "black" in deps
    assert deps["black"].dependency_type == DependencyType.DEV

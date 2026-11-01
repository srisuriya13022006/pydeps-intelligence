"""Unit tests for StdlibCatalog and LocalModuleDetector."""

from __future__ import annotations

from pathlib import Path

from pydeps_intelligence.classifier import LocalModuleDetector, StdlibCatalog
from pydeps_intelligence.models.structure import ProjectStructure


def test_stdlib_catalog_core_modules() -> None:
    """Test standard library identification for common core modules."""
    catalog = StdlibCatalog()
    for mod in ("os", "sys", "math", "json", "urllib", "typing", "collections"):
        assert catalog.is_stdlib(mod, target_python_version="3.11") is True
        assert catalog.is_stdlib(mod, target_python_version="3.10") is True


def test_stdlib_catalog_version_differences() -> None:
    """Test target-version aware differences in standard library availability."""
    catalog = StdlibCatalog()

    # tomllib was added in Python 3.11
    assert catalog.is_stdlib("tomllib", target_python_version="3.10") is False
    assert catalog.is_stdlib("tomllib", target_python_version="3.11") is True
    assert catalog.is_stdlib("tomllib", target_python_version="3.12") is True

    # zoneinfo was added in Python 3.9
    assert catalog.is_stdlib("zoneinfo", target_python_version="3.8") is False
    assert catalog.is_stdlib("zoneinfo", target_python_version="3.9") is True
    assert catalog.is_stdlib("zoneinfo", target_python_version="3.11") is True

    # distutils was removed in Python 3.12
    assert catalog.is_stdlib("distutils", target_python_version="3.10") is True
    assert catalog.is_stdlib("distutils", target_python_version="3.12") is False

    # aifc was removed in Python 3.13
    assert catalog.is_stdlib("aifc", target_python_version="3.11") is True
    assert catalog.is_stdlib("aifc", target_python_version="3.13") is False


def test_stdlib_catalog_third_party_rejection() -> None:
    """Test that third-party packages are recognized as not stdlib."""
    catalog = StdlibCatalog()
    for pkg in ("requests", "pydantic", "fastapi", "numpy", "pytest", "typer"):
        assert catalog.is_stdlib(pkg, target_python_version="3.11") is False


def test_stdlib_catalog_unknown_version() -> None:
    """Test unrecognized Python versions return None (unverified) instead of guessing."""
    catalog = StdlibCatalog()
    # Python 1.5 or arbitrary non-cataloged versions
    assert catalog.is_stdlib("sys", target_python_version="1.5") is None
    assert catalog.is_stdlib("requests", target_python_version="99.0") is None


def test_local_module_detector_src_layout(tmp_path: Path) -> None:
    """Test local module detection with a standard src/ layout."""
    src = tmp_path / "src"
    pkg = src / "my_package"
    pkg.mkdir(parents=True)
    init_file = pkg / "__init__.py"
    init_file.write_text("# init\n", encoding="utf-8")
    mod_file = pkg / "core.py"
    mod_file.write_text("import os\n", encoding="utf-8")

    structure = ProjectStructure(
        root_path=tmp_path,
        source_files=[init_file, mod_file],
        notebook_files=[],
        source_roots=[src],
        metadata_files=[],
        local_modules=["my_package"],
        diagnostics=[],
    )

    detector = LocalModuleDetector(structure)
    assert detector.is_local_module("my_package") is True
    assert detector.is_local_module("my_package.core") is True
    assert detector.is_local_module("external_pkg") is False


def test_local_module_detector_relative_imports(tmp_path: Path) -> None:
    """Test relative import resolution against package hierarchies."""
    src = tmp_path / "src"
    app = src / "app"
    core = app / "core"
    core.mkdir(parents=True)

    init_app = app / "__init__.py"
    init_app.write_text("", encoding="utf-8")
    init_core = core / "__init__.py"
    init_core.write_text("", encoding="utf-8")
    engine = core / "engine.py"
    engine.write_text("", encoding="utf-8")
    utils = app / "utils.py"
    utils.write_text("", encoding="utf-8")

    structure = ProjectStructure(
        root_path=tmp_path,
        source_files=[init_app, init_core, engine, utils],
        notebook_files=[],
        source_roots=[src],
        metadata_files=[],
        local_modules=["app"],
        diagnostics=[],
    )

    detector = LocalModuleDetector(structure)

    # From engine.py: level 1 (same package app.core) -> app.core.helper
    res1 = detector.resolve_relative_import("helper", level=1, source_file=engine)
    assert res1 == "app.core.helper"

    # From engine.py: level 2 (parent package app) -> app.utils
    res2 = detector.resolve_relative_import("utils", level=2, source_file=engine)
    assert res2 == "app.utils"


def test_local_module_detector_namespace_packages(tmp_path: Path) -> None:
    """Test detection of namespace packages without __init__.py."""
    ns_dir = tmp_path / "namespace" / "sub"
    ns_dir.mkdir(parents=True)
    mod = ns_dir / "worker.py"
    mod.write_text("", encoding="utf-8")

    structure = ProjectStructure(
        root_path=tmp_path,
        source_files=[mod],
        notebook_files=[],
        source_roots=[tmp_path],
        metadata_files=[],
        local_modules=["namespace"],
        diagnostics=[],
    )

    detector = LocalModuleDetector(structure)
    assert detector.is_local_module("namespace") is True
    assert detector.is_local_module("namespace.sub.worker") is True

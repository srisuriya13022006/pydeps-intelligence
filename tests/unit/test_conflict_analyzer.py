"""Unit tests for ConflictAnalyzer diagnostic parsing."""

from __future__ import annotations

from pydeps_intelligence.resolver.conflict_analyzer import ConflictAnalyzer


def test_conflict_analyzer_uv_version_incompatibility() -> None:
    """Test parsing uv version conflict outputs."""
    stderr = """
error: Failed to resolve dependencies
  Because package-a==1.0.0 depends on package-b>=2.0
  and package-c==2.0.0 depends on package-b<2.0,
  we can conclude that the requirements are incompatible.
"""
    conflicts = ConflictAnalyzer.analyze_uv_error(stderr)
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.resolver_backend == "uv"
    assert c.error_category == "version_conflict"
    assert "package-b" in c.package_name or "package-a" in c.package_name
    assert "simultaneously satisfied" in c.suggested_investigation


def test_conflict_analyzer_uv_no_matching_release() -> None:
    """Test parsing no matching distribution error for Python version."""
    stderr = """
error: No solution found when resolving dependencies:
  Because package `numpy` has no releases matching python_version >= '3.14',
  we can conclude that numpy cannot be installed.
"""
    conflicts = ConflictAnalyzer.analyze_uv_error(stderr, target_environment="linux-x86_64-py3.14")
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.package_name == "numpy"
    assert c.error_category == "no_matching_release"
    assert c.target_environment == "linux-x86_64-py3.14"


def test_conflict_analyzer_uv_no_compatible_wheel() -> None:
    """Test parsing no pre-built wheel error with --no-build."""
    stderr = """
error: Failed to resolve requirements
  No compatible wheel available for `scipy` on win_arm64 and source builds are disabled (--no-build)
"""
    conflicts = ConflictAnalyzer.analyze_uv_error(stderr, target_environment="win_arm64")
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.package_name == "scipy"
    assert c.error_category == "no_compatible_wheel"
    assert "Source build is required" in c.suggested_investigation


def test_conflict_analyzer_pip_conflict() -> None:
    """Test parsing pip version conflict diagnostics."""
    stderr = """
ERROR: Cannot install package-a==1.0 and package-b==2.0 because
these package versions have conflicting dependencies.
"""
    conflicts = ConflictAnalyzer.analyze_pip_error(stderr)
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.resolver_backend == "pip"
    assert c.error_category == "version_conflict"


def test_conflict_analyzer_pip_no_match() -> None:
    """Test parsing pip no matching distribution error."""
    stderr = """
ERROR: No matching distribution found for torch>=2.0.0; sys_platform == 'darwin'
"""
    conflicts = ConflictAnalyzer.analyze_pip_error(stderr, target_environment="macos-arm64")
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.package_name == "torch"
    assert c.error_category == "no_matching_release"

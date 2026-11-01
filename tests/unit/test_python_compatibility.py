"""Unit tests for Python version compatibility evaluator."""

from __future__ import annotations

from packaging.version import Version

from pydeps_intelligence.compatibility.python_compatibility import evaluate_python_version
from pydeps_intelligence.models.compatibility import CompatibilityStatus


def test_python_compatibility_exact_and_range() -> None:
    """Test standard inclusive and exclusive range boundaries."""
    # Match in range
    res = evaluate_python_version(">=3.9, <3.13", "3.11")
    assert res.status == CompatibilityStatus.COMPATIBLE
    assert res.is_compatible is True

    # Exact boundary exclusion
    res_excl = evaluate_python_version("<3.11", "3.11")
    assert res_excl.status == CompatibilityStatus.INCOMPATIBLE
    assert res_excl.is_compatible is False

    # Lower bound exclusion
    res_lower = evaluate_python_version(">=3.10", "3.9")
    assert res_lower.status == CompatibilityStatus.INCOMPATIBLE
    assert res_lower.is_compatible is False


def test_python_compatibility_compound_specifier() -> None:
    """Test compound specifiers with exclusions."""
    spec = ">=3.8, !=3.9.0, !=3.9.1, <3.12"

    res_pass = evaluate_python_version(spec, "3.9.2")
    assert res_pass.status == CompatibilityStatus.COMPATIBLE

    res_excluded = evaluate_python_version(spec, "3.9.0")
    assert res_excluded.status == CompatibilityStatus.INCOMPATIBLE

    res_upper = evaluate_python_version(spec, "3.12.0")
    assert res_upper.status == CompatibilityStatus.INCOMPATIBLE


def test_python_compatibility_missing_metadata() -> None:
    """Test that missing Requires-Python returns UNVERIFIED rather than assumed compatible."""
    # None
    res_none = evaluate_python_version(None, "3.11")
    assert res_none.status == CompatibilityStatus.UNVERIFIED
    assert res_none.is_compatible is None
    assert "No Requires-Python specifier declared" in res_none.reason

    # Empty string
    res_empty = evaluate_python_version("", "3.11")
    assert res_empty.status == CompatibilityStatus.UNVERIFIED
    assert res_empty.is_compatible is None


def test_python_compatibility_invalid_specifier() -> None:
    """Test malformed Requires-Python strings are handled gracefully with UNVERIFIED."""
    res = evaluate_python_version("invalid>>>3.8", "3.11")
    assert res.status == CompatibilityStatus.UNVERIFIED
    assert res.is_compatible is None
    assert "Malformed Requires-Python constraint" in res.reason


def test_python_compatibility_prerelease_handling() -> None:
    """Test evaluation with future versions and prereleases (e.g. Python 3.14a1)."""
    # Target is prerelease
    res_pre = evaluate_python_version(">=3.10", "3.14.0a2", prereleases=True)
    assert res_pre.status == CompatibilityStatus.COMPATIBLE

    # Specifier excludes 3.14
    res_capped = evaluate_python_version(">=3.10, <3.14", "3.14.0a2", prereleases=True)
    assert res_capped.status == CompatibilityStatus.INCOMPATIBLE


def test_python_compatibility_version_object_input() -> None:
    """Test passing packaging Version object directly."""
    v = Version("3.12.1")
    res = evaluate_python_version(">=3.12", v)
    assert res.status == CompatibilityStatus.COMPATIBLE
    assert res.target_version == "3.12.1"

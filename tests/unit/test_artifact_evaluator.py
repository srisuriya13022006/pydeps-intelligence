"""Unit tests for artifact evaluator."""

from __future__ import annotations

from pydeps_intelligence.compatibility.artifact_evaluator import evaluate_release_artifacts
from pydeps_intelligence.metadata.metadata_models import PackageRelease, ReleaseArtifact
from pydeps_intelligence.models.compatibility import CompatibilityStatus
from pydeps_intelligence.models.project import (
    Architecture,
    OperatingSystem,
    PythonImplementation,
    TargetEnvironment,
)


def _sample_target() -> TargetEnvironment:
    return TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.LINUX,
        architecture=Architecture.X86_64,
        implementation=PythonImplementation.CPYTHON,
    )


def test_artifact_compatible_wheel() -> None:
    """Test release with compatible wheel artifact returns COMPATIBLE."""
    target = _sample_target()
    rel = PackageRelease(
        distribution_name="sample-pkg",
        version="1.0.0",
        release_files=[
            ReleaseArtifact(
                filename="sample_pkg-1.0.0-py3-none-any.whl",
                package_type="bdist_wheel",
            ),
            ReleaseArtifact(
                filename="sample_pkg-1.0.0.tar.gz",
                package_type="sdist",
            ),
        ],
    )
    res = evaluate_release_artifacts(rel, target)
    assert res.status == CompatibilityStatus.COMPATIBLE
    assert res.has_compatible_wheel is True
    assert "sample_pkg-1.0.0-py3-none-any.whl" in res.compatible_wheels
    assert res.has_sdist is True


def test_artifact_sdist_only_unverified() -> None:
    """Test release with only source distribution returns UNVERIFIED."""
    target = _sample_target()
    rel = PackageRelease(
        distribution_name="sdist-only",
        version="0.5.0",
        release_files=[
            ReleaseArtifact(
                filename="sdist_only-0.5.0.tar.gz",
                package_type="sdist",
            )
        ],
    )
    res = evaluate_release_artifacts(rel, target)
    assert res.status == CompatibilityStatus.UNVERIFIED
    assert res.has_compatible_wheel is False
    assert res.has_sdist is True
    assert res.sdist_filename == "sdist_only-0.5.0.tar.gz"
    assert any("requires runtime validation" in r for r in res.reasons)


def test_artifact_neither_wheel_nor_sdist() -> None:
    """Test release where wheels are incompatible and no sdist exists returns INCOMPATIBLE."""
    target = _sample_target()
    rel = PackageRelease(
        distribution_name="win-only",
        version="2.0.0",
        release_files=[
            ReleaseArtifact(
                filename="win_only-2.0.0-cp311-cp311-win_amd64.whl",
                package_type="bdist_wheel",
            )
        ],
    )
    res = evaluate_release_artifacts(rel, target)
    assert res.status == CompatibilityStatus.INCOMPATIBLE
    assert res.has_compatible_wheel is False
    assert res.has_sdist is False
    assert "win_only-2.0.0-cp311-cp311-win_amd64.whl" in res.incompatible_wheels


def test_artifact_empty_release_files() -> None:
    """Test release with no files declared returns UNVERIFIED."""
    target = _sample_target()
    rel = PackageRelease(
        distribution_name="empty-files",
        version="1.0.0",
        release_files=[],
    )
    res = evaluate_release_artifacts(rel, target)
    assert res.status == CompatibilityStatus.UNVERIFIED
    assert res.has_compatible_wheel is False
    assert res.has_sdist is False


def test_artifact_yanked_warnings() -> None:
    """Test yanked release and yanked artifact warnings."""
    target = _sample_target()
    rel = PackageRelease(
        distribution_name="yanked-pkg",
        version="1.0.1",
        yanked=True,
        yanked_reason="Critical bug in release",
        release_files=[
            ReleaseArtifact(
                filename="yanked_pkg-1.0.1-py3-none-any.whl",
                package_type="bdist_wheel",
                yanked=True,
            )
        ],
    )
    res = evaluate_release_artifacts(rel, target)
    assert res.has_compatible_wheel is True
    assert any("yanked on PyPI" in w for w in res.warnings)
    assert any("Critical bug in release" in w for w in res.warnings)

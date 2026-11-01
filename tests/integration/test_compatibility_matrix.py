"""Integration tests for CompatibilityMatrix across multiple targets, packages, and facade."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pydeps_intelligence.compatibility.compatibility_matrix import MatrixBuilder
from pydeps_intelligence.facade import PyDeps
from pydeps_intelligence.metadata.metadata_models import (
    MetadataResult,
    PackageRelease,
    ReleaseArtifact,
)
from pydeps_intelligence.models.compatibility import (
    CompatibilityMatrix,
    CompatibilityStatus,
)
from pydeps_intelligence.models.dependencies import Dependency
from pydeps_intelligence.models.project import (
    Architecture,
    OperatingSystem,
    PythonImplementation,
    TargetEnvironment,
)


@pytest.fixture
def sample_releases() -> dict[str, PackageRelease]:
    """Provide realistic fixture releases representing pure-Python, compiled, and sdist packages."""
    # 1. Pure Python universal package (requests)
    requests_rel = PackageRelease(
        distribution_name="requests",
        version="2.31.0",
        requires_python=">=3.7",
        requires_dist=[
            Dependency(name="urllib3", version_specifier="<3,>=1.21.1"),
            Dependency(name="pywin32", environment_marker="sys_platform == 'win32'"),
        ],
        release_files=[
            ReleaseArtifact(
                filename="requests-2.31.0-py3-none-any.whl",
                package_type="bdist_wheel",
            ),
            ReleaseArtifact(
                filename="requests-2.31.0.tar.gz",
                package_type="sdist",
            ),
        ],
    )

    # 2. CPython C-extension package (numpy)
    numpy_rel = PackageRelease(
        distribution_name="numpy",
        version="1.24.3",
        requires_python=">=3.8, <3.12",
        release_files=[
            # Linux x86_64
            ReleaseArtifact(
                filename="numpy-1.24.3-cp311-cp311-manylinux_2_17_x86_64.whl",
                package_type="bdist_wheel",
            ),
            # Windows x86_64
            ReleaseArtifact(
                filename="numpy-1.24.3-cp311-cp311-win_amd64.whl",
                package_type="bdist_wheel",
            ),
            # macOS arm64
            ReleaseArtifact(
                filename="numpy-1.24.3-cp311-cp311-macosx_11_0_arm64.whl",
                package_type="bdist_wheel",
            ),
        ],
    )

    # 3. Source-only legacy package without wheels
    sdist_rel = PackageRelease(
        distribution_name="legacy-sdist",
        version="0.1.0",
        requires_python=None,  # Missing requires_python
        release_files=[
            ReleaseArtifact(
                filename="legacy-sdist-0.1.0.tar.gz",
                package_type="sdist",
            )
        ],
    )

    return {
        "requests": requests_rel,
        "numpy": numpy_rel,
        "legacy-sdist": sdist_rel,
    }


def test_matrix_multi_target_evaluation(sample_releases: dict[str, PackageRelease]) -> None:
    """Test matrix evaluation across multiple Python versions, OSs, and architectures."""
    targets = [
        # Linux x86_64 CPython 3.11 (Both requests & numpy have binary wheels)
        TargetEnvironment(
            python_version="3.11",
            operating_system=OperatingSystem.LINUX,
            architecture=Architecture.X86_64,
            implementation=PythonImplementation.CPYTHON,
        ),
        # Windows x86_64 CPython 3.11 (Both requests & numpy have binary wheels)
        TargetEnvironment(
            python_version="3.11",
            operating_system=OperatingSystem.WINDOWS,
            architecture=Architecture.X86_64,
            implementation=PythonImplementation.CPYTHON,
        ),
        # Linux x86_64 CPython 3.14 (Python version exceeds numpy's <3.12 constraint)
        TargetEnvironment(
            python_version="3.14",
            operating_system=OperatingSystem.LINUX,
            architecture=Architecture.X86_64,
            implementation=PythonImplementation.CPYTHON,
        ),
        # Linux x86_64 PyPy 3.9 (PyPy lacks binary wheel for numpy 1.24.3)
        TargetEnvironment(
            python_version="3.9",
            operating_system=OperatingSystem.LINUX,
            architecture=Architecture.X86_64,
            implementation=PythonImplementation.PYPY,
        ),
    ]

    builder = MatrixBuilder()
    matrix = builder.evaluate_matrix(sample_releases, targets=targets)

    assert len(matrix.packages) == 3
    assert len(matrix.targets) == 4
    assert len(matrix.entries) == 12

    # 1. Requests: universal wheel matches all Python 3 targets
    # 3.11 Linux: COMPATIBLE
    res_req_linux = matrix.get_result("requests", targets[0])
    assert res_req_linux is not None
    assert res_req_linux.status == CompatibilityStatus.COMPATIBLE
    # pywin32 marker should be False on Linux
    pywin32_eval = next(
        m for m in res_req_linux.marker_evaluations if m.dependency_name == "pywin32"
    )
    assert pywin32_eval.applies is False

    # 3.11 Windows: COMPATIBLE, pywin32 applies
    res_req_win = matrix.get_result("requests", targets[1])
    assert res_req_win is not None
    assert res_req_win.status == CompatibilityStatus.COMPATIBLE
    win_marker = next(m for m in res_req_win.marker_evaluations if m.dependency_name == "pywin32")
    assert win_marker.applies is True

    # 2. Numpy:
    # 3.11 Linux: COMPATIBLE
    res_np_linux = matrix.get_result("numpy", targets[0])
    assert res_np_linux is not None
    assert res_np_linux.status == CompatibilityStatus.COMPATIBLE

    # 3.14 Linux: INCOMPATIBLE (exceeds <3.12)
    res_np_314 = matrix.get_result("numpy", targets[2])
    assert res_np_314 is not None
    assert res_np_314.status == CompatibilityStatus.INCOMPATIBLE
    assert "does not satisfy" in res_np_314.reason

    # PyPy 3.9: INCOMPATIBLE (no wheel and no sdist in release_files)
    res_np_pypy = matrix.get_result("numpy", targets[3])
    assert res_np_pypy is not None
    assert res_np_pypy.status == CompatibilityStatus.INCOMPATIBLE

    # 3. Legacy-sdist: UNVERIFIED across all targets (missing requires_python, only sdist available)
    for t in targets:
        res_legacy = matrix.get_result("legacy-sdist", t)
        assert res_legacy is not None
        assert res_legacy.status == CompatibilityStatus.UNVERIFIED


def test_matrix_json_serialization(sample_releases: dict[str, PackageRelease]) -> None:
    """Test that CompatibilityMatrix serializes cleanly to structured JSON and deserializes."""
    target = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.LINUX,
        architecture=Architecture.X86_64,
    )
    builder = MatrixBuilder()
    matrix = builder.evaluate_matrix(sample_releases, targets=[target])

    json_str = matrix.model_dump_json(indent=2)
    parsed = json.loads(json_str)

    assert "packages" in parsed
    assert "targets" in parsed
    assert "entries" in parsed
    assert "matrix" in parsed
    assert len(parsed["packages"]) == 3

    # Roundtrip validation
    reloaded = CompatibilityMatrix.model_validate(parsed)
    assert len(reloaded.packages) == 3
    assert len(reloaded.entries) == 3


def test_facade_check_compatibility_integration(
    tmp_path: Path, sample_releases: dict[str, PackageRelease]
) -> None:
    """Test PyDeps.check_compatibility() facade method."""
    engine = PyDeps(project_path=tmp_path)
    target = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )

    # Convert sample releases to MetadataResult mapping
    metadata_map = {
        name: MetadataResult(
            success=True,
            package_name=name,
            version=rel.version,
            metadata=rel,
            source="mock",
        )
        for name, rel in sample_releases.items()
    }

    matrix = engine.check_compatibility(metadata=metadata_map, targets=[target])
    assert isinstance(matrix, CompatibilityMatrix)
    assert len(matrix.packages) == 3
    assert matrix.summary()["total_evaluations"] == 3

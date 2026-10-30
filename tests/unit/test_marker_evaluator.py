"""Unit tests for PEP 508 environment marker evaluator."""

from __future__ import annotations

from pydeps.compatibility.marker_evaluator import MarkerEvaluator
from pydeps.compatibility.platform_profiles import TargetPlatformProfile
from pydeps.models.compatibility import CompatibilityStatus
from pydeps.models.dependencies import Dependency
from pydeps.models.project import (
    Architecture,
    OperatingSystem,
    PythonImplementation,
    TargetEnvironment,
)


def _make_target(
    os: OperatingSystem = OperatingSystem.LINUX,
    arch: Architecture = Architecture.X86_64,
    py: str = "3.11",
    impl: PythonImplementation = PythonImplementation.CPYTHON,
) -> TargetEnvironment:
    return TargetEnvironment(
        python_version=py,
        operating_system=os,
        architecture=arch,
        implementation=impl,
    )


def test_marker_unconditional_dependency() -> None:
    """Test dependency without environment marker applies unconditionally."""
    target = _make_target()
    evaluator = MarkerEvaluator(target=target)
    dep = Dependency(name="requests", version_specifier=">=2.0.0", environment_marker=None)

    res = evaluator.evaluate_dependency(dep)
    assert res.status == CompatibilityStatus.COMPATIBLE
    assert res.applies is True
    assert "Unconditional dependency" in res.explanation


def test_marker_os_and_platform_system() -> None:
    """Test OS-specific markers (Windows vs Linux vs macOS)."""
    linux_target = _make_target(os=OperatingSystem.LINUX)
    windows_target = _make_target(os=OperatingSystem.WINDOWS)
    macos_target = _make_target(os=OperatingSystem.MACOS)

    dep_win = Dependency(name="pywin32", environment_marker="os_name == 'nt'")
    dep_linux = Dependency(name="pyinotify", environment_marker="sys_platform == 'linux'")
    dep_mac = Dependency(name="pyobjc", environment_marker="sys_platform == 'darwin'")

    # Linux target
    eval_linux = MarkerEvaluator(target=linux_target)
    assert eval_linux.evaluate_dependency(dep_win).applies is False
    assert eval_linux.evaluate_dependency(dep_linux).applies is True
    assert eval_linux.evaluate_dependency(dep_mac).applies is False

    # Windows target
    eval_win = MarkerEvaluator(target=windows_target)
    assert eval_win.evaluate_dependency(dep_win).applies is True
    assert eval_win.evaluate_dependency(dep_linux).applies is False
    assert eval_win.evaluate_dependency(dep_mac).applies is False

    # macOS target
    eval_mac = MarkerEvaluator(target=macos_target)
    assert eval_mac.evaluate_dependency(dep_win).applies is False
    assert eval_mac.evaluate_dependency(dep_linux).applies is False
    assert eval_mac.evaluate_dependency(dep_mac).applies is True


def test_marker_python_version_and_machine() -> None:
    """Test Python version and machine architecture markers."""
    target_311 = _make_target(arch=Architecture.X86_64, py="3.11")
    evaluator = MarkerEvaluator(target=target_311)

    dep_old = Dependency(name="typing-extensions", environment_marker="python_version < '3.10'")
    dep_current = Dependency(name="tomli", environment_marker="python_version < '3.11'")
    dep_arch = Dependency(name="intel-mkl", environment_marker="platform_machine == 'x86_64'")

    assert evaluator.evaluate_dependency(dep_old).applies is False
    assert evaluator.evaluate_dependency(dep_current).applies is False
    assert evaluator.evaluate_dependency(dep_arch).applies is True


def test_marker_implementation_cpython_vs_pypy() -> None:
    """Test implementation markers distinguishing CPython and PyPy."""
    cpython_target = _make_target(impl=PythonImplementation.CPYTHON)
    pypy_target = _make_target(impl=PythonImplementation.PYPY)

    dep_cpython = Dependency(
        name="numpy", environment_marker="platform_python_implementation == 'CPython'"
    )
    dep_pypy = Dependency(
        name="pypy-tools", environment_marker="platform_python_implementation == 'PyPy'"
    )

    eval_cpython = MarkerEvaluator(target=cpython_target)
    assert eval_cpython.evaluate_dependency(dep_cpython).applies is True
    assert eval_cpython.evaluate_dependency(dep_pypy).applies is False

    eval_pypy = MarkerEvaluator(target=pypy_target)
    assert eval_pypy.evaluate_dependency(dep_cpython).applies is False
    assert eval_pypy.evaluate_dependency(dep_pypy).applies is True


def test_marker_extras_handling() -> None:
    """Test evaluation of dependency markers with extra options."""
    target = _make_target()
    evaluator = MarkerEvaluator(target=target)

    dep_dev = Dependency(name="pytest", environment_marker="extra == 'dev'")

    # Default (no extra specified): does not apply
    assert evaluator.evaluate_dependency(dep_dev, extra=None).applies is False

    # Different extra: does not apply
    assert evaluator.evaluate_dependency(dep_dev, extra="test").applies is False

    # Matching extra: applies
    assert evaluator.evaluate_dependency(dep_dev, extra="dev").applies is True


def test_marker_missing_profile_field_unverified() -> None:
    """Test that missing target profile fields return UNVERIFIED without falling back to host."""
    target = _make_target()
    # Explicit sparse profile without platform_release
    sparse_profile = TargetPlatformProfile(
        sys_platform="linux",
        os_name="posix",
        platform_machine="x86_64",
        platform_release=None,  # Missing
    )
    evaluator = MarkerEvaluator(target=target, profile=sparse_profile)

    dep_kernel = Dependency(name="kernel-pkg", environment_marker="platform_release >= '5.10'")
    res = evaluator.evaluate_dependency(dep_kernel)

    assert res.status == CompatibilityStatus.UNVERIFIED
    assert res.applies is None
    assert "platform_release" in res.missing_fields
    assert "Evaluation unverified" in res.explanation


def test_marker_malformed_syntax() -> None:
    """Test handling of invalid marker expressions."""
    from unittest.mock import MagicMock

    import pytest

    # 1. Dependency validation catches invalid marker on creation
    with pytest.raises(ValueError, match="Invalid environment marker"):
        Dependency(name="bad", environment_marker="os_name >>> 'nt'")

    # 2. MarkerEvaluator handles unparseable marker gracefully
    target = _make_target()
    evaluator = MarkerEvaluator(target=target)

    mock_dep = MagicMock()
    mock_dep.name = "bad"
    mock_dep.environment_marker = "os_name >>> 'nt'"
    mock_dep.to_pep508.return_value = "bad; os_name >>> 'nt'"

    res = evaluator.evaluate_dependency(mock_dep)
    assert res.status == CompatibilityStatus.UNVERIFIED
    assert res.applies is None
    assert "Malformed PEP 508" in res.explanation

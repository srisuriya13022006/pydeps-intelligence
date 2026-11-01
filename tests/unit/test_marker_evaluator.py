"""Unit tests for PEP 508 environment marker evaluator."""

from __future__ import annotations

from pydeps_intelligence.compatibility.marker_evaluator import MarkerEvaluator
from pydeps_intelligence.compatibility.platform_profiles import TargetPlatformProfile
from pydeps_intelligence.models.compatibility import CompatibilityStatus
from pydeps_intelligence.models.dependencies import Dependency
from pydeps_intelligence.models.project import (
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


def test_marker_isolation_windows_target() -> None:
    """Regression test: Windows target markers are isolated from host environment."""
    win_target = _make_target(os=OperatingSystem.WINDOWS, arch=Architecture.X86_64)
    evaluator = MarkerEvaluator(target=win_target)

    dep_win_nt = Dependency(name="win-nt", environment_marker="os_name == 'nt'")
    dep_win_sys = Dependency(name="win-sys", environment_marker="sys_platform == 'win32'")
    dep_linux_sys = Dependency(name="lin-sys", environment_marker="sys_platform == 'linux'")
    dep_darwin_sys = Dependency(name="mac-sys", environment_marker="sys_platform == 'darwin'")

    assert evaluator.evaluate_dependency(dep_win_nt).applies is True
    assert evaluator.evaluate_dependency(dep_win_sys).applies is True
    assert evaluator.evaluate_dependency(dep_linux_sys).applies is False
    assert evaluator.evaluate_dependency(dep_darwin_sys).applies is False


def test_marker_isolation_linux_target() -> None:
    """Regression test: Linux target markers are isolated from host environment."""
    linux_target = _make_target(os=OperatingSystem.LINUX, arch=Architecture.AARCH64)
    evaluator = MarkerEvaluator(target=linux_target)

    dep_posix = Dependency(name="posix-pkg", environment_marker="os_name == 'posix'")
    dep_linux = Dependency(name="linux-pkg", environment_marker="sys_platform == 'linux'")
    dep_win = Dependency(name="win-pkg", environment_marker="sys_platform == 'win32'")
    dep_machine = Dependency(name="arm-pkg", environment_marker="platform_machine == 'aarch64'")
    dep_x86 = Dependency(name="x86-pkg", environment_marker="platform_machine == 'x86_64'")

    assert evaluator.evaluate_dependency(dep_posix).applies is True
    assert evaluator.evaluate_dependency(dep_linux).applies is True
    assert evaluator.evaluate_dependency(dep_win).applies is False
    assert evaluator.evaluate_dependency(dep_machine).applies is True
    assert evaluator.evaluate_dependency(dep_x86).applies is False


def test_marker_isolation_macos_target() -> None:
    """Regression test: macOS target markers are isolated from host environment."""
    mac_target = _make_target(os=OperatingSystem.MACOS, arch=Architecture.ARM64)
    evaluator = MarkerEvaluator(target=mac_target)

    dep_darwin = Dependency(name="mac-pkg", environment_marker="sys_platform == 'darwin'")
    dep_linux = Dependency(name="lin-pkg", environment_marker="sys_platform == 'linux'")
    dep_win = Dependency(name="win-pkg", environment_marker="sys_platform == 'win32'")
    dep_arm = Dependency(name="arm-pkg", environment_marker="platform_machine == 'arm64'")

    assert evaluator.evaluate_dependency(dep_darwin).applies is True
    assert evaluator.evaluate_dependency(dep_linux).applies is False
    assert evaluator.evaluate_dependency(dep_win).applies is False
    assert evaluator.evaluate_dependency(dep_arm).applies is True


def test_marker_guarded_variable_extraction_fallback() -> None:
    """Regression test: guarded marker variable extraction works with or without _markers AST."""
    from packaging.markers import Marker

    from pydeps_intelligence.compatibility.marker_evaluator import extract_marker_variables

    marker = Marker("sys_platform == 'linux' and python_version >= '3.11' and os_name == 'posix'")
    vars_found = extract_marker_variables(marker)
    assert "sys_platform" in vars_found
    assert "python_version" in vars_found
    assert "os_name" in vars_found

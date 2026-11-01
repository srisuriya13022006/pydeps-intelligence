"""Unit tests for wheel filename tag compatibility."""

from __future__ import annotations

from pydeps_intelligence.compatibility.platform_profiles import (
    create_platform_profile,
    get_supported_wheel_tags,
)
from pydeps_intelligence.compatibility.wheel_compatibility import evaluate_wheel_filename
from pydeps_intelligence.models.project import (
    Architecture,
    OperatingSystem,
    PythonImplementation,
    TargetEnvironment,
)


def _tags_for(
    os: OperatingSystem = OperatingSystem.LINUX,
    arch: Architecture = Architecture.X86_64,
    py: str = "3.11",
    impl: PythonImplementation = PythonImplementation.CPYTHON,
):
    target = TargetEnvironment(
        python_version=py,
        operating_system=os,
        architecture=arch,
        implementation=impl,
    )
    profile = create_platform_profile(target)
    return get_supported_wheel_tags(target, profile=profile)


def test_universal_wheel_compatibility() -> None:
    """Test pure Python universal wheels match all operating systems and architectures."""
    linux_tags = _tags_for(os=OperatingSystem.LINUX)
    win_tags = _tags_for(os=OperatingSystem.WINDOWS)
    mac_tags = _tags_for(os=OperatingSystem.MACOS)

    whl_py3 = "requests-2.31.0-py3-none-any.whl"
    whl_universal = "six-1.16.0-py2.py3-none-any.whl"

    for tags in (linux_tags, win_tags, mac_tags):
        res_py3 = evaluate_wheel_filename(whl_py3, tags)
        assert res_py3.is_compatible is True
        assert any("py3-none-any" in str(t) for t in res_py3.matching_tags)

        res_uni = evaluate_wheel_filename(whl_universal, tags)
        assert res_uni.is_compatible is True


def test_cpython_abi_and_abi3_wheels() -> None:
    """Test CPython-specific ABI wheels and stable abi3 wheels."""
    cpython_tags = _tags_for(os=OperatingSystem.LINUX, py="3.11", impl=PythonImplementation.CPYTHON)
    pypy_tags = _tags_for(os=OperatingSystem.LINUX, py="3.9", impl=PythonImplementation.PYPY)

    # Exact ABI wheel for cp311
    cp311_whl = "numpy-1.24.3-cp311-cp311-manylinux_2_17_x86_64.whl"
    res_cp311 = evaluate_wheel_filename(cp311_whl, cpython_tags)
    assert res_cp311.is_compatible is True

    # Incompatible cp310 wheel on cp311 target
    cp310_whl = "numpy-1.24.3-cp310-cp310-manylinux_2_17_x86_64.whl"
    assert evaluate_wheel_filename(cp310_whl, cpython_tags).is_compatible is False

    # abi3 wheel on CPython 3.11 (compatible)
    abi3_whl = "cryptography-41.0.1-cp37-abi3-manylinux_2_17_x86_64.whl"
    assert evaluate_wheel_filename(abi3_whl, cpython_tags).is_compatible is True

    # abi3 wheel on PyPy (incompatible)
    assert evaluate_wheel_filename(abi3_whl, pypy_tags).is_compatible is False


def test_pypy_wheel_compatibility() -> None:
    """Test PyPy-specific wheel tags."""
    pypy_tags = _tags_for(os=OperatingSystem.LINUX, py="3.9", impl=PythonImplementation.PYPY)
    cpython_tags = _tags_for(os=OperatingSystem.LINUX, py="3.9", impl=PythonImplementation.CPYTHON)

    pp_whl = "typed_ast-1.5.4-pp39-pypy39_pp73-manylinux_2_17_x86_64.whl"
    assert evaluate_wheel_filename(pp_whl, pypy_tags).is_compatible is True
    assert evaluate_wheel_filename(pp_whl, cpython_tags).is_compatible is False


def test_windows_wheel_compatibility() -> None:
    """Test Windows wheel tags on win_amd64 and win_arm64."""
    win_x64_tags = _tags_for(os=OperatingSystem.WINDOWS, arch=Architecture.X86_64)
    win_arm_tags = _tags_for(os=OperatingSystem.WINDOWS, arch=Architecture.ARM64)
    linux_tags = _tags_for(os=OperatingSystem.LINUX, arch=Architecture.X86_64)

    win_whl = "scipy-1.10.1-cp311-cp311-win_amd64.whl"
    win_arm_whl = "scipy-1.10.1-cp311-cp311-win_arm64.whl"

    assert evaluate_wheel_filename(win_whl, win_x64_tags).is_compatible is True
    assert evaluate_wheel_filename(win_whl, win_arm_tags).is_compatible is False
    assert evaluate_wheel_filename(win_whl, linux_tags).is_compatible is False

    assert evaluate_wheel_filename(win_arm_whl, win_arm_tags).is_compatible is True


def test_macos_wheel_compatibility() -> None:
    """Test macOS wheels across x86_64, arm64, and universal2."""
    mac_arm_tags = _tags_for(os=OperatingSystem.MACOS, arch=Architecture.ARM64)
    mac_x64_tags = _tags_for(os=OperatingSystem.MACOS, arch=Architecture.X86_64)

    arm_whl = "scipy-1.10.1-cp311-cp311-macosx_11_0_arm64.whl"
    x64_whl = "scipy-1.10.1-cp311-cp311-macosx_10_9_x86_64.whl"
    uni_whl = "cffi-1.15.1-cp311-cp311-macosx_10_9_universal2.whl"
    newer_mac12_whl = "scipy-1.10.1-cp311-cp311-macosx_12_0_arm64.whl"

    # arm64 matches arm64 and universal2
    assert evaluate_wheel_filename(arm_whl, mac_arm_tags).is_compatible is True
    assert evaluate_wheel_filename(uni_whl, mac_arm_tags).is_compatible is True
    assert evaluate_wheel_filename(x64_whl, mac_arm_tags).is_compatible is False
    # macosx_12_0 requires macOS 12+, incompatible with default macOS 11 target
    assert evaluate_wheel_filename(newer_mac12_whl, mac_arm_tags).is_compatible is False

    # x86_64 matches x86_64 and universal2
    assert evaluate_wheel_filename(x64_whl, mac_x64_tags).is_compatible is True
    assert evaluate_wheel_filename(uni_whl, mac_x64_tags).is_compatible is True
    assert evaluate_wheel_filename(arm_whl, mac_x64_tags).is_compatible is False


def test_linux_manylinux_and_musllinux() -> None:
    """Test Linux glibc and musl wheel tags."""
    linux_x64_tags = _tags_for(os=OperatingSystem.LINUX, arch=Architecture.X86_64)

    whl_2014 = "torch-2.0.0-cp311-cp311-manylinux2014_x86_64.whl"
    whl_2_17 = "torch-2.0.0-cp311-cp311-manylinux_2_17_x86_64.whl"
    whl_musl = "torch-2.0.0-cp311-cp311-musllinux_1_1_x86_64.whl"

    assert evaluate_wheel_filename(whl_2014, linux_x64_tags).is_compatible is True
    assert evaluate_wheel_filename(whl_2_17, linux_x64_tags).is_compatible is True
    assert evaluate_wheel_filename(whl_musl, linux_x64_tags).is_compatible is True


def test_wheel_artifact_requires_python_mismatch() -> None:
    """Test wheel matching platform tags but failing artifact Requires-Python."""
    linux_tags = _tags_for(os=OperatingSystem.LINUX, py="3.9")
    whl = "pkg-1.0-py3-none-any.whl"

    # Fails because target is 3.9 but artifact requires >=3.10
    res = evaluate_wheel_filename(
        filename=whl,
        supported_tags=linux_tags,
        target_python_version="3.9",
        artifact_requires_python=">=3.10",
    )
    assert res.is_compatible is False
    assert "constraint" in res.reason


def test_invalid_wheel_filename() -> None:
    """Test handling of unparseable wheel filenames."""
    tags = _tags_for()
    res = evaluate_wheel_filename("not-a-valid-wheel-name.whl", tags)
    assert res.is_compatible is False
    assert res.is_invalid is True
    assert "Invalid wheel filename syntax" in res.reason

"""Unit tests for platform profiles and target configuration feasibility."""

from __future__ import annotations

from pydeps_intelligence.compatibility.platform_profiles import (
    TargetPlatformProfile,
    create_platform_profile,
    is_valid_target_configuration,
)
from pydeps_intelligence.models.project import (
    Architecture,
    OperatingSystem,
    PythonImplementation,
    TargetEnvironment,
)


def test_platform_profile_linux_x86_64() -> None:
    """Test Linux x86_64 profile construction."""
    target = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.LINUX,
        architecture=Architecture.X86_64,
        implementation=PythonImplementation.CPYTHON,
    )
    prof = create_platform_profile(target)
    assert prof.sys_platform == "linux"
    assert prof.os_name == "posix"
    assert prof.platform_system == "Linux"
    assert prof.platform_machine == "x86_64"
    assert prof.platform_python_implementation == "CPython"
    assert prof.python_abi == "cp311"
    assert "manylinux_2_28" in (prof.manylinux_policy or [])


def test_platform_profile_windows_amd64() -> None:
    """Test Windows AMD64 profile construction."""
    target = TargetEnvironment(
        python_version="3.10",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
        implementation=PythonImplementation.CPYTHON,
    )
    prof = create_platform_profile(target)
    assert prof.sys_platform == "win32"
    assert prof.os_name == "nt"
    assert prof.platform_system == "Windows"
    assert prof.platform_machine == "AMD64"
    assert prof.windows_platform_tag == "win_amd64"


def test_platform_profile_macos_arm64() -> None:
    """Test macOS ARM64 profile construction."""
    target = TargetEnvironment(
        python_version="3.12",
        operating_system=OperatingSystem.MACOS,
        architecture=Architecture.ARM64,
        implementation=PythonImplementation.CPYTHON,
    )
    prof = create_platform_profile(target)
    assert prof.sys_platform == "darwin"
    assert prof.os_name == "posix"
    assert prof.platform_system == "Darwin"
    assert prof.platform_machine == "arm64"
    assert prof.macos_deployment_target == "11_0"


def test_platform_profile_overrides() -> None:
    """Test user-defined profile overrides."""
    target = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.LINUX,
        architecture=Architecture.X86_64,
    )
    prof = create_platform_profile(
        target,
        overrides={"platform_release": "5.15.0-generic", "python_abi": "custom_abi"},
    )
    assert prof.platform_release == "5.15.0-generic"
    assert prof.python_abi == "custom_abi"


def test_marker_environment_and_missing_keys() -> None:
    """Test conversion to marker dictionary and detection of missing keys."""
    prof = TargetPlatformProfile(
        sys_platform="linux",
        os_name="posix",
        platform_machine="x86_64",
    )
    env = prof.to_marker_environment(extra="test")
    assert env["sys_platform"] == "linux"
    assert env["os_name"] == "posix"
    assert env["extra"] == "test"
    assert "platform_release" not in env

    # Check missing fields
    missing = prof.check_missing_marker_fields({"sys_platform", "platform_release", "extra"})
    assert "platform_release" in missing
    assert "sys_platform" not in missing


def test_is_valid_target_configuration() -> None:
    """Test detection of impossible or unsupported target combinations."""
    # Valid
    valid_target = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.LINUX,
        architecture=Architecture.X86_64,
    )
    is_valid, _ = is_valid_target_configuration(valid_target)
    assert is_valid is True

    # Invalid: macOS 32-bit x86
    invalid_mac = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.MACOS,
        architecture=Architecture.X86,
    )
    is_valid_mac, reason = is_valid_target_configuration(invalid_mac)
    assert is_valid_mac is False
    assert "macOS does not support 32-bit" in (reason or "")

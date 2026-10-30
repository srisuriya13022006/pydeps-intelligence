"""Platform profile models and target-compatible wheel tag generators."""

from __future__ import annotations

from typing import Any

from packaging.tags import (
    Tag,
    compatible_tags,
    cpython_tags,
    generic_tags,
    mac_platforms,
    parse_tag,
    pure_python_tags,
)
from packaging.version import Version
from pydantic import BaseModel, ConfigDict, Field

from pydeps.models.project import (
    Architecture,
    OperatingSystem,
    PythonImplementation,
    TargetEnvironment,
)


class TargetPlatformProfile(BaseModel):
    """Detailed platform environment profile for cross-platform evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sys_platform: str | None = Field(
        default=None,
        description="Value of sys.platform (e.g. 'linux', 'win32', 'darwin')",
    )
    os_name: str | None = Field(
        default=None,
        description="Value of os.name (e.g. 'posix', 'nt')",
    )
    platform_machine: str | None = Field(
        default=None,
        description="Hardware machine identifier (e.g. 'x86_64', 'AMD64', 'arm64', 'aarch64')",
    )
    platform_system: str | None = Field(
        default=None,
        description="Operating system name from platform.system() ('Linux', 'Windows', 'Darwin')",
    )
    platform_release: str | None = Field(
        default=None,
        description="OS release string from platform.release()",
    )
    platform_version: str | None = Field(
        default=None,
        description="OS version string from platform.version()",
    )
    implementation_name: str | None = Field(
        default=None,
        description="Python implementation name (e.g. 'cpython', 'pypy')",
    )
    implementation_version: str | None = Field(
        default=None,
        description="Python implementation release version",
    )
    platform_python_implementation: str | None = Field(
        default=None,
        description="Canonical implementation string (e.g. 'CPython', 'PyPy')",
    )
    python_version: str | None = Field(
        default=None,
        description="Major.minor Python version string ('3.10', '3.11')",
    )
    python_full_version: str | None = Field(
        default=None,
        description="Full Python version string (e.g. '3.11.9')",
    )
    python_abi: str | None = Field(
        default=None,
        description="Target Python ABI tag (e.g. 'cp311', 'abi3', 'pypy39_pp73')",
    )
    manylinux_policy: list[str] | None = Field(
        default=None,
        description="Supported Linux glibc policies (e.g. ['manylinux_2_28', 'manylinux_2_17'])",
    )
    musllinux_policy: list[str] | None = Field(
        default=None,
        description="Supported musllinux policies (e.g. ['musllinux_1_2', 'musllinux_1_1'])",
    )
    macos_deployment_target: str | None = Field(
        default=None,
        description="macOS deployment target version string (e.g. '11_0', '12_0', '10_9')",
    )
    macos_arch: str | None = Field(
        default=None,
        description="macOS architecture identifier (e.g. 'arm64', 'x86_64', 'universal2')",
    )
    windows_platform_tag: str | None = Field(
        default=None,
        description="Windows platform tag (e.g. 'win_amd64', 'win_arm64', 'win32')",
    )
    supported_tags: list[str] | None = Field(
        default=None,
        description="Explicit list of supported wheel tags, overriding standard generation",
    )

    def to_marker_environment(self, extra: str | None = None) -> dict[str, str]:
        """Construct dictionary containing only explicitly known marker variables."""
        env: dict[str, str] = {}
        fields = [
            "sys_platform",
            "os_name",
            "platform_machine",
            "platform_system",
            "platform_release",
            "platform_version",
            "implementation_name",
            "implementation_version",
            "platform_python_implementation",
            "python_version",
            "python_full_version",
        ]
        for field in fields:
            val = getattr(self, field)
            if val is not None:
                env[field] = str(val)

        # extra is optional in PEP 508
        if extra is not None:
            env["extra"] = extra
        else:
            env["extra"] = ""

        return env

    def get_known_marker_keys(self) -> set[str]:
        """Return the set of marker variable names that are explicitly defined in this profile."""
        env = self.to_marker_environment()
        return set(env.keys())

    def check_missing_marker_fields(self, required_fields: set[str]) -> list[str]:
        """Identify which fields in required_fields are missing from this profile."""
        known = self.get_known_marker_keys()
        return sorted(list(required_fields - known))


def is_valid_target_configuration(target: TargetEnvironment) -> tuple[bool, str | None]:
    """Check whether a target environment represents a valid, feasible system configuration."""
    os = target.operating_system
    arch = target.architecture
    impl = target.implementation

    # macOS on 32-bit x86 was dropped before modern Python 3.8+
    if os == OperatingSystem.MACOS and arch == Architecture.X86:
        return False, "macOS does not support 32-bit x86 on modern Python versions"

    # PyPy availability
    if impl == PythonImplementation.PYPY and arch == Architecture.X86:
        return False, "PyPy on 32-bit architecture is not standardly supported"

    return True, None


def create_platform_profile(
    target: TargetEnvironment,
    overrides: dict[str, Any] | None = None,
) -> TargetPlatformProfile:
    """Build a comprehensive TargetPlatformProfile from a TargetEnvironment."""
    os = target.operating_system
    arch = target.architecture
    impl = target.implementation
    py_ver = target.python_version

    parsed_ver = Version(py_ver)
    major = parsed_ver.major
    minor = parsed_ver.minor
    full_ver = f"{major}.{minor}.0" if len(parsed_ver.release) < 3 else str(parsed_ver)

    # Defaults by OS
    if os == OperatingSystem.LINUX:
        sys_platform = "linux"
        os_name = "posix"
        platform_system = "Linux"
        if arch in (Architecture.AARCH64, Architecture.ARM64):
            machine = "aarch64"
            manylinux = ["manylinux_2_28", "manylinux_2_17", "manylinux2014"]
        elif arch == Architecture.X86:
            machine = "i686"
            manylinux = [
                "manylinux_2_28",
                "manylinux_2_17",
                "manylinux2014",
                "manylinux2010",
                "manylinux1",
            ]
        else:
            machine = "x86_64"
            manylinux = [
                "manylinux_2_28",
                "manylinux_2_17",
                "manylinux2014",
                "manylinux2010",
                "manylinux1",
            ]

        musllinux = ["musllinux_1_2", "musllinux_1_1"]
        macos_deployment = None
        macos_arch = None
        win_tag = None

    elif os == OperatingSystem.WINDOWS:
        sys_platform = "win32"
        os_name = "nt"
        platform_system = "Windows"
        if arch in (Architecture.AARCH64, Architecture.ARM64):
            machine = "ARM64"
            win_tag = "win_arm64"
        elif arch == Architecture.X86:
            machine = "x86"
            win_tag = "win32"
        else:
            machine = "AMD64"
            win_tag = "win_amd64"

        manylinux = None
        musllinux = None
        macos_deployment = None
        macos_arch = None

    elif os == OperatingSystem.MACOS:
        sys_platform = "darwin"
        os_name = "posix"
        platform_system = "Darwin"
        if arch in (Architecture.AARCH64, Architecture.ARM64):
            machine = "arm64"
            macos_arch = "arm64"
            macos_deployment = "11_0"
        else:
            machine = "x86_64"
            macos_arch = "x86_64"
            macos_deployment = "10_9"

        manylinux = None
        musllinux = None
        win_tag = None

    else:
        sys_platform = os.value
        os_name = "posix"
        platform_system = os.value.capitalize()
        machine = arch.value
        manylinux = None
        musllinux = None
        macos_deployment = None
        macos_arch = None
        win_tag = None

    if impl == PythonImplementation.CPYTHON:
        impl_name = "cpython"
        impl_platform = "CPython"
        impl_version = full_ver
        abi = f"cp{major}{minor}"
    else:
        impl_name = "pypy"
        impl_platform = "PyPy"
        impl_version = "7.3.11"
        abi = f"pypy{major}{minor}_pp73"

    profile_data: dict[str, Any] = {
        "sys_platform": sys_platform,
        "os_name": os_name,
        "platform_machine": machine,
        "platform_system": platform_system,
        "platform_release": None,  # Intentionally None unless explicitly supplied
        "platform_version": None,  # Intentionally None unless explicitly supplied
        "implementation_name": impl_name,
        "implementation_version": impl_version,
        "platform_python_implementation": impl_platform,
        "python_version": f"{major}.{minor}",
        "python_full_version": full_ver,
        "python_abi": abi,
        "manylinux_policy": manylinux,
        "musllinux_policy": musllinux,
        "macos_deployment_target": macos_deployment,
        "macos_arch": macos_arch,
        "windows_platform_tag": win_tag,
        "supported_tags": None,
    }

    if overrides:
        profile_data.update(overrides)

    return TargetPlatformProfile(**profile_data)


def get_supported_wheel_tags(
    target: TargetEnvironment,
    profile: TargetPlatformProfile | None = None,
) -> frozenset[Tag]:
    """Calculate the complete set of compatible wheel tags for the target environment."""
    prof = profile or create_platform_profile(target)

    # 1. If explicit supported tags are specified in the profile, use them directly
    if prof.supported_tags:
        tags: set[Tag] = set()
        for t in prof.supported_tags:
            tags.update(parse_tag(t))
        return frozenset(tags)

    parsed_ver = Version(target.python_version)
    py_tuple = (parsed_ver.major, parsed_ver.minor)
    major, minor = py_tuple

    # 2. Derive platforms list
    platforms: list[str] = []
    if target.operating_system == OperatingSystem.WINDOWS:
        if prof.windows_platform_tag:
            platforms.append(prof.windows_platform_tag)

    elif target.operating_system == OperatingSystem.MACOS:
        deploy_str = prof.macos_deployment_target or "11_0"
        parts = deploy_str.split("_")
        deploy_tuple = (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
        arch_str = prof.macos_arch or target.architecture.value
        try:
            platforms.extend(list(mac_platforms(deploy_tuple, arch_str)))
        except Exception:
            platforms.append(f"macosx_{deploy_str}_{arch_str}")

    elif target.operating_system == OperatingSystem.LINUX:
        arch_name = (
            "x86_64"
            if target.architecture == Architecture.X86_64
            else (
                "aarch64"
                if target.architecture in (Architecture.AARCH64, Architecture.ARM64)
                else "i686"
            )
        )
        if prof.manylinux_policy:
            for policy in prof.manylinux_policy:
                platforms.append(f"{policy}_{arch_name}")
        if prof.musllinux_policy:
            for musl in prof.musllinux_policy:
                platforms.append(f"{musl}_{arch_name}")
        platforms.append(f"linux_{arch_name}")

    tags_set: set[Tag] = set()

    # 3. Add interpreter-specific & ABI tags
    if target.implementation == PythonImplementation.CPYTHON:
        abis = [f"cp{major}{minor}"]
        # Python 3.2+ on Linux/macOS/Windows standardly supports abi3
        if minor >= 2:
            abis.append("abi3")
        abis.append("none")

        tags_set.update(cpython_tags(python_version=py_tuple, abis=abis, platforms=platforms))
        tags_set.update(
            compatible_tags(
                python_version=py_tuple, interpreter=f"cp{major}{minor}", platforms=platforms
            )
        )
    else:
        # PyPy
        pypy_abi = prof.python_abi or f"pypy{major}{minor}_pp73"
        abis = [pypy_abi, "none"]
        interp = f"pp{major}{minor}"
        tags_set.update(generic_tags(interpreter=interp, abis=abis, platforms=platforms))
        tags_set.update(
            compatible_tags(python_version=py_tuple, interpreter=interp, platforms=platforms)
        )

    # 4. Add pure python tags (e.g. py3-none-any)
    tags_set.update(pure_python_tags(python_version=py_tuple))

    return frozenset(tags_set)

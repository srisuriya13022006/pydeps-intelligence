"""Project configuration and target environment data models."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field, field_validator


class OperatingSystem(str, Enum):
    """Supported target operating systems."""

    LINUX = "linux"
    WINDOWS = "windows"
    MACOS = "macos"

    @classmethod
    def _missing_(cls, value: object) -> Any:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("darwin", "osx", "mac"):
                return cls.MACOS
            if normalized in ("win32", "win", "windows_nt"):
                return cls.WINDOWS
            if normalized in ("linux", "ubuntu", "debian", "centos", "rhel", "alpine"):
                return cls.LINUX
        return super()._missing_(value)


class Architecture(str, Enum):
    """Supported target machine architectures."""

    X86_64 = "x86_64"
    AARCH64 = "aarch64"
    ARM64 = "arm64"
    X86 = "x86"

    @classmethod
    def _missing_(cls, value: object) -> Any:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("amd64", "x64"):
                return cls.X86_64
            if normalized in ("i386", "i686", "win32"):
                return cls.X86
            if normalized in ("armv8", "armv8l", "armv8a"):
                return cls.AARCH64
        return super()._missing_(value)


class PythonImplementation(str, Enum):
    """Supported target Python implementations."""

    CPYTHON = "cpython"
    PYPY = "pypy"


DEFAULT_EXCLUDED_DIRECTORIES: list[str] = [
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "ENV",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    "build",
    "dist",
    "node_modules",
]

DEFAULT_TARGET_PYTHON_VERSIONS: list[str] = ["3.10", "3.11", "3.12", "3.13"]
DEFAULT_TARGET_OPERATING_SYSTEMS: list[OperatingSystem] = [
    OperatingSystem.LINUX,
    OperatingSystem.WINDOWS,
    OperatingSystem.MACOS,
]
DEFAULT_TARGET_ARCHITECTURES: list[Architecture] = [
    Architecture.X86_64,
    Architecture.AARCH64,
]
DEFAULT_TARGET_IMPLEMENTATIONS: list[PythonImplementation] = [
    PythonImplementation.CPYTHON,
]


class TargetEnvironment(BaseModel):
    """Specification of an execution environment.

    Decoupled from the host machine running PyDeps to support cross-platform analysis.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    python_version: str = Field(
        ...,
        description="Target Python version, e.g. '3.8', '3.11', or '3.12.1'",
    )
    operating_system: OperatingSystem = Field(
        ...,
        description="Target operating system",
    )
    architecture: Architecture = Field(
        ...,
        description="Target hardware architecture",
    )
    implementation: PythonImplementation = Field(
        default=PythonImplementation.CPYTHON,
        description="Target Python implementation (e.g. cpython or pypy)",
    )

    @field_validator("python_version")
    @classmethod
    def validate_python_version(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("python_version must not be empty")
        try:
            parsed = Version(trimmed)
            if parsed.major < 2 or parsed.major > 4:
                raise ValueError(f"Unsupported major Python version: {parsed.major}")
        except InvalidVersion as exc:
            raise ValueError(f"Invalid Python version string '{v}': {exc}") from exc
        return trimmed

    @property
    def platform_tag(self) -> str:
        """Return a simplified platform identifier for display and reporting."""
        return (
            f"{self.operating_system.value}-{self.architecture.value}-"
            f"{self.implementation.value}-py{self.python_version}"
        )


class ProjectConfig(BaseModel):
    """Configuration settings for PyDeps project analysis."""

    model_config = ConfigDict(extra="forbid")

    project_path: Path = Field(
        default_factory=lambda: Path("."),
        description="Root path of the project to analyze",
    )
    target_python_versions: list[str] = Field(
        default_factory=lambda: list(DEFAULT_TARGET_PYTHON_VERSIONS),
        description="Python versions to evaluate compatibility and resolution against",
    )
    target_operating_systems: list[OperatingSystem] = Field(
        default_factory=lambda: list(DEFAULT_TARGET_OPERATING_SYSTEMS),
        description="Operating systems to evaluate against",
    )
    target_architectures: list[Architecture] = Field(
        default_factory=lambda: list(DEFAULT_TARGET_ARCHITECTURES),
        description="Hardware architectures to evaluate against",
    )
    target_implementations: list[PythonImplementation] = Field(
        default_factory=lambda: list(DEFAULT_TARGET_IMPLEMENTATIONS),
        description="Python implementations to evaluate against",
    )
    validate_runtime: bool = Field(
        default=False,
        description="Whether to run isolated environment validation tests",
    )
    output_directory: Path = Field(
        default_factory=lambda: Path(".pydeps"),
        description="Directory for generated reports, lockfiles, and artifacts",
    )
    excluded_directories: list[str] = Field(
        default_factory=lambda: list(DEFAULT_EXCLUDED_DIRECTORIES),
        description="Directory names or patterns to ignore during scanning",
    )

    @field_validator("target_python_versions")
    @classmethod
    def validate_target_python_versions(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("target_python_versions must contain at least one version")
        validated: list[str] = []
        for ver in v:
            trimmed = ver.strip()
            if not trimmed:
                raise ValueError("Python version entry cannot be empty")
            try:
                Version(trimmed)
            except InvalidVersion as exc:
                raise ValueError(f"Invalid target Python version '{ver}': {exc}") from exc
            validated.append(trimmed)
        return validated

    @field_validator("target_operating_systems")
    @classmethod
    def validate_target_os(cls, v: list[OperatingSystem]) -> list[OperatingSystem]:
        if not v:
            raise ValueError("target_operating_systems must contain at least one operating system")
        return v

    @field_validator("target_architectures")
    @classmethod
    def validate_target_arch(cls, v: list[Architecture]) -> list[Architecture]:
        if not v:
            raise ValueError("target_architectures must contain at least one architecture")
        return v

    @field_validator("target_implementations")
    @classmethod
    def validate_target_impl(cls, v: list[PythonImplementation]) -> list[PythonImplementation]:
        if not v:
            raise ValueError("target_implementations must contain at least one implementation")
        return v

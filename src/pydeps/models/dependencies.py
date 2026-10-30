"""Dependency specification and resolution data models."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from packaging.markers import InvalidMarker, Marker
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DependencyType(str, Enum):
    """Classification of the dependency in relation to the project."""

    DIRECT = "direct"
    TRANSITIVE = "transitive"
    DEV = "dev"
    OPTIONAL = "optional"
    BUILD = "build"
    TYPE_CHECKING = "type_checking"
    NOTEBOOK = "notebook"


class Dependency(BaseModel):
    """Specification of a Python package dependency."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        description="Distribution package name (e.g., 'requests', 'pydantic')",
    )
    version_specifier: str | None = Field(
        default=None,
        description="PEP 440 version specifier string, e.g. '>=2.0.0, <3.0'",
    )
    extras: frozenset[str] = Field(
        default_factory=frozenset,
        description="Requested package extras (e.g., {'email', 'security'})",
    )
    environment_marker: str | None = Field(
        default=None,
        description="PEP 508 environment marker string, e.g. 'python_version >= \"3.10\"'",
    )
    dependency_type: DependencyType = Field(
        default=DependencyType.DIRECT,
        description="Classification of this dependency",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Dependency name must not be empty")
        return canonicalize_name(trimmed)

    @field_validator("version_specifier")
    @classmethod
    def validate_version_specifier(cls, v: str | None) -> str | None:
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            return None
        try:
            SpecifierSet(trimmed)
        except InvalidSpecifier as exc:
            raise ValueError(f"Invalid version specifier '{v}': {exc}") from exc
        return trimmed

    @field_validator("environment_marker")
    @classmethod
    def validate_environment_marker(cls, v: str | None) -> str | None:
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            return None
        try:
            Marker(trimmed)
        except InvalidMarker as exc:
            raise ValueError(f"Invalid environment marker '{v}': {exc}") from exc
        return trimmed

    @field_validator("extras", mode="before")
    @classmethod
    def coerce_extras(cls, v: object) -> frozenset[str]:
        if v is None:
            return frozenset()
        if isinstance(v, (list, set, tuple, frozenset)):
            return frozenset(str(x).strip() for x in v if str(x).strip())
        if isinstance(v, str):
            return frozenset(x.strip() for x in v.split(",") if x.strip())
        raise ValueError(f"Invalid extras format: {v}")

    def to_pep508(self) -> str:
        """Render dependency as a valid PEP 508 requirement string."""
        parts: list[str] = [self.name]
        if self.extras:
            sorted_extras = ",".join(sorted(self.extras))
            parts.append(f"[{sorted_extras}]")
        if self.version_specifier:
            parts.append(f" {self.version_specifier}")
        if self.environment_marker:
            parts.append(f"; {self.environment_marker}")
        return "".join(parts)


class ResolutionMode(str, Enum):
    """Execution mode of the dependency resolution engine."""

    UNIVERSAL = "universal"
    PER_TARGET = "per-target"


class ResolutionStrategy(str, Enum):
    """Version selection strategy governing resolution decisions."""

    LATEST_COMPATIBLE = "latest-compatible"
    FEWEST_VERSIONS = "fewest-versions"
    PRESERVE_EXISTING_LOCK = "preserve-existing-lock"
    PREFER_EXISTING_CONSTRAINTS = "prefer-existing-constraints"


class ResolutionStatus(str, Enum):
    """High-level outcome status of resolution."""

    SUCCESS = "success"
    CONFLICT = "conflict"
    FAILURE = "failure"
    UNRESOLVED = "unresolved"


class ResolutionTarget(BaseModel):
    """Specification of an explicit target environment for per-target resolution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    python_version: str = Field(..., description="Target Python version, e.g. '3.11'")
    operating_system: str = Field(..., description="Target OS (windows, linux, macos)")
    architecture: str = Field(..., description="Target CPU architecture (x86_64, arm64)")
    implementation: str = Field(default="cpython", description="Target Python implementation")
    abi: str | None = Field(default=None, description="Explicit ABI tag if specified")
    platform_tag: str = Field(..., description="Normalized unique platform identifier")


class ResolvedPackage(BaseModel):
    """Representation of an exact resolved package version in the dependency graph."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Canonicalized package distribution name")
    version: str = Field(..., description="Resolved exact version string (e.g. '2.31.0')")
    dependency_type: DependencyType = Field(
        default=DependencyType.DIRECT,
        description="Whether package was directly or transitively required",
    )
    extras: frozenset[str] = Field(
        default_factory=frozenset,
        description="Activated package extras",
    )
    environment_marker: str | None = Field(
        default=None,
        description="Environment marker under which package was resolved",
    )
    hashes: list[str] = Field(
        default_factory=list,
        description="Cryptographic artifact hashes (sha256) where available",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="List of direct child dependency package names",
    )
    required_by: list[str] = Field(
        default_factory=list,
        description="List of parent package names requesting this dependency",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Resolved package name must not be empty")
        return canonicalize_name(trimmed)


class ResolutionConflict(BaseModel):
    """Structured diagnostic representation of a dependency resolution conflict."""

    model_config = ConfigDict(extra="forbid")

    package_name: str = Field(..., description="Distribution experiencing the conflict")
    conflicting_requirements: list[str] = Field(
        ...,
        description="Mutually exclusive or contradictory requirement specifiers",
    )
    source_packages: list[str] = Field(
        default_factory=list,
        description="Packages that introduced the conflicting requirements",
    )
    target_environment: str | None = Field(
        default=None,
        description="Target platform tag where conflict occurred, if per-target",
    )
    resolver_backend: str = Field(
        default="uv",
        description="Resolver backend that detected the conflict (uv or pip)",
    )
    error_category: str = Field(
        default="version_conflict",
        description="Category: version_conflict, no_matching_release, marker_conflict, etc.",
    )
    original_diagnostics: str = Field(
        default="",
        description="Raw error output or diagnostics from resolver subprocess",
    )
    suggested_investigation: str = Field(
        default="",
        description="Actionable guidance on how to remediate the conflict",
    )


class ResolutionDiagnostic(BaseModel):
    """Diagnostic notice, warning, or limitation emitted during resolution."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., description="Diagnostic explanation")
    level: str = Field(default="warning", description="Severity: info, warning, error")
    package_name: str | None = Field(
        default=None,
        description="Related package name if applicable",
    )
    source: str = Field(default="resolver", description="Subsystem originating the diagnostic")


class ResolvedDependencyGraph(BaseModel):
    """Complete directed dependency graph of resolved direct and transitive packages."""

    model_config = ConfigDict(extra="forbid")

    packages: dict[str, ResolvedPackage] = Field(
        default_factory=dict,
        description="Mapping from canonical package name to ResolvedPackage",
    )
    roots: list[str] = Field(
        default_factory=list,
        description="Direct root dependency package names",
    )
    edges: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Adjacency list mapping package to dependent packages",
    )
    direct_count: int = Field(default=0, description="Total count of direct packages")
    transitive_count: int = Field(default=0, description="Total count of transitive packages")


class ResolutionRequest(BaseModel):
    """Configuration request for executing dependency resolution."""

    model_config = ConfigDict(extra="forbid")

    project_path: Path = Field(..., description="Path to the project root directory")
    direct_dependencies: list[Dependency] = Field(
        default_factory=list,
        description="Candidate direct dependencies to resolve",
    )
    constraints: list[Dependency] = Field(
        default_factory=list,
        description="Explicit pinned or bounded constraints to enforce",
    )
    mode: ResolutionMode = Field(
        default=ResolutionMode.UNIVERSAL,
        description="Resolution mode: universal or per-target",
    )
    strategy: ResolutionStrategy = Field(
        default=ResolutionStrategy.LATEST_COMPATIBLE,
        description="Resolution strategy",
    )
    backend: str = Field(default="uv", description="Resolver backend: 'uv' or 'pip'")
    targets: list[Any] = Field(
        default_factory=list,
        description="Configured target environments",
    )
    extras: list[str] = Field(default_factory=list, description="Project extras to resolve")
    include_dev: bool = Field(default=False, description="Whether to include dev dependencies")
    include_optional: bool = Field(
        default=False,
        description="Whether to include optional dependencies",
    )
    offline: bool = Field(default=False, description="Whether to resolve offline")
    allow_prereleases: bool = Field(
        default=False,
        description="Whether to permit pre-release versions",
    )
    output_dir: Path | None = Field(default=None, description="Output export directory")
    upgrade: bool = Field(default=False, description="Whether to upgrade existing locked packages")
    upgrade_packages: list[str] = Field(
        default_factory=list,
        description="Specific package names to upgrade",
    )


class ResolutionResult(BaseModel):
    """Result of resolving a set of dependencies for target environments."""

    model_config = ConfigDict(extra="forbid")

    success: bool = Field(
        ...,
        description="Whether all dependency constraints were successfully resolved",
    )
    resolved_dependencies: list[Dependency] = Field(
        default_factory=list,
        description="Fully resolved dependencies with exact pinned versions",
    )
    conflicts: list[str] = Field(
        default_factory=list,
        description="Descriptions of dependency version or marker conflicts encountered",
    )
    unresolved_dependencies: list[str] = Field(
        default_factory=list,
        description="Dependencies that could not be resolved or satisfied",
    )
    mode: ResolutionMode = Field(
        default=ResolutionMode.UNIVERSAL,
        description="Resolution mode executed",
    )
    strategy: ResolutionStrategy = Field(
        default=ResolutionStrategy.LATEST_COMPATIBLE,
        description="Resolution strategy employed",
    )
    backend: str = Field(default="uv", description="Backend used: uv or pip")
    status: ResolutionStatus = Field(
        default=ResolutionStatus.SUCCESS,
        description="Outcome status of resolution",
    )
    graph: ResolvedDependencyGraph | None = Field(
        default=None,
        description="Complete resolved dependency graph with direct and transitive nodes",
    )
    structured_conflicts: list[ResolutionConflict] = Field(
        default_factory=list,
        description="Structured conflict objects with root-cause diagnostics",
    )
    per_target_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-target resolution results mapped by platform tag",
    )
    target: ResolutionTarget | None = Field(
        default=None,
        description="Specific target environment if this result is for a single target",
    )
    diagnostics: list[ResolutionDiagnostic] = Field(
        default_factory=list,
        description="Notices, warnings, or limitations emitted during resolution",
    )
    lockfile_content: str | None = Field(
        default=None,
        description="Raw content of generated uv.lock if applicable",
    )
    requirements_txt: str | None = Field(
        default=None,
        description="Resolved pinned requirements.txt output",
    )
    output_files: list[str] = Field(
        default_factory=list,
        description="Paths of exported output files written to disk",
    )

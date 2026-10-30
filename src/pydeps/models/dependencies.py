"""Dependency specification and resolution data models."""

from __future__ import annotations

from enum import Enum

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

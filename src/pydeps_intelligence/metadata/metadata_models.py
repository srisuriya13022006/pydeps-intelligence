"""PyPI package release metadata models."""

from __future__ import annotations

from datetime import datetime, timezone

from packaging.utils import canonicalize_name
from pydantic import BaseModel, ConfigDict, Field, field_validator

from pydeps_intelligence.models.dependencies import Dependency


class ReleaseArtifact(BaseModel):
    """Metadata describing a downloadable release file (wheel, sdist) from PyPI."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    filename: str = Field(
        ...,
        description="Artifact archive filename (e.g. 'requests-2.31.0-py3-none-any.whl')",
    )
    package_type: str = Field(
        ...,
        description="Type of distribution package ('bdist_wheel', 'sdist')",
    )
    python_version: str | None = Field(
        default=None,
        description="Python version tag (e.g. 'py3', 'source')",
    )
    platform_tags: list[str] = Field(
        default_factory=list,
        description="Parsed wheel platform tags (e.g. ['manylinux_2_17_x86_64', 'any'])",
    )
    requires_python: str | None = Field(
        default=None,
        description="Per-artifact Requires-Python constraint",
    )
    sha256: str | None = Field(
        default=None,
        description="SHA256 checksum digest of the artifact",
    )
    yanked: bool = Field(
        default=False,
        description="Whether this specific artifact file has been yanked",
    )
    size: int | None = Field(
        default=None,
        description="File size in bytes",
    )
    upload_time: str | None = Field(
        default=None,
        description="ISO 8601 upload timestamp",
    )


class PackageRelease(BaseModel):
    """Structured release metadata for a specific distribution package version on PyPI."""

    model_config = ConfigDict(extra="forbid")

    distribution_name: str = Field(
        ...,
        description="Normalized distribution package name (PEP 503)",
    )
    version: str = Field(
        ...,
        description="Release version string (PEP 440)",
    )
    requires_python: str | None = Field(
        default=None,
        description="Requires-Python specification string (e.g. '>=3.8')",
    )
    requires_dist: list[Dependency] = Field(
        default_factory=list,
        description="Declared distribution dependencies (parsed from Requires-Dist)",
    )
    provides_extra: list[str] = Field(
        default_factory=list,
        description="Available optional dependency extras",
    )
    release_files: list[ReleaseArtifact] = Field(
        default_factory=list,
        description="Available build artifacts and distributions for this version",
    )
    yanked: bool = Field(
        default=False,
        description="Whether this release version has been yanked on PyPI",
    )
    yanked_reason: str | None = Field(
        default=None,
        description="Explanation provided by maintainer if yanked",
    )
    metadata_source: str = Field(
        default="pypi_json_api",
        description="Origin of metadata ('pypi_json_api', 'cache', etc.)",
    )
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when metadata was retrieved",
    )
    summary: str | None = Field(
        default=None,
        description="Short description of the release from PyPI",
    )
    project_urls: dict[str, str] = Field(
        default_factory=dict,
        description="Official URLs associated with the project",
    )

    @field_validator("distribution_name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("distribution_name must not be empty")
        return canonicalize_name(trimmed)


class MetadataResult(BaseModel):
    """Result of attempting to retrieve distribution metadata from PyPI or cache."""

    model_config = ConfigDict(extra="forbid")

    success: bool = Field(
        ...,
        description="Whether metadata was successfully obtained and parsed",
    )
    package_name: str = Field(
        ...,
        description="Target package name requested",
    )
    version: str | None = Field(
        default=None,
        description="Specific version requested or resolved latest version",
    )
    metadata: PackageRelease | None = Field(
        default=None,
        description="Extracted release metadata if successfully retrieved",
    )
    source: str = Field(
        default="pypi",
        description="Source of the result ('network', 'cache', 'offline_fallback')",
    )
    diagnostics: list[str] = Field(
        default_factory=list,
        description="Informational diagnostics, HTTP status notices, or failure reasons",
    )

    @field_validator("package_name")
    @classmethod
    def normalize_package_name(cls, v: str) -> str:
        return canonicalize_name(v.strip())

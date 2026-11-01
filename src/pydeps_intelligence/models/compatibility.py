"""Compatibility evaluation data models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from packaging.utils import canonicalize_name
from pydantic import BaseModel, ConfigDict, Field, field_validator

from pydeps_intelligence.models.project import TargetEnvironment


class CompatibilityStatus(str, Enum):
    """Tri-state compatibility status as mandated by architecture ADR-005."""

    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNVERIFIED = "unverified"


class MarkerEvaluation(BaseModel):
    """Evaluation outcome of a single PEP 508 dependency environment marker."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requirement: str = Field(
        ...,
        description="Original requirement string (e.g. 'requests>=2.0; os_name == \"nt\"')",
    )
    dependency_name: str = Field(
        ...,
        description="Target dependency package name",
    )
    marker_expression: str | None = Field(
        default=None,
        description="Extracted environment marker expression",
    )
    target_environment: str = Field(
        ...,
        description="Target platform descriptor against which marker was evaluated",
    )
    applies: bool | None = Field(
        default=None,
        description="True if dependency applies to target, False if excluded, None if unverified",
    )
    status: CompatibilityStatus = Field(
        default=CompatibilityStatus.COMPATIBLE,
        description="Evaluation status (COMPATIBLE or UNVERIFIED if profile info missing)",
    )
    explanation: str = Field(
        ...,
        description="Detailed explanation of marker evaluation outcome",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Target environment profile fields referenced by marker but missing",
    )


class ArtifactCompatibility(BaseModel):
    """Assessment of downloadable artifacts (wheels, sdist) for a release."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    has_compatible_wheel: bool = Field(
        default=False,
        description="Whether at least one compatible binary wheel artifact exists for target",
    )
    compatible_wheels: list[str] = Field(
        default_factory=list,
        description="Filenames of compatible wheel artifacts",
    )
    incompatible_wheels: list[str] = Field(
        default_factory=list,
        description="Filenames of incompatible wheel artifacts",
    )
    has_sdist: bool = Field(
        default=False,
        description="Whether a source distribution is available for this release",
    )
    sdist_filename: str | None = Field(
        default=None,
        description="Filename of available source distribution, if present",
    )
    status: CompatibilityStatus = Field(
        default=CompatibilityStatus.UNVERIFIED,
        description="Artifact compatibility determination",
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="Explanations supporting the artifact compatibility status",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings regarding yanked artifacts or incomplete metadata",
    )


class CompatibilityResult(BaseModel):
    """Outcome of compatibility evaluation of a package against a target environment."""

    model_config = ConfigDict(extra="forbid")

    package_name: str = Field(
        ...,
        description="Name of the package evaluated",
    )
    package_version: str | None = Field(
        default=None,
        description="Specific package version evaluated, if pinned",
    )
    target_environment: TargetEnvironment = Field(
        ...,
        description="The target platform environment",
    )
    status: CompatibilityStatus = Field(
        ...,
        description="Compatibility status (compatible, incompatible, or unverified)",
    )
    reason: str | None = Field(
        default=None,
        description="Detailed explanation of the compatibility determination",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Auditable evidence points (wheel tags, python_requires, metadata fields)",
    )
    python_constraint_compatible: bool | None = Field(
        default=None,
        description="Whether the release satisfies target Python version constraints",
    )
    evaluated_python_constraints: str | None = Field(
        default=None,
        description="Evaluated Requires-Python constraint string from metadata",
    )
    wheel_candidates: list[str] = Field(
        default_factory=list,
        description="List of compatible wheel filenames available for target",
    )
    incompatible_wheels: list[str] = Field(
        default_factory=list,
        description="List of incompatible wheel filenames available for target",
    )
    has_source_distribution: bool = Field(
        default=False,
        description="Whether an sdist archive exists for this release",
    )
    sdist_name: str | None = Field(
        default=None,
        description="Name of the sdist artifact if present",
    )
    marker_evaluations: list[MarkerEvaluation] = Field(
        default_factory=list,
        description="Evaluations of declared dependency markers against target environment",
    )
    evidence_source: str = Field(
        default="pypi_metadata",
        description="Origin of evidence used for evaluation",
    )
    unverified_conditions: list[str] = Field(
        default_factory=list,
        description="Conditions or missing evidence preventing definitive determination",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Diagnostic warnings (e.g. yanked status, missing requires_python)",
    )

    @field_validator("package_name")
    @classmethod
    def normalize_package_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("package_name must not be empty")
        return canonicalize_name(trimmed)


# PackageCompatibility is synonymous with CompatibilityResult
PackageCompatibility = CompatibilityResult


class PackageCompatibilityMatrix(BaseModel):
    """Compatibility results for a single package release evaluated across multiple targets."""

    model_config = ConfigDict(extra="forbid")

    package_name: str = Field(
        ...,
        description="Distribution package name",
    )
    version: str = Field(
        ...,
        description="Release version string",
    )
    results: dict[str, CompatibilityResult] = Field(
        default_factory=dict,
        description="Mapping from target environment platform tag to evaluation result",
    )
    summary: dict[str, int] = Field(
        default_factory=dict,
        description="Count of compatible, incompatible, and unverified target environments",
    )


class CompatibilityMatrix(BaseModel):
    """Overall compatibility matrix evaluating packages across target environments."""

    model_config = ConfigDict(extra="forbid")

    packages: list[str] = Field(
        default_factory=list,
        description="List of evaluated package distribution names",
    )
    targets: list[TargetEnvironment] = Field(
        default_factory=list,
        description="List of configured target environments",
    )
    entries: list[CompatibilityResult] = Field(
        default_factory=list,
        description="Flat list of all individual compatibility evaluations",
    )
    matrix: dict[str, dict[str, CompatibilityResult]] = Field(
        default_factory=dict,
        description="Nested mapping: package_name -> target_platform_tag -> CompatibilityResult",
    )
    diagnostics: list[str] = Field(
        default_factory=list,
        description="General diagnostic messages, warnings, or unsupported configuration notices",
    )
    summary_counts: dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregate statistics of matrix evaluations",
    )

    def get_result(
        self, package_name: str, target: TargetEnvironment | str
    ) -> CompatibilityResult | None:
        """Retrieve result for a given package and target environment."""
        pkg = canonicalize_name(package_name)
        tag = target.platform_tag if isinstance(target, TargetEnvironment) else target
        return self.matrix.get(pkg, {}).get(tag)

    def summary(self) -> dict[str, Any]:
        """Compute and return summary statistics of the compatibility matrix."""
        total_evaluations = len(self.entries)
        compatible_count = sum(
            1 for e in self.entries if e.status == CompatibilityStatus.COMPATIBLE
        )
        incompatible_count = sum(
            1 for e in self.entries if e.status == CompatibilityStatus.INCOMPATIBLE
        )
        unverified_count = sum(
            1 for e in self.entries if e.status == CompatibilityStatus.UNVERIFIED
        )

        return {
            "total_packages": len(self.packages),
            "total_targets": len(self.targets),
            "total_evaluations": total_evaluations,
            "compatible_count": compatible_count,
            "incompatible_count": incompatible_count,
            "unverified_count": unverified_count,
            "diagnostics_count": len(self.diagnostics),
        }

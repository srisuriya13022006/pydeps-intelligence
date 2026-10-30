"""Compatibility evaluation data models."""

from __future__ import annotations

from enum import Enum

from packaging.utils import canonicalize_name
from pydantic import BaseModel, ConfigDict, Field, field_validator

from pydeps.models.project import TargetEnvironment


class CompatibilityStatus(str, Enum):
    """Tri-state compatibility status as mandated by architecture ADR-005."""

    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNVERIFIED = "unverified"


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

    @field_validator("package_name")
    @classmethod
    def normalize_package_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("package_name must not be empty")
        return canonicalize_name(trimmed)

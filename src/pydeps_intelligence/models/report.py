"""Analysis report aggregate model."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pydeps_intelligence.models.compatibility import CompatibilityResult
from pydeps_intelligence.models.dependencies import ResolutionResult
from pydeps_intelligence.models.imports import ImportRecord, PackageMapping
from pydeps_intelligence.models.validation import ValidationResult


class ProjectInformation(BaseModel):
    """Metadata describing the target project analyzed by PyDeps."""

    model_config = ConfigDict(extra="allow")

    project_name: str | None = Field(
        default=None,
        description="Name of the project, if identified from metadata or directory name",
    )
    project_path: Path = Field(
        ...,
        description="Root directory of the analyzed project",
    )
    analysis_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when analysis was conducted",
    )
    pydeps_version: str = Field(
        default="0.1.0",
        description="PyDeps engine version producing the report",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional project details (e.g. build backend, pyproject.toml status)",
    )


class AnalysisReport(BaseModel):
    """Comprehensive dependency intelligence report produced by PyDeps."""

    model_config = ConfigDict(extra="forbid")

    project_information: ProjectInformation = Field(
        ...,
        description="Project metadata and analysis context",
    )
    discovered_imports: list[ImportRecord] = Field(
        default_factory=list,
        description="All import statements discovered across project source files",
    )
    mapped_dependencies: list[PackageMapping] = Field(
        default_factory=list,
        description="Mapping from discovered imports to canonical distribution packages",
    )
    compatibility_results: list[CompatibilityResult] = Field(
        default_factory=list,
        description="Compatibility determinations across target environments",
    )
    resolution_results: ResolutionResult | None = Field(
        default=None,
        description="Dependency resolution outcome, if resolution was performed",
    )
    validation_results: list[ValidationResult] = Field(
        default_factory=list,
        description="Isolated runtime environment validation results",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Diagnostic warnings and caveats recorded during analysis",
    )

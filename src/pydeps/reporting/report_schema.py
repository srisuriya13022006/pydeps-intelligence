"""Versioned diagnostic report schema models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pydeps._version import __version__
from pydeps.models.project import TargetEnvironment


class StageStatus(str, Enum):
    """Discrete status outcomes for diagnostic pipeline stages."""

    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    SKIPPED = "skipped"
    UNSUPPORTED = "unsupported"
    BLOCKED_BY_POLICY = "blocked_by_policy"


class DependencyHealthStatus(str, Enum):
    """Evaluated health status of project dependencies based on collected evidence."""

    HEALTHY = "healthy"
    PARTIAL = "partial"
    PROBLEMATIC = "problematic"
    UNKNOWN = "unknown"


class RecommendationSeverity(str, Enum):
    """Severity classification for actionable diagnostic findings."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RecommendationItem(BaseModel):
    """Evidence-backed developer guidance or recommendation."""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(
        ..., description="Category: missing_dependency, compatibility, conflict, security, etc."
    )
    severity: RecommendationSeverity = Field(..., description="Severity level")
    title: str = Field(..., description="Short summary of the recommendation")
    description: str = Field(
        ..., description="Detailed explanation of the issue and why it matters"
    )
    evidence: list[str] = Field(
        default_factory=list, description="Concrete evidence backing this recommendation"
    )
    actionable_remedy: str | None = Field(
        default=None, description="Recommended resolution or command"
    )


class StageResultSummary(BaseModel):
    """Execution outcome and telemetry for an individual pipeline stage."""

    model_config = ConfigDict(extra="allow")

    stage_name: str = Field(..., description="Name of the pipeline stage")
    status: StageStatus = Field(..., description="Stage completion status")
    duration_seconds: float = Field(default=0.0, description="Duration in seconds")
    diagnostics: list[str] = Field(
        default_factory=list, description="Diagnostics, warnings, or errors"
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Stage-specific telemetry metadata"
    )


class ProjectInfo(BaseModel):
    """Metadata describing the analyzed target project."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(default="", description="Identified or fallback project name")
    path: str = Field(..., description="Absolute or relative path to project root")
    analysis_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the diagnosis run",
    )
    python_version_detected: str | None = Field(
        default=None, description="Python version inferred from project files"
    )
    file_count: int = Field(default=0, description="Total scanned Python source files")
    test_file_count: int = Field(default=0, description="Total identified test files")
    lines_of_code: int = Field(default=0, description="Total estimated lines of Python code")


class ExecutionEnvironmentInfo(BaseModel):
    """Host execution environment details."""

    model_config = ConfigDict(extra="forbid")

    operating_system: str = Field(..., description="Host operating system name")
    architecture: str = Field(..., description="Host CPU architecture")
    python_version: str = Field(..., description="Python interpreter version running PyDeps")
    python_implementation: str = Field(
        default="CPython", description="Python implementation (CPython/PyPy)"
    )
    offline_mode: bool = Field(
        default=False, description="Whether analysis was run in offline mode"
    )


class SourceAnalysisSection(BaseModel):
    """Findings from static file scanning and AST import analysis."""

    model_config = ConfigDict(extra="allow")

    scanned_files: list[str] = Field(default_factory=list, description="List of scanned files")
    total_files: int = Field(default=0, description="Number of files scanned")
    total_imports: int = Field(default=0, description="Total import statements parsed")
    standard_library: list[str] = Field(
        default_factory=list, description="Discovered standard-library modules"
    )
    local_imports: list[str] = Field(
        default_factory=list, description="Discovered local project modules"
    )
    external_candidates: list[str] = Field(
        default_factory=list, description="Discovered third-party candidates"
    )
    dynamic_imports: list[dict[str, Any]] = Field(
        default_factory=list, description="Dynamic import statements"
    )
    syntax_errors: list[str] = Field(default_factory=list, description="Files with syntax errors")


class PackageIntelligenceSection(BaseModel):
    """Findings from import-to-distribution mapping and metadata retrieval."""

    model_config = ConfigDict(extra="allow")

    mappings: dict[str, str] = Field(
        default_factory=dict, description="Resolved import-to-distribution mapping"
    )
    confidence_levels: dict[str, str] = Field(
        default_factory=dict, description="Confidence per mapped package"
    )
    ambiguous_mappings: dict[str, list[str]] = Field(
        default_factory=dict, description="Imports with multiple candidate packages"
    )
    unresolved_candidates: list[str] = Field(
        default_factory=list, description="External candidates that could not be mapped"
    )
    overrides_applied: dict[str, Any] = Field(
        default_factory=dict, description="User configuration overrides applied"
    )
    metadata_summary: dict[str, Any] = Field(
        default_factory=dict, description="Summary of retrieved package metadata"
    )


class CompatibilitySection(BaseModel):
    """Cross-platform compatibility evaluation results."""

    model_config = ConfigDict(extra="allow")

    evaluated_targets: list[dict[str, Any]] = Field(
        default_factory=list, description="Target environment specifications"
    )
    evaluated_packages: list[str] = Field(
        default_factory=list, description="List of packages evaluated"
    )
    compatible_count: int = Field(
        default=0, description="Number of compatible package-target combinations"
    )
    incompatible_count: int = Field(
        default=0, description="Number of incompatible package-target combinations"
    )
    unverified_count: int = Field(
        default=0, description="Number of unverified package-target combinations"
    )
    matrix: dict[str, dict[str, dict[str, Any]]] = Field(
        default_factory=dict,
        description="Target ID -> Package Name -> {status, reason, wheel_tags, details}",
    )


class ResolutionSection(BaseModel):
    """Dependency resolution outcome and graph structure."""

    model_config = ConfigDict(extra="allow")

    success: bool = Field(default=False, description="Whether dependency resolution succeeded")
    mode: str = Field(default="universal", description="Resolution mode (universal/per_target)")
    strategy: str = Field(default="latest-compatible", description="Resolution strategy")
    backend: str = Field(default="uv", description="Resolution backend used (uv/pip)")
    direct_packages: list[str] = Field(
        default_factory=list, description="Direct project dependencies"
    )
    transitive_packages: list[str] = Field(
        default_factory=list, description="Transitive resolved dependencies"
    )
    pinned_versions: dict[str, str] = Field(
        default_factory=dict, description="Package -> Pinned version string"
    )
    conflicts: list[dict[str, Any]] = Field(
        default_factory=list, description="Detected version conflicts"
    )
    dependency_graph: dict[str, list[str]] = Field(
        default_factory=dict, description="Adjacency list: package -> direct dependencies"
    )


class ValidationSection(BaseModel):
    """Isolated runtime validation execution findings."""

    model_config = ConfigDict(extra="allow")

    executed: bool = Field(
        default=False, description="Whether runtime validation was authorized and executed"
    )
    status: StageStatus = Field(
        default=StageStatus.SKIPPED, description="Overall validation status"
    )
    runner_type: str | None = Field(default=None, description="Runner type: local, docker, remote")
    isolation_level: str | None = Field(default=None, description="Isolation level achieved")
    execution_policy: str | None = Field(default=None, description="Execution policy applied")
    stages: dict[str, Any] = Field(
        default_factory=dict, description="L1, L2, L3 individual stage results"
    )
    installed_packages: dict[str, str] = Field(
        default_factory=dict, description="Actual packages installed in venv"
    )
    import_results: list[dict[str, Any]] = Field(
        default_factory=list, description="Import smoke test outcomes"
    )
    project_test_results: dict[str, Any] | None = Field(
        default=None, description="Project test execution outcomes"
    )
    diagnostics: list[str] = Field(
        default_factory=list, description="Validation-specific diagnostics"
    )


class ProvenanceInfo(BaseModel):
    """Origin, versioning, and execution provenance."""

    model_config = ConfigDict(extra="allow")

    cli_command: str | None = Field(default=None, description="CLI command invoked")
    pydeps_version: str = Field(default=__version__, description="PyDeps tool version")
    schema_version: str = Field(default="1.0.0", description="Diagnostic report schema version")
    config_hash: str | None = Field(default=None, description="Hash of the effective configuration")
    git_commit: str | None = Field(default=None, description="Project Git commit if available")


class DiagnosticReport(BaseModel):
    """Unified, versioned PyDeps diagnostic report."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = Field(..., description="Diagnostic report schema specification version")
    tool_version: str = Field(..., description="PyDeps version that produced this report")
    pipeline_status: StageStatus = Field(
        default=StageStatus.PASSED,
        description="Execution status of the diagnostic pipeline workflow",
    )
    dependency_health_status: DependencyHealthStatus = Field(
        default=DependencyHealthStatus.HEALTHY,
        description="Evidence-backed health status of project dependencies",
    )
    runtime_validation_status: StageStatus = Field(
        default=StageStatus.SKIPPED,
        description="Outcome of runtime environment validation",
    )
    overall_status: StageStatus = Field(
        ...,
        description="Overall diagnosis status (for backward compatibility)",
    )
    project_information: ProjectInfo = Field(
        ..., description="Project metadata and analysis context"
    )
    execution_environment: ExecutionEnvironmentInfo = Field(
        ..., description="Execution host context"
    )
    target_environments: list[TargetEnvironment] = Field(
        default_factory=list, description="Target environments evaluated"
    )
    stage_results: dict[str, StageResultSummary] = Field(
        default_factory=dict, description="Per-stage status and telemetry"
    )
    source_analysis: SourceAnalysisSection = Field(
        default_factory=SourceAnalysisSection, description="Source analysis results"
    )
    package_intelligence: PackageIntelligenceSection = Field(
        default_factory=PackageIntelligenceSection,
        description="Package mapping and metadata results",
    )
    compatibility: CompatibilitySection = Field(
        default_factory=CompatibilitySection, description="Platform compatibility results"
    )
    resolution: ResolutionSection = Field(
        default_factory=ResolutionSection, description="Dependency resolution results"
    )
    validation: ValidationSection = Field(
        default_factory=ValidationSection, description="Runtime validation results"
    )
    recommendations: list[RecommendationItem] = Field(
        default_factory=list, description="Evidence-backed developer guidance"
    )
    diagnostics: list[str] = Field(
        default_factory=list, description="Aggregated pipeline warnings and diagnostics"
    )
    provenance: ProvenanceInfo = Field(
        default_factory=ProvenanceInfo, description="Execution provenance and metadata"
    )

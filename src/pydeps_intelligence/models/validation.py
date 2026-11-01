"""Isolated environment runtime validation models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pydeps_intelligence.models.project import (
    Architecture,
    OperatingSystem,
    PythonImplementation,
    TargetEnvironment,
)


class ExecutionPolicy(str, Enum):
    """Authorization and trust policy for executing code in validation environments."""

    STATIC_ONLY = "static_only"
    TRUSTED_LOCAL = "trusted_local"
    ISOLATED_CONTAINER = "isolated_container"
    REMOTE_RUNNER = "remote_runner"


class NetworkPolicy(str, Enum):
    """Network egress policy during runtime validation."""

    DISABLED = "disabled"
    PACKAGE_DOWNLOAD_ONLY = "package_download_only"
    CONTROLLED = "controlled"
    UNRESTRICTED = "unrestricted"


class ValidationStage(str, Enum):
    """Discrete runtime validation levels."""

    INSTALLATION = "installation"
    IMPORT_TEST = "import_test"
    PROJECT_TEST = "project_test"


class ValidationStatus(str, Enum):
    """Execution status for isolated validation stages."""

    SUCCESS = "success"
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    UNSUPPORTED = "unsupported"
    UNVERIFIED = "unverified"
    TIMED_OUT = "timed_out"
    BLOCKED_BY_POLICY = "blocked_by_policy"
    PENDING = "pending"


class RunnerCapabilities(BaseModel):
    """Capabilities and constraints supported by an execution runner."""

    model_config = ConfigDict(extra="forbid")

    runner_type: str = Field(..., description="Unique runner identifier (local, docker, remote)")
    supported_operating_systems: list[OperatingSystem] = Field(
        default_factory=list,
        description="Operating systems natively executable by this runner",
    )
    supported_architectures: list[Architecture] = Field(
        default_factory=list,
        description="CPU architectures executable by this runner",
    )
    supported_python_versions: list[str] = Field(
        default_factory=list,
        description="Python versions currently discovered or available",
    )
    supported_implementations: list[PythonImplementation] = Field(
        default_factory=lambda: [PythonImplementation.CPYTHON],
        description="Python interpreter implementations supported",
    )
    isolation_level: str = Field(
        default="none",
        description="Isolation mechanism provided (e.g., host_venv, container, remote_vm)",
    )
    supported_network_policies: list[NetworkPolicy] = Field(
        default_factory=lambda: [NetworkPolicy.DISABLED],
        description="Network policies enforceable by this runner",
    )
    is_available: bool = Field(
        default=True,
        description="Whether this runner backend is operational on the current system",
    )
    unavailable_reason: str | None = Field(
        default=None,
        description="Explanation if the runner is unavailable (e.g. docker daemon not running)",
    )


class EnvironmentInfo(BaseModel):
    """Metadata regarding a created disposable validation environment."""

    model_config = ConfigDict(extra="forbid")

    environment_path: Path = Field(..., description="Filesystem root of the isolated environment")
    python_executable: Path = Field(
        ..., description="Path to the python interpreter within the environment"
    )
    python_version: str = Field(..., description="Exact Python version string")
    operating_system: OperatingSystem = Field(
        ..., description="Operating system of the environment"
    )
    architecture: Architecture = Field(..., description="CPU architecture of the environment")
    implementation: PythonImplementation = Field(
        default=PythonImplementation.CPYTHON,
        description="Python implementation (CPython, PyPy)",
    )
    is_disposable: bool = Field(
        default=True,
        description="Whether the environment will be purged upon completion",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when environment was initialized",
    )
    is_cleaned_up: bool = Field(
        default=False,
        description="Whether the environment files have been purged",
    )


class ImportTestResult(BaseModel):
    """Result of attempting to import a single package or module in the environment."""

    model_config = ConfigDict(extra="forbid")

    module_name: str = Field(..., description="Top-level imported module name tested")
    distribution_name: str | None = Field(
        default=None,
        description="Canonical PyPI distribution providing this module",
    )
    status: ValidationStatus = Field(..., description="Outcome of the smoke import test")
    exit_code: int | None = Field(default=None, description="Subprocess return code")
    duration_seconds: float = Field(default=0.0, description="Execution duration in seconds")
    error_traceback: str | None = Field(
        default=None,
        description="Captured traceback if import raised an unhandled exception",
    )
    stdout: str | None = Field(default=None, description="Standard output from import execution")
    stderr: str | None = Field(default=None, description="Standard error from import execution")
    diagnostic: str | None = Field(
        default=None,
        description="Normalized explanation (e.g. module_not_found, import_error)",
    )


class ProjectTestResult(BaseModel):
    """Result of running an authorized project test suite."""

    model_config = ConfigDict(extra="forbid")

    command: list[str] = Field(..., description="Exact test command executed")
    status: ValidationStatus = Field(..., description="Overall test run status")
    exit_code: int | None = Field(default=None, description="Test runner return code")
    duration_seconds: float = Field(default=0.0, description="Test suite run duration in seconds")
    stdout: str | None = Field(default=None, description="Standard output from test runner")
    stderr: str | None = Field(default=None, description="Standard error from test runner")
    error_message: str | None = Field(
        default=None, description="Failure diagnostic or error summary"
    )


class ValidationStageResult(BaseModel):
    """Outcome and captured evidence for a specific validation stage."""

    model_config = ConfigDict(extra="forbid")

    stage: ValidationStage = Field(..., description="Validation stage identifier")
    status: ValidationStatus = Field(..., description="Stage completion status")
    duration_seconds: float = Field(default=0.0, description="Stage execution time in seconds")
    installed_packages: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of installed distribution names to installed versions",
    )
    import_results: list[ImportTestResult] = Field(
        default_factory=list,
        description="Detailed findings from L2 smoke import tests",
    )
    test_result: ProjectTestResult | None = Field(
        default=None,
        description="Findings from L3 project test suite execution",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Diagnostic messages or failures captured during this stage",
    )
    logs: str = Field(default="", description="Sanitized stdout/stderr logs from stage execution")


class ValidationRequest(BaseModel):
    """Specification of a runtime validation run."""

    model_config = ConfigDict(extra="forbid")

    project_path: Path = Field(..., description="Path to the project root directory")
    target_environment: TargetEnvironment = Field(..., description="Requested target environment")
    runner_type: str = Field(
        default="local", description="Requested runner backend ('local', 'docker', 'remote')"
    )
    level: str = Field(
        default="install", description="Validation level: 'install', 'imports', or 'project-tests'"
    )
    execution_policy: ExecutionPolicy = Field(
        default=ExecutionPolicy.STATIC_ONLY,
        description="Execution trust policy",
    )
    network_policy: NetworkPolicy = Field(
        default=NetworkPolicy.DISABLED,
        description="Network egress policy during validation",
    )
    allow_local_execution: bool = Field(
        default=False,
        description="Explicit user authorization to run code locally on host",
    )
    allow_project_code: bool = Field(
        default=False,
        description="Explicit user authorization to run project code (tests)",
    )
    project_test_command: list[str] = Field(
        default_factory=lambda: ["pytest"],
        description="Command array to run for L3 project test execution",
    )
    timeout_seconds: int = Field(
        default=300, ge=1, description="Maximum execution timeout in seconds"
    )
    memory_limit: str | None = Field(
        default=None,
        description="Container memory limit (e.g. '1g', '512m')",
    )
    cpu_limit: str | None = Field(
        default=None,
        description="Container CPU quota (e.g. '1.0', '0.5')",
    )
    dry_run: bool = Field(
        default=False, description="Whether to simulate validation plan without execution"
    )
    keep_environment: bool = Field(
        default=False,
        description="Preserve the created disposable environment for post-mortem debugging",
    )
    output_directory: Path | None = Field(
        default=None,
        description="Directory where validation logs and reports should be stored",
    )


class ValidationReport(BaseModel):
    """Comprehensive report summarizing runtime environment validation."""

    model_config = ConfigDict(extra="forbid")

    project_name: str | None = Field(default=None, description="Project name")
    project_path: Path = Field(..., description="Analyzed project root directory")
    status: ValidationStatus = Field(..., description="Overall validation status")
    target_environment: TargetEnvironment = Field(..., description="Evaluated target environment")
    runner_type: str = Field(..., description="Runner backend used")
    isolation_level: str = Field(..., description="Isolation level achieved")
    execution_policy: ExecutionPolicy = Field(..., description="Active execution trust policy")
    network_policy: NetworkPolicy = Field(..., description="Active network policy")
    python_interpreter_version: str | None = Field(
        default=None,
        description="Version of Python interpreter used inside the environment",
    )
    installed_packages: dict[str, str] = Field(
        default_factory=dict,
        description="All packages and exact versions verified in the environment",
    )
    stages: dict[str, ValidationStageResult] = Field(
        default_factory=dict,
        description="Per-stage validation outcomes",
    )
    stage_statuses: dict[str, ValidationStatus] = Field(
        default_factory=dict,
        description="Summary status mapping for each stage",
    )
    diagnostics: list[str] = Field(
        default_factory=list,
        description="Diagnostic messages, caveats, or policy warnings",
    )
    resource_limits: dict[str, Any] = Field(
        default_factory=dict,
        description="Resource limit constraints applied during execution",
    )
    environment_info: EnvironmentInfo | None = Field(
        default=None,
        description="Details of the created environment",
    )
    cleanup_status: str = Field(
        default="cleaned",
        description="Cleanup outcome: 'cleaned', 'preserved', or 'failed'",
    )
    output_files: list[Path] = Field(
        default_factory=list,
        description="Artifacts generated by validation run",
    )
    dry_run_plan: dict[str, Any] | None = Field(
        default=None,
        description="Dry-run execution plan if dry_run=True was requested",
    )


class ValidationResult(BaseModel):
    """Results from executing validation checks in an isolated environment.

    Retained for backward compatibility with existing tests and facades.
    """

    model_config = ConfigDict(extra="forbid")

    target_environment: TargetEnvironment = Field(
        ...,
        description="Environment in which validation was performed",
    )
    installation_status: ValidationStatus = Field(
        default=ValidationStatus.PENDING,
        description="Status of package installation into the isolated environment",
    )
    import_test_status: ValidationStatus = Field(
        default=ValidationStatus.PENDING,
        description="Status of smoke import tests for resolved packages",
    )
    test_status: ValidationStatus = Field(
        default=ValidationStatus.PENDING,
        description="Status of project test suite execution in the environment",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Diagnostic messages or tracebacks captured during validation",
    )

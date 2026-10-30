"""Isolated environment runtime validation models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from pydeps.models.project import TargetEnvironment


class ValidationStatus(str, Enum):
    """Execution status for isolated validation stages."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"


class ValidationResult(BaseModel):
    """Results from executing validation checks in an isolated environment."""

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

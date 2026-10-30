"""Domain data models for PyDeps."""

from pydeps.models.compatibility import CompatibilityResult, CompatibilityStatus
from pydeps.models.dependencies import Dependency, DependencyType, ResolutionResult
from pydeps.models.imports import ImportRecord, ImportType, MappingSource, PackageMapping
from pydeps.models.project import (
    Architecture,
    OperatingSystem,
    ProjectConfig,
    PythonImplementation,
    TargetEnvironment,
)
from pydeps.models.report import AnalysisReport, ProjectInformation
from pydeps.models.validation import ValidationResult, ValidationStatus

__all__ = [
    "AnalysisReport",
    "Architecture",
    "CompatibilityResult",
    "CompatibilityStatus",
    "Dependency",
    "DependencyType",
    "ImportRecord",
    "ImportType",
    "MappingSource",
    "OperatingSystem",
    "PackageMapping",
    "ProjectConfig",
    "ProjectInformation",
    "PythonImplementation",
    "ResolutionResult",
    "TargetEnvironment",
    "ValidationResult",
    "ValidationStatus",
]

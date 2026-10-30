"""PyDeps: A Python Dependency Intelligence Engine."""

from __future__ import annotations

from pydeps.config import get_default_config, load_config_from_file, resolve_project_config
from pydeps.exceptions import (
    CompatibilityError,
    ConfigError,
    EnvironmentValidationError,
    PyDepsError,
    ResolutionError,
    TargetEnvironmentError,
)
from pydeps.models import (
    AnalysisReport,
    Architecture,
    CompatibilityResult,
    CompatibilityStatus,
    Dependency,
    DependencyType,
    ImportRecord,
    ImportType,
    MappingSource,
    OperatingSystem,
    PackageMapping,
    ProjectConfig,
    ProjectInformation,
    PythonImplementation,
    ResolutionResult,
    TargetEnvironment,
    ValidationResult,
    ValidationStatus,
)

__version__ = "0.1.0"

__all__ = [
    "AnalysisReport",
    "Architecture",
    "CompatibilityError",
    "CompatibilityResult",
    "CompatibilityStatus",
    "ConfigError",
    "Dependency",
    "DependencyType",
    "EnvironmentValidationError",
    "ImportRecord",
    "ImportType",
    "MappingSource",
    "OperatingSystem",
    "PackageMapping",
    "ProjectConfig",
    "ProjectInformation",
    "PyDepsError",
    "PythonImplementation",
    "ResolutionError",
    "ResolutionResult",
    "TargetEnvironment",
    "TargetEnvironmentError",
    "ValidationResult",
    "ValidationStatus",
    "__version__",
    "get_default_config",
    "load_config_from_file",
    "resolve_project_config",
]

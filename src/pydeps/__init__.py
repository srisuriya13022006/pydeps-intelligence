"""PyDeps: A Python Dependency Intelligence Engine."""

from __future__ import annotations

from pydeps.aggregator import ImportAggregator
from pydeps.analyzer import ASTImportVisitor, ImportAnalyzer
from pydeps.classifier import LocalModuleDetector, StdlibCatalog
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
    ImportAnalysisResult,
    ImportContext,
    ImportRecord,
    ImportType,
    MappingSource,
    OperatingSystem,
    PackageMapping,
    ProjectConfig,
    ProjectInformation,
    ProjectStructure,
    PythonImplementation,
    ResolutionResult,
    TargetEnvironment,
    ValidationResult,
    ValidationStatus,
)
from pydeps.scanner import KNOWN_METADATA_FILES, ProjectScanner

__version__ = "0.1.0"

__all__ = [
    "KNOWN_METADATA_FILES",
    "ASTImportVisitor",
    "AnalysisReport",
    "Architecture",
    "CompatibilityError",
    "CompatibilityResult",
    "CompatibilityStatus",
    "ConfigError",
    "Dependency",
    "DependencyType",
    "EnvironmentValidationError",
    "ImportAggregator",
    "ImportAnalysisResult",
    "ImportAnalyzer",
    "ImportContext",
    "ImportRecord",
    "ImportType",
    "LocalModuleDetector",
    "MappingSource",
    "OperatingSystem",
    "PackageMapping",
    "ProjectConfig",
    "ProjectInformation",
    "ProjectScanner",
    "ProjectStructure",
    "PyDepsError",
    "PythonImplementation",
    "ResolutionError",
    "ResolutionResult",
    "StdlibCatalog",
    "TargetEnvironment",
    "TargetEnvironmentError",
    "ValidationResult",
    "ValidationStatus",
    "__version__",
    "get_default_config",
    "load_config_from_file",
    "resolve_project_config",
]

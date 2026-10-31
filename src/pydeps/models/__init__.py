"""Domain data models for PyDeps."""

from __future__ import annotations

from pydeps.metadata.metadata_models import (
    MetadataResult,
    PackageRelease,
    ReleaseArtifact,
)
from pydeps.models.analysis import ImportAnalysisResult
from pydeps.models.compatibility import (
    ArtifactCompatibility,
    CompatibilityMatrix,
    CompatibilityResult,
    CompatibilityStatus,
    MarkerEvaluation,
    PackageCompatibility,
    PackageCompatibilityMatrix,
)
from pydeps.models.dependencies import (
    Dependency,
    DependencyType,
    ResolutionConflict,
    ResolutionDiagnostic,
    ResolutionMode,
    ResolutionRequest,
    ResolutionResult,
    ResolutionStatus,
    ResolutionStrategy,
    ResolutionTarget,
    ResolvedDependencyGraph,
    ResolvedPackage,
)
from pydeps.models.imports import (
    ImportContext,
    ImportRecord,
    ImportType,
    MappingSource,
    PackageMapping,
)
from pydeps.models.mapping import (
    ConfidenceLevel,
    PackageMappingResult,
    PackageReport,
)
from pydeps.models.project import (
    Architecture,
    OperatingSystem,
    ProjectConfig,
    PythonImplementation,
    TargetEnvironment,
)
from pydeps.models.report import AnalysisReport, ProjectInformation
from pydeps.models.structure import ProjectStructure
from pydeps.models.validation import (
    EnvironmentInfo,
    ExecutionPolicy,
    ImportTestResult,
    NetworkPolicy,
    ProjectTestResult,
    RunnerCapabilities,
    ValidationReport,
    ValidationRequest,
    ValidationResult,
    ValidationStage,
    ValidationStageResult,
    ValidationStatus,
)

__all__ = [
    "AnalysisReport",
    "Architecture",
    "ArtifactCompatibility",
    "CompatibilityMatrix",
    "CompatibilityResult",
    "CompatibilityStatus",
    "ConfidenceLevel",
    "Dependency",
    "DependencyType",
    "EnvironmentInfo",
    "ExecutionPolicy",
    "ImportAnalysisResult",
    "ImportContext",
    "ImportRecord",
    "ImportTestResult",
    "ImportType",
    "MappingSource",
    "MarkerEvaluation",
    "MetadataResult",
    "NetworkPolicy",
    "OperatingSystem",
    "PackageCompatibility",
    "PackageCompatibilityMatrix",
    "PackageMapping",
    "PackageMappingResult",
    "PackageRelease",
    "PackageReport",
    "ProjectConfig",
    "ProjectInformation",
    "ProjectStructure",
    "ProjectTestResult",
    "PythonImplementation",
    "ReleaseArtifact",
    "ResolutionConflict",
    "ResolutionDiagnostic",
    "ResolutionMode",
    "ResolutionRequest",
    "ResolutionResult",
    "ResolutionStatus",
    "ResolutionStrategy",
    "ResolutionTarget",
    "ResolvedDependencyGraph",
    "ResolvedPackage",
    "RunnerCapabilities",
    "TargetEnvironment",
    "ValidationReport",
    "ValidationRequest",
    "ValidationResult",
    "ValidationStage",
    "ValidationStageResult",
    "ValidationStatus",
]

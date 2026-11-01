"""Domain data models for PyDeps."""

from __future__ import annotations

from pydeps_intelligence.metadata.metadata_models import (
    MetadataResult,
    PackageRelease,
    ReleaseArtifact,
)
from pydeps_intelligence.models.analysis import ImportAnalysisResult
from pydeps_intelligence.models.compatibility import (
    ArtifactCompatibility,
    CompatibilityMatrix,
    CompatibilityResult,
    CompatibilityStatus,
    MarkerEvaluation,
    PackageCompatibility,
    PackageCompatibilityMatrix,
)
from pydeps_intelligence.models.dependencies import (
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
from pydeps_intelligence.models.imports import (
    ImportContext,
    ImportRecord,
    ImportType,
    MappingSource,
    PackageMapping,
)
from pydeps_intelligence.models.mapping import (
    ConfidenceLevel,
    PackageMappingResult,
    PackageReport,
)
from pydeps_intelligence.models.project import (
    Architecture,
    OperatingSystem,
    ProjectConfig,
    PythonImplementation,
    TargetEnvironment,
)
from pydeps_intelligence.models.report import AnalysisReport, ProjectInformation
from pydeps_intelligence.models.structure import ProjectStructure
from pydeps_intelligence.models.validation import (
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
from pydeps_intelligence.reporting.report_schema import (
    DependencyHealthStatus,
    DiagnosticReport,
    RecommendationItem,
    RecommendationSeverity,
    StageStatus,
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
    "DependencyHealthStatus",
    "DependencyType",
    "DiagnosticReport",
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
    "RecommendationItem",
    "RecommendationSeverity",
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
    "StageStatus",
    "TargetEnvironment",
    "ValidationReport",
    "ValidationRequest",
    "ValidationResult",
    "ValidationStage",
    "ValidationStageResult",
    "ValidationStatus",
]
